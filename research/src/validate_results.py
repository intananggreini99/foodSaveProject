"""Periksa kesetaraan data, metrik, dan artefak sebelum menyerahkan hasil."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import numpy as np
import pandas as pd
import joblib
from src.experiment import OUT, ART, prepare, metrics, sequence, predict, FoodPreprocessor

table=pd.read_csv(OUT/'experiment_results.csv')
assert len(table)==8 and not table[['model','preprocessing']].duplicated().any()
assert np.isfinite(table.select_dtypes('number').to_numpy()).all()
best=json.loads((OUT/'best_model.json').read_text())
winner=table.sort_values(['validation_MAE','validation_RMSE','validation_ms_per_row']).iloc[0]
assert (winner.model,winner.preprocessing)==(best['model'],best['preprocessing'])
reference=None
for _,row in table.iterrows():
    label=f'{row.model}_{row.preprocessing}'
    df,prep,idx,ys,x,xs,native=prepare(row.preprocessing)
    pred=pd.read_csv(OUT/f'{label}_test_predictions.csv')
    if reference is None: reference=pred[['row','actual']]
    else: pd.testing.assert_frame_equal(reference,pred[['row','actual']])
    for split in ['train','validation','test']:
        p=pd.read_csv(OUT/f'{label}_{split}_predictions.csv')
        for metric,value in metrics(p.actual.to_numpy(),p.prediction.to_numpy()).items():
            assert np.isclose(value,row[f'{split}_{metric}']), (label,split,metric)
    bundle=joblib.load(ART/f'{label}_preprocessing.joblib')
    pd.testing.assert_frame_equal(prep.transform(df),bundle['preprocessor'].transform(df))
    if row.model=='LSTM':
        import tensorflow as tf
        model=tf.keras.models.load_model(ART/f'{label}.keras')
        features=sequence(xs,idx['test'])
    else:
        model=joblib.load(ART/f'{label}.joblib')
        features=(native if row.model=='CatBoost' else x).iloc[idx['test']]
    actual=predict(model,features,row.model,bundle['target_scaler'])
    np.testing.assert_allclose(actual,pred.prediction,rtol=1e-5,atol=1e-5)
    # Target heldout tidak memengaruhi fitur atau nilai hasil transform.
    changed=df.copy(); changed.loc[changed.split!='train','food_waste_kg']=9999999
    pd.testing.assert_frame_equal(prep.transform(df),prep.transform(changed))
    assert np.isfinite(x.to_numpy()).all()
    assert not set(['ID','food_waste_kg','waste_category','past_waste_kg']).intersection(x.columns)
    print('LULUS',label,flush=True)
assert table.n_test.nunique()==1 and table.n_validation.nunique()==1
save={'status':'passed','experiments':8,'checks':['same_holdout_rows','metrics_recomputed','saved_model_roundtrip','no_target_in_features','heldout_targets_do_not_change_features','finite_features','winner_uses_validation']}
(OUT/'verification.json').write_text(json.dumps(save,indent=2),encoding='utf-8')
print('Semua pemeriksaan hasil lulus.')
