"""Eksperimen FoodSave yang dapat diulang dari notebook maupun terminal.

Semua statistik preprocessing dipelajari dari training saja. Pemenang dipilih
dengan MAE validasi sebelum hasil test dibuka. Satuan target selalu kilogram.
"""
from pathlib import Path
import json
import os
import time
import hashlib

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ.setdefault('TF_NUM_INTRAOP_THREADS', '2')
os.environ.setdefault('TF_NUM_INTEROP_THREADS', '1')
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results' / 'evaluation'
ART = ROOT / 'models' / 'best_model'
TARGET = 'food_waste_kg'
SEED = 42
WINDOW = 7
# Kategori limbah dikeluarkan: waktu tersedianya belum terverifikasi.
# past_waste_kg juga dikeluarkan: definisi periode dan restoran belum diketahui.
NUM = ['meals_served', 'kitchen_staff', 'temperature_C', 'humidity_percent', 'special_event']
CAT = ['staff_experience']


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def load_data():
    """Gunakan train berlabel, bukan submission atau test Kaggle tanpa label."""
    path = ROOT / 'dataset/raw/train.csv'
    df = pd.read_csv(path)
    df['_row'] = np.arange(len(df))
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df[TARGET] = pd.to_numeric(df[TARGET], errors='coerce')
    valid = df['date'].notna() & df[TARGET].notna() & (df[TARGET] >= 0)
    df = df.loc[valid].sort_values(['date', '_row']).reset_index(drop=True)
    # Duplikat persis tidak boleh muncul pada dua partisi berbeda.
    # Dedup global untuk identitas observasi, bukan estimasi statistik.
    key = [c for c in df if c not in ['ID', '_row']]
    duplicates = int(df.duplicated(key).sum())
    df = df.drop_duplicates(key).reset_index(drop=True)
    dates = df['date'].drop_duplicates().sort_values().to_numpy()
    cut1, cut2 = dates[int(len(dates) * .60)], dates[int(len(dates) * .80)]
    df['split'] = np.where(df.date < cut1, 'train', np.where(df.date < cut2, 'validation', 'test'))
    assert df.loc[df.split == 'train', 'date'].max() < df.loc[df.split == 'validation', 'date'].min()
    assert df.loc[df.split == 'validation', 'date'].max() < df.loc[df.split == 'test', 'date'].min()
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    audit = {'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'raw_rows': int(valid.size), 'invalid_date_or_target_removed': int((~valid).sum()),
             'exact_duplicates_removed_for_all_models': duplicates, 'usable_rows': len(df),
             'missing_before': pd.read_csv(path).isna().sum().to_dict(),
             'excluded_features': ['ID', 'waste_category', 'past_waste_kg'],
             'sequence_warning': '7 observasi, bukan 7 hari. Tidak ada ID restoran; urutan temporal tidak membuktikan satu seri restoran.',
             'split': {s: {'n': len(d), 'start': str(d.date.min().date()), 'end': str(d.date.max().date())}
                       for s, d in df.groupby('split')}}
    save_json(OUT / 'data_audit.json', audit)
    df[['_row', 'ID', 'date', 'split', TARGET]].to_csv(OUT / 'split_manifest.csv', index=False)
    return df


class FoodPreprocessor:
    """Standard: konversi sederhana. Robust: normalisasi dan batas IQR training."""
    def __init__(self, method='standard'):
        self.method = method

    def clean(self, df):
        d = df[NUM + CAT].copy()
        for c in NUM:
            s = d[c]
            if self.method == 'robust':
                s = s.astype('string').str.strip().str.replace(',', '', regex=False).str.replace(r'[^0-9.eE+\-]', '', regex=True)
            # Float mendukung median/batas IQR pecahan, termasuk pada pandas 3.
            d[c] = pd.to_numeric(s, errors='coerce').astype('float64').replace([np.inf, -np.inf], np.nan)
        for c in CAT:
            s = d[c].astype('string')
            if self.method == 'robust':
                s = s.str.strip().str.lower().replace({'nan': pd.NA, 'none': pd.NA, '': pd.NA})
            d[c] = s
        date = pd.to_datetime(df['date'])
        d['is_weekend'] = (date.dt.dayofweek >= 5).astype(float)
        d['month_sin'] = np.sin(2 * np.pi * date.dt.month / 12)
        d['month_cos'] = np.cos(2 * np.pi * date.dt.month / 12)
        return d

    def fit(self, df):
        d = self.clean(df)
        self.numerics = d.select_dtypes(include='number').columns.tolist()
        self.medians = d[self.numerics].median().fillna(0)
        self.modes = {c: (d[c].dropna().mode().iloc[0] if d[c].notna().any() else 'unknown') for c in CAT}
        self.bounds = {}
        if self.method == 'robust':
            for c in ['meals_served', 'kitchen_staff', 'temperature_C', 'humidity_percent']:
                q1, q3 = d[c].quantile([.25, .75]); iqr = q3 - q1
                self.bounds[c] = (float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr))
        native = self.native(df)
        self.columns = pd.get_dummies(native, columns=CAT, dtype=float).columns.tolist()
        self.scaler = (RobustScaler() if self.method == 'robust' else StandardScaler())
        self.scaler.fit(self.encoded(df))
        return self

    def native(self, df):
        d = self.clean(df)
        d[self.numerics] = d[self.numerics].fillna(self.medians)
        for c, bounds in self.bounds.items():
            d[c] = d[c].clip(*bounds)
        for c in CAT:
            d[c] = d[c].fillna(self.modes[c]).astype(str)
        # Rasio dihitung setelah imputasi dan penanganan outlier.
        d['staff_per_portion'] = d.kitchen_staff / d.meals_served.clip(lower=1)
        d['portion_per_staff'] = d.meals_served / d.kitchen_staff.clip(lower=1)
        d['special_event_portion'] = d.special_event * d.meals_served
        return d

    def encoded(self, df):
        return pd.get_dummies(self.native(df), columns=CAT, dtype=float).reindex(columns=self.columns, fill_value=0).astype(float)

    def transform(self, df, scaled=False):
        x = self.encoded(df)
        return self.scaler.transform(x).astype('float32') if scaled else x


def sequence(x, indices, window=WINDOW):
    """Jendela fitur s.d. hari rencana saat ini; tanpa target aktual sebagai input.

    Fitur operasional hari target diasumsikan sudah diketahui ketika merencanakan.
    Observasi masa depan dan label test tidak pernah dipakai sebagai konteks.
    """
    return np.asarray([x[i-window+1:i+1] for i in indices], dtype='float32')


def metrics(y, pred):
    error = np.asarray(y) - np.asarray(pred)
    return {'MAE': float(mean_absolute_error(y, pred)), 'RMSE': float(np.sqrt(mean_squared_error(y, pred))),
            'R2': float(r2_score(y, pred)), 'MedAE': float(np.median(np.abs(error))),
            'Bias': float(-error.mean()), 'WAPE_percent': float(np.abs(error).sum()/np.abs(y).sum()*100)}


def train_candidate(name, config, xtr, ytr, xva, yva, target_scaler):
    """Latih satu kandidat dan simpan kurva training/validation dalam kg."""
    start = time.perf_counter()
    if name == 'RandomForest':
        model = RandomForestRegressor(random_state=SEED, n_jobs=2, warm_start=True, **config)
        rows = []
        for n in [20, 60, 120, 200]:
            model.set_params(n_estimators=n).fit(xtr, ytr)
            rows.append({'step': n, 'train_RMSE': metrics(ytr, model.predict(xtr))['RMSE'],
                         'validation_RMSE': metrics(yva, model.predict(xva))['RMSE']})
        curve = pd.DataFrame(rows)
    elif name == 'XGBoost':
        from xgboost import XGBRegressor
        model = XGBRegressor(n_estimators=500, learning_rate=.04, objective='reg:squarederror',
                             eval_metric='rmse', early_stopping_rounds=40, random_state=SEED, n_jobs=2, **config)
        model.fit(xtr, ytr, eval_set=[(xtr, ytr), (xva, yva)], verbose=False)
        h = model.evals_result()
        curve = pd.DataFrame({'train_RMSE': h['validation_0']['rmse'], 'validation_RMSE': h['validation_1']['rmse']})
        curve['step'] = np.arange(1, len(curve)+1)
    elif name == 'CatBoost':
        from catboost import CatBoostRegressor
        model = CatBoostRegressor(iterations=500, learning_rate=.04, loss_function='RMSE',
                                  random_seed=SEED, thread_count=2, allow_writing_files=False, verbose=False, **config)
        model.fit(xtr, ytr, cat_features=CAT, eval_set=(xva, yva), early_stopping_rounds=40)
        h = model.get_evals_result()
        curve = pd.DataFrame({'train_RMSE': h['learn']['RMSE'], 'validation_RMSE': h['validation']['RMSE']})
        curve['step'] = np.arange(1, len(curve)+1)
    else:
        import tensorflow as tf
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(SEED)
        tf.config.experimental.enable_op_determinism()
        model = tf.keras.Sequential([tf.keras.layers.Input(shape=xtr.shape[1:]),
                    tf.keras.layers.LSTM(config['units']), tf.keras.layers.Dense(16, activation='relu'),
                    tf.keras.layers.Dense(1)])
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=config['learning_rate'], clipnorm=1.), loss='mse')
        a = target_scaler.transform(np.asarray(ytr).reshape(-1, 1)).astype('float32')
        b = target_scaler.transform(np.asarray(yva).reshape(-1, 1)).astype('float32')
        # Batasi thread agar pelatihan tidak membebani seluruh CPU Windows.
        opts = tf.data.Options(); opts.threading.private_threadpool_size = 1
        tr = tf.data.Dataset.from_tensor_slices((xtr, a)).batch(32).with_options(opts)
        va = tf.data.Dataset.from_tensor_slices((xva, b)).batch(64).with_options(opts)
        class GradientMonitor(tf.keras.callbacks.Callback):
            """Ukur besar gradien pada batch training tetap setiap akhir epoch."""
            def __init__(self):
                super().__init__(); self.norms = []
            def on_epoch_end(self, epoch, logs=None):
                with tf.GradientTape() as tape:
                    loss = tf.reduce_mean(tf.square(self.model(xtr[:32], training=False) - a[:32]))
                gradients = tape.gradient(loss, self.model.trainable_variables)
                self.norms.append(float(tf.linalg.global_norm([g for g in gradients if g is not None])))
        monitor = GradientMonitor()
        hist = model.fit(tr, validation_data=va, epochs=160, verbose=0,
                    callbacks=[monitor, tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=20, restore_best_weights=True)])
        factor = float(target_scaler.scale_[0])
        curve = pd.DataFrame({'step': np.arange(1, len(hist.history['loss'])+1),
                    'train_RMSE': np.sqrt(hist.history['loss'])*factor,
                    'validation_RMSE': np.sqrt(hist.history['val_loss'])*factor,
                    'gradient_norm_fixed_train_batch': monitor.norms})
    return model, curve, time.perf_counter() - start


def predict(model, x, name, target_scaler):
    if name == 'LSTM':
        p = model(x, training=False).numpy().ravel()
        return target_scaler.inverse_transform(p.reshape(-1, 1)).ravel()
    return model.predict(x)


def prepare(method):
    df = load_data()
    prep = FoodPreprocessor(method).fit(df.loc[df.split == 'train'])
    # Semua model dievaluasi pada baris yang sama setelah konteks awal tersedia.
    eligible = np.arange(len(df)) >= WINDOW-1
    idx = {s: np.flatnonzero((df.split == s).to_numpy() & eligible) for s in ['train', 'validation', 'test']}
    yscaler = StandardScaler().fit(df.loc[idx['train'], TARGET].to_numpy().reshape(-1, 1))
    x = prep.transform(df)
    xs = prep.transform(df, scaled=True)
    native = prep.native(df)
    return df, prep, idx, yscaler, x, xs, native


def run_model(name):
    """Dua konfigurasi per pendekatan; pilih menggunakan validasi saja."""
    grids = {'RandomForest': [{'max_depth': None, 'min_samples_leaf': 1, 'max_features': 1.},
                               {'max_depth': 10, 'min_samples_leaf': 3, 'max_features': .8}],
             'XGBoost': [{'max_depth': 3, 'reg_lambda': 5.}, {'max_depth': 5, 'reg_lambda': 10.}],
             'CatBoost': [{'depth': 4, 'l2_leaf_reg': 5.}, {'depth': 6, 'l2_leaf_reg': 10.}],
             'LSTM': [{'units': 24, 'learning_rate': .001}, {'units': 48, 'learning_rate': .003}]}
    results = []
    for method in ['standard', 'robust']:
        df, prep, idx, ys, x, xs, native = prepare(method)
        y = {s: df.loc[ix, TARGET].to_numpy() for s, ix in idx.items()}
        if name == 'LSTM':
            features = {s: sequence(xs, ix) for s, ix in idx.items()}
        elif name == 'CatBoost':
            features = {s: native.iloc[ix] for s, ix in idx.items()}
        else:
            features = {s: x.iloc[ix] for s, ix in idx.items()}
        candidates, tuned = [], []
        for config in grids[name]:
            model, curve, duration = train_candidate(name, config, features['train'], y['train'], features['validation'], y['validation'], ys)
            score = metrics(y['validation'], predict(model, features['validation'], name, ys))
            candidates.append((score['MAE'], model, curve, duration, config))
            tuned.append({'config': json.dumps(config), **score, 'train_time_s': duration})
        _, model, curve, duration, config = min(candidates, key=lambda c: c[0])
        label = f'{name}_{method}'
        curve.to_csv(OUT / f'{label}_curve.csv', index=False)
        pd.DataFrame(tuned).to_csv(OUT / f'{label}_tuning.csv', index=False)
        plot_curve(curve, label)
        # Tidak melatih ulang pada validasi agar peran setiap partisi tetap jelas.
        protocol = hashlib.sha256(Path(__file__).read_bytes() + (ROOT/'dataset/raw/train.csv').read_bytes()).hexdigest()
        row = {'model': name, 'preprocessing': method, 'config': json.dumps(config), 'protocol_sha256': protocol,
               'train_time_s': duration, 'tuning_total_time_s': sum(t['train_time_s'] for t in tuned),
               'n_train': len(y['train']), 'n_validation': len(y['validation']), 'n_test': len(y['test'])}
        for split in ['train', 'validation', 'test']:
            start = time.perf_counter()
            pred = predict(model, features[split], name, ys)
            elapsed = time.perf_counter() - start
            row.update({f'{split}_{k}': v for k, v in metrics(y[split], pred).items()})
            row[f'{split}_prediction_time_s'] = elapsed
            row[f'{split}_ms_per_row'] = elapsed / len(pred) * 1000
            pd.DataFrame({'row': df.loc[idx[split], '_row'], 'date': df.loc[idx[split], 'date'],
                          'actual': y[split], 'prediction': pred, 'residual': y[split]-pred}).to_csv(OUT / f'{label}_{split}_predictions.csv', index=False)
        if name == 'LSTM':
            model.save(ART / f'{label}.keras')
        else:
            joblib.dump(model, ART / f'{label}.joblib')
        # Simpan class dari modul stabil, termasuk jika CLI berjalan sebagai __main__.
        from src.experiment import FoodPreprocessor as PortablePreprocessor
        portable_prep = PortablePreprocessor(method)
        portable_prep.__dict__.update(prep.__dict__)
        joblib.dump({'preprocessor': portable_prep, 'target_scaler': ys, 'window': WINDOW, 'name': name}, ART / f'{label}_preprocessing.joblib')
        save_json(OUT / f'{label}_metrics.json', row)
        # Importance par permutation sur validation, sans explorer le test.
        rng = np.random.default_rng(SEED)
        baseline = row['validation_MAE']; importance = []
        names = prep.columns if name != 'CatBoost' else native.columns.tolist()
        for j, feature in enumerate(names):
            differences = []
            for repeat in range(3):
                shuffled = features['validation'].copy()
                order = rng.permutation(len(shuffled))
                if name == 'LSTM':
                    shuffled[:, :, j] = shuffled[order, :, j]
                else:
                    shuffled.iloc[:, j] = shuffled.iloc[order, j].to_numpy()
                differences.append(metrics(y['validation'], predict(model, shuffled, name, ys))['MAE']-baseline)
            importance.append({'feature': feature, 'MAE_increase': np.mean(differences), 'std': np.std(differences)})
        pd.DataFrame(importance).sort_values('MAE_increase', ascending=False).to_csv(OUT / f'{label}_importance.csv', index=False)
        results.append(row)
        print(label, 'validation MAE=', round(row['validation_MAE'], 4), 'test MAE=', round(row['test_MAE'], 4), flush=True)
    return pd.DataFrame(results)


def plot_curve(curve, label):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(curve.step, curve.train_RMSE, label='Training')
    ax.plot(curve.step, curve.validation_RMSE, label='Validasi')
    kind = 'Jumlah pohon (tanpa gradient descent)' if label.startswith('RandomForest') else ('Epoch Adam / gradient descent' if label.startswith('LSTM') else 'Tahap gradient boosting')
    ax.set(xlabel=kind, ylabel='RMSE (kg)', title=f'Proses belajar {label}')
    ax.legend(); fig.tight_layout(); fig.savefig(OUT / f'{label}_curve.png', dpi=140); plt.close(fig)
    if 'gradient_norm_fixed_train_batch' in curve:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(curve.step, curve.gradient_norm_fixed_train_batch)
        ax.set(xlabel='Epoch', ylabel='Norma gradien pada target terskala', title=f'Besar gradien LSTM {label}')
        fig.tight_layout(); fig.savefig(OUT / f'{label}_gradient.png', dpi=140); plt.close(fig)


def evaluate():
    """Rangking validasi dikunci; test hanya melaporkan generalisasi akhir."""
    files = [OUT / f'{name}_{method}_metrics.json' for name in ['LSTM', 'RandomForest', 'XGBoost', 'CatBoost'] for method in ['standard', 'robust']]
    if not all(p.exists() for p in files):
        raise RuntimeError('Jalankan keempat notebook model terlebih dahulu: masih ada eksperimen belum selesai.')
    table = pd.DataFrame([json.loads(p.read_text(encoding='utf-8')) for p in files])
    current = hashlib.sha256(Path(__file__).read_bytes() + (ROOT/'dataset/raw/train.csv').read_bytes()).hexdigest()
    if 'protocol_sha256' not in table or not table.protocol_sha256.eq(current).all():
        raise RuntimeError('Kode atau dataset berubah. Jalankan ulang semua model agar hasil tidak tercampur dengan eksperimen lama.')
    import importlib.metadata
    import platform
    save_json(OUT/'environment.json', {'python': platform.python_version(), 'platform': platform.platform(),
             'seed': SEED, 'window_observations': WINDOW,
             'packages': {p: importlib.metadata.version(p) for p in ['numpy','pandas','scikit-learn','tensorflow','xgboost','catboost','joblib']}})
    table = table.sort_values(['validation_MAE', 'validation_RMSE', 'validation_ms_per_row']).reset_index(drop=True)
    table['validation_rank'] = np.arange(1, 9)
    table.to_csv(OUT / 'experiment_results.csv', index=False)
    df, prep, idx, ys, x, xs, native = prepare('standard')
    baseline = float(df.loc[idx['train'], TARGET].median())
    base = {s: metrics(df.loc[ix, TARGET].to_numpy(), np.full(len(ix), baseline)) for s, ix in idx.items()}
    save_json(OUT / 'baseline_metrics.json', base)
    best = table.iloc[0].to_dict(); label = f"{best['model']}_{best['preprocessing']}"
    best['selection_rule'] = 'MAE validasi terkecil; tie-break RMSE validasi dan latensi validasi. Tidak berdasarkan test.'
    best['baseline_test_MAE'] = base['test']['MAE']
    va = pd.read_csv(OUT / f'{label}_validation_predictions.csv')
    te = pd.read_csv(OUT / f'{label}_test_predictions.csv')
    # Interval empiris dari validasi, bukan jaminan coverage conformal karena validasi dipakai seleksi.
    radius = float(np.quantile(np.abs(va.residual), .90))
    best['empirical_90_percent_interval_radius_kg'] = radius
    best['test_interval_coverage'] = float((np.abs(te.residual) <= radius).mean())
    best['interval_note'] = 'Interval empiris eksploratif; validasi dipakai seleksi, data temporal tidak exchangeable.'
    best['risk_thresholds_train_kg'] = df.loc[idx['train'], TARGET].quantile([1/3, 2/3]).tolist()
    save_json(OUT / 'best_model.json', best)
    # Artefak baru disimpan terpisah agar tidak menimpa model lama milik tim.
    save_json(ART / 'selected_model.json', {'model_path': str((ART / (label + ('.keras' if best['model']=='LSTM' else '.joblib'))).relative_to(ROOT)),
                        'preprocessing_path': str((ART / f'{label}_preprocessing.joblib').relative_to(ROOT)), **best})
    labels = table.model + ' / ' + table.preprocessing
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for ax, col in zip(axes.flat, ['MAE','RMSE','R2','train_time_s','test_ms_per_row','Bias']):
        field = col if col in table else 'test_'+col
        ax.barh(labels, table[field]); ax.set_title(field); ax.invert_yaxis()
    fig.tight_layout(); fig.savefig(OUT / 'comparison_metrics.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0,0].scatter(te.actual, te.prediction, alpha=.6)
    low, high = min(te.actual.min(), te.prediction.min()), max(te.actual.max(), te.prediction.max())
    axes[0,0].plot([low,high],[low,high],'r--'); axes[0,0].set(xlabel='Aktual (kg)',ylabel='Prediksi (kg)',title=label)
    axes[0,1].hist(te.residual, bins=25); axes[0,1].axvline(0,color='red'); axes[0,1].set_title('Distribusi kesalahan (kg)')
    axes[1,0].scatter(te.prediction,te.residual,alpha=.6); axes[1,0].axhline(0,color='red'); axes[1,0].set(xlabel='Prediksi (kg)',ylabel='Aktual - prediksi (kg)')
    axes[1,1].plot(te.actual.to_numpy(),label='Aktual'); axes[1,1].plot(te.prediction.to_numpy(),label='Prediksi'); axes[1,1].legend(); axes[1,1].set_title('Urutan observasi test')
    fig.tight_layout(); fig.savefig(OUT / 'best_model_diagnostics.png',dpi=140); plt.close(fig)
    imp = pd.read_csv(OUT / f'{label}_importance.csv').head(12).sort_values('MAE_increase')
    fig, ax=plt.subplots(figsize=(9,5));ax.barh(imp.feature,imp.MAE_increase,xerr=imp['std']);ax.set(xlabel='Kenaikan MAE validasi jika fitur diacak (kg)',title='Pengaruh fitur model terpilih');fig.tight_layout();fig.savefig(OUT/'best_model_importance.png',dpi=140);plt.close(fig)
    return table


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--model', choices=['LSTM','RandomForest','XGBoost','CatBoost','all','evaluate'],default='all')
    args=parser.parse_args()
    if args.model=='all':
        for name in ['RandomForest','XGBoost','CatBoost','LSTM']: run_model(name)
        print(evaluate().to_string(index=False))
    elif args.model=='evaluate': print(evaluate().to_string(index=False))
    else: run_model(args.model)
