"""Isi langkah demi langkah untuk notebook model, tanpa mengganti sel lama."""
import ast
import textwrap
from pathlib import Path


def model_cells(name, description, md, code, setup):
    tree=ast.parse((Path(__file__).parent/'experiment.py').read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='train_candidate')
    branch=next(n for n in fn.body if isinstance(n,ast.If))
    while True:
        if isinstance(branch.test,ast.Compare) and ast.literal_eval(branch.test.comparators[0])==name:
            selected=branch.body;break
        if branch.orelse and isinstance(branch.orelse[0],ast.If):branch=branch.orelse[0]
        else:selected=branch.orelse;break
    body='\n'.join(ast.unparse(node) for node in selected)
    training='def latih_kandidat(config, xtr, ytr, xva, yva, target_scaler):\n    start = time.perf_counter()\n'+textwrap.indent(body,'    ')+'\n    return model, curve, time.perf_counter() - start'
    grids={
        'LSTM':"[{'units':24,'learning_rate':.001}, {'units':48,'learning_rate':.003}]",
        'RandomForest':"[{'max_depth':None,'min_samples_leaf':1,'max_features':1.0}, {'max_depth':10,'min_samples_leaf':3,'max_features':.8}]",
        'XGBoost':"[{'max_depth':3,'reg_lambda':5.0}, {'max_depth':5,'reg_lambda':10.0}]",
        'CatBoost':"[{'depth':4,'l2_leaf_reg':5.0}, {'depth':6,'l2_leaf_reg':10.0}]"}
    imports=setup+"""
import time
import hashlib
import inspect
import joblib
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from src.experiment import NUM, CAT, TARGET, SEED, WINDOW, FoodPreprocessor, sequence, metrics, predict, plot_curve, save_json
"""+f"MODEL = {name!r}\nCONFIGS = {grids[name]}\n"
    cells=[md(f'# Model {name} untuk prediksi limbah makanan\n\n**Tujuan notebook:** menyelesaikan dua eksperimen {name} dengan Standard dan Robust secara terbuka, langkah demi langkah.\n\n{description}\n\n**Pertanyaan yang dijawab:** Seberapa besar kesalahan dalam kg? Apakah Robust membantu? Apakah training terlalu bagus dibanding validasi? Fitur apa yang membantu model? Seberapa cepat prediksinya? Semua angka kesimpulan dihasilkan dari kode, bukan angka ilustrasi.'),
           md('## Langkah 1 Menyiapkan alat dan konfigurasi\n`numpy` mengolah angka, `pandas` mengolah tabel, `matplotlib` membuat grafik, dan `joblib` menyimpan model. Seed 42 membantu pengulangan. Fungsi bersama dipakai untuk menjaga definisi metrik, data, dan preprocessing tetap sama di empat notebook. Bagian pelatihan model ditulis langsung di notebook ini.'),code(imports),
           md('## Langkah 2 Membaca data dan memastikan urutan waktu\nTraining memakai tanggal awal, validasi tanggal berikutnya, dan test tanggal terbaru. Tidak ada tanggal yang masuk dua partisi. Duplikat persis tanpa ID dibuang untuk semua model agar tidak muncul salinan observasi yang sama pada train/test. Dataset test Kaggle tanpa label tidak digunakan sebagai holdout penelitian.'),
           code("""df = load_data()
display(df.head(8))
display(df.groupby('split').agg(jumlah=('date','size'), tanggal_awal=('date','min'), tanggal_akhir=('date','max')))
display(json.loads((OUT/'data_audit.json').read_text(encoding='utf-8')))
assert df.loc[df.split=='train','date'].max() < df.loc[df.split=='validation','date'].min()
assert df.loc[df.split=='validation','date'].max() < df.loc[df.split=='test','date'].min()
"""),
           md('## Langkah 3 Memahami input dan mencegah kebocoran informasi\nHanya informasi yang diasumsikan tersedia ketika merencanakan operasional yang digunakan. ID, kategori limbah, dan limbah sebelumnya dikeluarkan; asal/waktu ketersediaannya belum terverifikasi. Hari dihitung dari tanggal. Suhu/kelembapan harus berupa perkiraan jika nilai aktual belum diketahui. Target food_waste_kg tidak pernah menjadi input.\n\nStandard memakai konversi sederhana, imputasi median/modus training, dan kategori apa adanya. Robust menambah pembersihan simbol/spasi, normalisasi kategori, batas IQR training, dan RobustScaler untuk LSTM. Model pohon tidak memerlukan scaling. Target aktual tidak dipotong. Rasio dihitung setelah pembersihan agar tidak membagi dengan nilai nol.'),
           code("display(Code(inspect.getsource(FoodPreprocessor), language='python'))"),
           md('## Langkah 4 Menyiapkan fitur dan baris evaluasi yang setara\nStatistik preprocessing dipelajari dari training saja, lalu dipakai pada validasi/test. Tujuh observasi pertama diperlukan untuk jendela LSTM. Enam baris awal tidak dijadikan target pada seluruh model agar baris pembanding identik. Kategori CatBoost tetap berupa teks; RF/XGBoost memakai one-hot. LSTM memakai urutan fitur terskala. Tidak ada label test yang digunakan untuk konteks.'),
           code("""eligible = np.arange(len(df)) >= WINDOW-1
idx = {s: np.flatnonzero((df.split==s).to_numpy() & eligible) for s in ['train','validation','test']}
data = {}
for method in ['standard','robust']:
    prep = FoodPreprocessor(method).fit(df[df.split=='train'])
    x = prep.transform(df)
    scaled = prep.transform(df, scaled=True)
    native = prep.native(df)
    target_scaler = StandardScaler().fit(df.loc[idx['train'],TARGET].to_numpy().reshape(-1,1))
    y = {s:df.loc[ix,TARGET].to_numpy() for s,ix in idx.items()}
    if MODEL=='LSTM':
        features = {s:sequence(scaled,ix) for s,ix in idx.items()}
    elif MODEL=='CatBoost':
        features = {s:native.iloc[ix] for s,ix in idx.items()}
    else:
        features = {s:x.iloc[ix] for s,ix in idx.items()}
    assert np.isfinite(x.to_numpy()).all() and np.isfinite(scaled).all()
    assert not set(['ID',TARGET,'waste_category','past_waste_kg']).intersection(x.columns)
    data[method] = {'prep':prep,'ys':target_scaler,'y':y,'features':features,'names':native.columns.tolist() if MODEL=='CatBoost' else x.columns.tolist()}
    print(method, '| jumlah fitur:', x.shape[1], '| bentuk input:', {s:v.shape for s,v in features.items()})
    display(native.head(4))
"""),
           md('## Langkah 5 Menulis cara pelatihan model\nFungsi berikut berisi kode model yang benar-benar dilatih, bukan placeholder. Training memperbarui parameter dari data latihan. Validasi memantau kemampuan di periode berikutnya. Early stopping menghentikan jaringan/boosting ketika validasi tidak membaik, lalu memakai keadaan terbaik. RF melihat kestabilan error ketika jumlah pohon bertambah.\n\nDua konfigurasi diuji per metode, bukan pencarian optimum global. Learning rate adalah besar langkah belajar; kedalaman pohon mengatur kerumitan aturan; regularisasi/minimum daun membatasi model agar tidak terlalu menyesuaikan training.'),code(training),
           md('## Langkah 6 Mencoba kandidat dan menghitung skor validasi\nBagian ini membutuhkan waktu komputasi. Semua kandidat dilatih hanya pada training. Masing-masing dibandingkan menggunakan MAE validasi dalam kg. Data test belum digunakan untuk memilih konfigurasi. Kurva training/validasi dan waktu setiap kandidat dicatat agar prosesnya dapat diaudit.'),
           code("""candidates = {}
tuning_rows = []
for method, d in data.items():
    candidates[method] = []
    for config in CONFIGS:
        model, curve, duration = latih_kandidat(config, d['features']['train'], d['y']['train'], d['features']['validation'], d['y']['validation'], d['ys'])
        prediction = predict(model, d['features']['validation'], MODEL, d['ys'])
        score = metrics(d['y']['validation'], prediction)
        tuning_rows.append({'preprocessing':method, 'config':json.dumps(config), **score, 'train_time_s':duration})
        candidates[method].append({'model':model,'curve':curve,'duration':duration,'config':config,'score':score})
        print(method, config, '| MAE validasi:', round(score['MAE'],4), 'kg', flush=True)
tuning = pd.DataFrame(tuning_rows)
display(tuning.sort_values(['preprocessing','MAE']))
"""),
           md('## Langkah 7 Mengunci konfigurasi dan membaca kurva belajar\nMAE validasi terendah memilih satu kandidat pada Standard dan satu pada Robust. Kurva yang turun berarti error mengecil; kurva tidak harus selalu turun. Error training yang jauh lebih rendah daripada validasi bisa menandakan overfitting atau perubahan distribusi waktu. Sumbu RF adalah jumlah pohon, sumbu boosting adalah tahap, dan sumbu LSTM adalah epoch. RF tidak memakai gradient descent.'),
           code("""selected = {method:min(items,key=lambda item:item['score']['MAE']) for method,items in candidates.items()}
for method,item in selected.items():
    label=f'{MODEL}_{method}'
    item['curve'].to_csv(OUT/f'{label}_curve.csv',index=False)
    tuning[tuning.preprocessing==method].drop(columns='preprocessing').to_csv(OUT/f'{label}_tuning.csv',index=False)
    plot_curve(item['curve'],label)
    print('Terpilih:',method,item['config'])
    display(Image(filename=str(OUT/f'{label}_curve.png')))
"""),
           md('## Langkah 8 Mengukur seluruh metrik training validasi dan test\nMAE: kesalahan absolut rata-rata dalam kg. RMSE: lebih sensitif terhadap error besar. R²: kemampuan menjelaskan variasi; dapat negatif. MedAE: median error absolut. Bias: prediksi dikurangi aktual; positif berarti terlalu tinggi. WAPE: total error absolut dibanding total limbah, bukan akurasi klasifikasi.\n\nWaktu prediksi berikut diukur untuk satu batch tanpa preprocessing dan pemuatan model. Milidetik per baris adalah waktu batch dibagi jumlah baris, bukan benchmark permintaan tunggal. Waktu training mencakup pelatihan dan pemantauan kurva kandidat terpilih, termasuk impor awal library/pengukuran gradien; total tuning mencakup kedua kandidat. Model tidak dilatih ulang pada validasi.'),
           code("""result_rows = []
protocol = hashlib.sha256((ROOT/'src/experiment.py').read_bytes()+(ROOT/'dataset/raw/train.csv').read_bytes()).hexdigest()
for method,item in selected.items():
    d=data[method];label=f'{MODEL}_{method}'
    row={'model':MODEL,'preprocessing':method,'config':json.dumps(item['config']),'protocol_sha256':protocol,
         'train_time_s':item['duration'],'tuning_total_time_s':float(tuning.loc[tuning.preprocessing==method,'train_time_s'].sum()),
         **{f'n_{s}':len(v) for s,v in d['y'].items()}}
    for split in ['train','validation','test']:
        start=time.perf_counter()
        prediction=predict(item['model'],d['features'][split],MODEL,d['ys'])
        elapsed=time.perf_counter()-start
        row.update({f'{split}_{k}':v for k,v in metrics(d['y'][split],prediction).items()})
        row[f'{split}_prediction_time_s']=elapsed
        row[f'{split}_ms_per_row']=elapsed/len(prediction)*1000
        pd.DataFrame({'row':df.loc[idx[split],'_row'],'date':df.loc[idx[split],'date'],'actual':d['y'][split],
                      'prediction':prediction,'residual':d['y'][split]-prediction}).to_csv(OUT/f'{label}_{split}_predictions.csv',index=False)
    save_json(OUT/f'{label}_metrics.json',row)
    result_rows.append(row)
hasil=pd.DataFrame(result_rows)
for split in ['train','validation','test']:
    display(Markdown(f'### Metrik {split}'))
    display(hasil[['model','preprocessing']+[f'{split}_{m}' for m in ['MAE','RMSE','R2','MedAE','Bias','WAPE_percent']]])
display(hasil[['model','preprocessing','train_time_s','tuning_total_time_s','test_prediction_time_s','test_ms_per_row']])
"""),
           md('## Langkah 9 Melihat prediksi dan kasus yang paling sulit\nGaris diagonal menandai prediksi sempurna. Residual positif berarti model meremehkan limbah. Histogram yang lebar berarti variasi error besar. Tabel error terbesar membantu mencari kondisi operasional yang sulit, tetapi tidak digunakan lagi untuk menyetel model; jika dilakukan, dibutuhkan test baru.'),
           code("""for method in ['standard','robust']:
    pred=pd.read_csv(OUT/f'{MODEL}_{method}_test_predictions.csv')
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    axes[0].scatter(pred.actual,pred.prediction,alpha=.6)
    limits=[min(pred.actual.min(),pred.prediction.min()),max(pred.actual.max(),pred.prediction.max())]
    axes[0].plot(limits,limits,'r--');axes[0].set(xlabel='Aktual kg',ylabel='Prediksi kg',title=f'{MODEL} {method}')
    axes[1].scatter(pred.prediction,pred.residual,alpha=.6);axes[1].axhline(0,color='red');axes[1].set(xlabel='Prediksi kg',ylabel='Aktual - prediksi kg')
    axes[2].hist(pred.residual,bins=20);axes[2].axvline(0,color='red');axes[2].set_title('Sebaran error kg')
    fig.tight_layout();fig.savefig(OUT/f'{MODEL}_{method}_diagnostics.png',dpi=140);display(fig);plt.close(fig)
    context=df[['_row','meals_served','kitchen_staff','special_event','staff_experience']]
    difficult=pred.merge(context,left_on='row',right_on='_row',how='left')
    display(difficult.assign(error_absolut=difficult.residual.abs()).nlargest(10,'error_absolut'))
"""),
           md('## Langkah 10 Menilai fitur yang membantu prediksi\nPermutation importance mengacak satu fitur pada validasi sebanyak tiga kali. Kenaikan MAE positif berarti fitur tersebut membantu model. Nilai negatif dapat terjadi akibat noise atau model yang terlalu mengandalkan fitur tersebut. Ini bukan bukti kausal. Rasio dan porsi saling berkaitan sehingga importance dapat terbagi. Pada LSTM, satu jalur fitur sepanjang jendela diacak sebagai satu blok; hasil bersifat diagnostik.'),
           code("""for method,item in selected.items():
    d=data[method];rng=np.random.default_rng(SEED);importance=[]
    for j,feature in enumerate(d['names']):
        differences=[]
        for repeat in range(3):
            shuffled=d['features']['validation'].copy();order=rng.permutation(len(shuffled))
            if MODEL=='LSTM':shuffled[:,:,j]=shuffled[order,:,j]
            else:shuffled.iloc[:,j]=shuffled.iloc[order,j].to_numpy()
            score=metrics(d['y']['validation'],predict(item['model'],shuffled,MODEL,d['ys']))['MAE']
            differences.append(score-item['score']['MAE'])
        importance.append({'feature':feature,'MAE_increase':np.mean(differences),'std':np.std(differences)})
    imp=pd.DataFrame(importance).sort_values('MAE_increase',ascending=False)
    imp.to_csv(OUT/f'{MODEL}_{method}_importance.csv',index=False)
    display(imp)
    top=imp.head(12).sort_values('MAE_increase')
    fig,ax=plt.subplots(figsize=(9,4));ax.barh(top.feature,top.MAE_increase,xerr=top['std'])
    ax.set(xlabel='Kenaikan MAE validasi kg',title=f'Pengaruh fitur {MODEL} {method}')
    fig.tight_layout();display(fig);plt.close(fig)
"""),
           md('## Langkah 11 Menyimpan model bersama preprocessing\nModel saja tidak cukup. Kategori, median, batas outlier, skala, dan urutan fitur harus sama saat digunakan kembali. Model lama milik tim tidak ditimpa: artefak baru memakai nama model/metode tersendiri di folder models/best_model yang sudah ada. Integrasi ke API merupakan langkah terpisah.'),
           code("""for method,item in selected.items():
    label=f'{MODEL}_{method}'
    if MODEL=='LSTM':item['model'].save(ART/f'{label}.keras')
    else:joblib.dump(item['model'],ART/f'{label}.joblib')
    joblib.dump({'preprocessor':data[method]['prep'],'target_scaler':data[method]['ys'],'window':WINDOW,'name':MODEL},ART/f'{label}_preprocessing.joblib')
    print('Tersimpan:',label)
"""),
           md('## Langkah 12 Menulis insight dari angka yang benar-benar diperoleh\nKesimpulan berikut berubah mengikuti hasil. MAE test tidak dipakai memilih pemenang. Robust bisa lebih buruk jika clipping menghilangkan nilai ekstrem yang sebenarnya bermakna. Satu split/seed tidak membuktikan keunggulan universal. Setelah notebook model selesai, buka notebook 08 untuk perbandingan delapan eksperimen.'),
           code("""a=hasil.set_index('preprocessing').loc['standard'];b=hasil.set_index('preprocessing').loc['robust']
delta=a.validation_MAE-b.validation_MAE
display(Markdown(f'**Dampak Robust pada validasi:** MAE berubah dari {a.validation_MAE:.3f} menjadi {b.validation_MAE:.3f} kg. Selisih Standard − Robust = {delta:.3f} kg. Positif berarti Robust lebih baik.'))
baseline_value=float(df.loc[idx['train'],TARGET].median())
baseline_mae=metrics(df.loc[idx['test'],TARGET].to_numpy(),np.full(len(idx['test']),baseline_value))['MAE']
for _,r in hasil.iterrows():
    improvement=(baseline_mae-r.test_MAE)/baseline_mae*100
    display(Markdown(f\"**{r.preprocessing}:** training MAE {r.train_MAE:.3f} kg, validasi {r.validation_MAE:.3f} kg, test {r.test_MAE:.3f} kg. Selisih validasi − training {r.validation_MAE-r.train_MAE:.3f} kg. R² test {r.test_R2:.3f}. Pengurangan error dibanding tebakan median training pada test {improvement:.1f}%.\"))
display(Markdown('Gunakan tabel error terbesar dan grafik residual untuk menjelaskan kelemahan model. Jangan mengubah parameter berdasarkan kasus test lalu tetap menyebut hasil test tersebut evaluasi independen.'))
""")]
    cells.extend([md('## Langkah 13 Membuka kembali artefak untuk melanjutkan pekerjaan\nContoh ini memeriksa model tersimpan pada lima observasi test yang sama, bukan pengujian baru. Jika prediksinya sama, pasangan model/preprocessing dapat dibuka kembali tanpa training. Saat dipakai pada input baru, urutan kolom dan asumsi ketersediaan fitur harus tetap sama. Model LSTM membutuhkan konteks, bukan hanya satu baris.'),
    code("""for method in ['standard','robust']:
    label=f'{MODEL}_{method}'
    bundle=joblib.load(ART/f'{label}_preprocessing.joblib')
    if MODEL=='LSTM':
        import tensorflow as tf
        loaded=tf.keras.models.load_model(ART/f'{label}.keras',compile=False)
        encoded=bundle['preprocessor'].transform(df,scaled=True)
        sample=sequence(encoded,idx['test'][:5])
    else:
        loaded=joblib.load(ART/f'{label}.joblib')
        transformed=bundle['preprocessor'].native(df) if MODEL=='CatBoost' else bundle['preprocessor'].transform(df)
        sample=transformed.iloc[idx['test'][:5]]
    restored=predict(loaded,sample,MODEL,bundle['target_scaler'])
    saved=pd.read_csv(OUT/f'{label}_test_predictions.csv').prediction.iloc[:5].to_numpy()
    np.testing.assert_allclose(restored,saved,rtol=1e-5,atol=1e-5)
    display(pd.DataFrame({'prediksi_tersimpan':saved,'prediksi_setelah_dibuka':restored}))
    print(method,': LULUS, model dapat dibuka kembali')
""")])
    if name=='LSTM':
        cells.extend([md('## Memahami gradien dan keterbatasan sequence LSTM\nAdam menggunakan gradien untuk menyesuaikan bobot. Bentuk gradient descent sederhana: bobot baru = bobot lama − learning rate × gradien. Grafik di bawah menunjukkan norma gradien MSE mentah sebelum clipping, pada target terskala dan batch training tetap setiap akhir epoch; bukan kilogram dan tidak harus turun terus. Epoch adalah satu kali model melewati seluruh data latihan. Batch adalah kelompok kecil data untuk pembaruan bobot.\n\nJendela 7 observasi termasuk input operasional target. Tidak ada label aktual dalam jendela. Karena tanggal tidak selalu harian dan tidak ada ID restoran, hasil ini bukan bukti peramalan tujuh hari. Model mungkin memanfaatkan terutama input porsi saat ini, sehingga keunggulan temporal belum terbukti.'),code("for method in ['standard','robust']:\n    display(Image(filename=str(OUT/f'LSTM_{method}_gradient.png')))\n    display(selected[method]['curve'].tail(10))")])
    return cells
