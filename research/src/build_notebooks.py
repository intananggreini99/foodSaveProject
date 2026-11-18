"""Bangun notebook berbahasa Indonesia; jalankan ulang hanya untuk memperbarui template."""
from pathlib import Path
import json
from build_model_cells import model_cells

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / 'notebooks'
NOTEBOOKS.mkdir(parents=True, exist_ok=True)


def md(text):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': text.splitlines(keepends=True)}


def code(text):
    return {'cell_type': 'code', 'metadata': {}, 'source': text.splitlines(keepends=True), 'execution_count': None, 'outputs': []}


SETUP = """from pathlib import Path
import sys
ROOT = Path.cwd().resolve()
while not (ROOT / 'src/experiment.py').exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
assert (ROOT / 'src/experiment.py').exists(), 'Buka notebook dari folder proyek FoodSave.'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import json
import numpy as np
import pandas as pd
from IPython.display import display, Image, Markdown, Code
from src.experiment import OUT, ART, load_data, prepare, run_model, evaluate
pd.set_option('display.max_columns', 40)
pd.set_option('display.precision', 4)
get_ipython().run_line_magic('matplotlib', 'inline')
"""


def write(name, cells):
    path = NOTEBOOKS/name
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'cells': []}
    retained = [c for c in previous['cells'] if not c.get('metadata', {}).get('foodsave_added')]
    for i,c in enumerate(retained):
        c.setdefault('id',f'foodsave-legacy-{i:03d}')
        if c['cell_type']=='code':
            tags=c.setdefault('metadata',{}).setdefault('tags',[])
            if 'foodsave-legacy' not in tags: tags.append('foodsave-legacy')
    if retained:
        cells = [md('## Tambahan eksperimen lengkap\n\nKode awal milik tim di atas tetap dipertahankan tanpa penghapusan. Bagian di bawah menyediakan alur tambahan yang dapat dijalankan mulai dari sel setup hingga akhir, tanpa menjalankan ulang sel lama. Hasil alur lama tidak dicampur karena pembagian data dan asumsi fiturnya berbeda. Script eksekusi otomatis melewati sel referensi lama bertag `foodsave-legacy`.')] + cells
    notebook = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python (FoodSave)', 'language': 'python', 'name': 'foodsave'},
                'language_info': {'name': 'python', 'version': '3.12'}}, 'nbformat': 4, 'nbformat_minor': 5}
    for i, cell in enumerate(cells):
        cell['id'] = f'foodsave-added-{i:03d}'
        cell['metadata']['foodsave_added']=True
    if retained:
        guide=md('# Petunjuk menjalankan notebook yang dilengkapi\n\nSel awal tim tetap utuh sebagai alur sebelumnya. Untuk menjalankan delapan eksperimen dengan pembagian data dan metrik seragam, buka bagian **Tambahan eksperimen lengkap** setelah sel awal, lalu jalankan mulai dari sel setup bagian tersebut sampai akhir. Setiap langkah tambahan menjelaskan tujuan kode dan cara membaca hasilnya. Script `python src/execute_notebooks.py` menjalankan bagian tambahan secara otomatis.')
        guide['metadata']['foodsave_added']=True
        guide['id']='foodsave-guide'
        notebook['cells']=[guide]+retained+cells
    else:
        notebook['cells']=cells
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding='utf-8')


write('01_data_understanding.ipynb', [
    md('# 01 Memahami data FoodSave\n\n**Tujuan:** mengenali isi data restoran sebelum membuat prediksi limbah makanan dalam kilogram. Satu baris adalah satu observasi, belum tentu satu restoran atau satu hari unik. Dataset diambil dari ZIP yang diberikan pengguna. File `submission.csv` bukan sumber label tambahan; test Kaggle tidak digunakan sebagai holdout penelitian.'),
    code(SETUP),
    md('## Membaca data asli\nKode berikut menampilkan contoh baris, tipe kolom, dan jumlah nilai yang belum terisi. Kolom ID hanya penanda, bukan faktor penyebab limbah.'),
    code("raw = pd.read_csv(ROOT/'dataset/raw/train.csv')\ndisplay(raw.head(10))\ndisplay(pd.DataFrame({'tipe': raw.dtypes.astype(str), 'kosong': raw.isna().sum(), 'unik': raw.nunique()}))\ndisplay(raw.describe(include='all').T)"),
    md('## Memeriksa tanggal dan duplikat\nObservasi bertanggal sama ditempatkan pada partisi yang sama. Duplikat persis tanpa ID dibuang untuk seluruh eksperimen agar salinan baris tidak membuat hasil terlalu optimistis. Baris bertarget kosong atau bertanggal tidak valid tidak boleh dilatih.'),
    code("df = load_data()\naudit = json.loads((OUT/'data_audit.json').read_text(encoding='utf-8'))\ndisplay(audit)\ndisplay(df.groupby('split').agg(jumlah=('date','size'), mulai=('date','min'), akhir=('date','max')))\nprint('Tanggal unik:', df.date.nunique(), 'Observasi:', len(df))"),
    md('## Fitur yang tersedia saat perencanaan\nModel memakai jumlah porsi, staf, suhu, kelembapan, acara khusus, pengalaman staf, dan fitur kalender/rasio. `waste_category` dikeluarkan karena mungkin baru diketahui setelah limbah dihasilkan. `past_waste_kg` dikeluarkan karena asal periode/restorannya belum terverifikasi. `day_of_week` dihitung ulang dari tanggal. Suhu dan kelembapan harus berupa perkiraan yang sudah tersedia saat membuat rencana.\n\n**Batasan:** data ini belum membuktikan hubungan sebab-akibat atau pola satu restoran. Jangan menyebut hasilnya jaminan pengurangan limbah.')])

write('02_eda.ipynb', [md('# 02 Menjelajahi pola dan kualitas data\n\n**Tujuan:** melihat distribusi limbah, format data bermasalah, dan hubungan antarvariabel. EDA yang memengaruhi keputusan model menggunakan training saja. Data validasi/test tetap tersimpan untuk evaluasi.'),code(SETUP),
    code("import matplotlib.pyplot as plt\ndf=load_data()\ntrain=df[df.split=='train'].copy()\ndisplay(train.head())\ndisplay(train.isna().sum().to_frame('jumlah kosong'))"),
    md('## Distribusi limbah dan urutan tanggal\nHistogram menunjukkan jumlah kemunculan tiap rentang limbah. Grafik waktu memperlihatkan rata-rata observasi per tanggal, bukan total limbah seluruh restoran.'),
    code("fig, axes=plt.subplots(1,2,figsize=(12,4))\naxes[0].hist(train.food_waste_kg,bins=30); axes[0].set(xlabel='Limbah (kg)',ylabel='Jumlah observasi',title='Distribusi target training')\ntrain.groupby('date').food_waste_kg.mean().plot(ax=axes[1],title='Rata-rata limbah per tanggal training')\nfig.tight_layout(); display(fig); plt.close(fig)"),
    md('## Contoh variasi format dan korelasi\nKorelasi hanya hubungan statistik. Korelasi tinggi tidak membuktikan bahwa mengubah satu input pasti mengubah limbah.'),
    code("for col in ['meals_served','kitchen_staff','staff_experience','waste_category']:\n    print(col, ':', train[col].astype(str).unique()[:20])\nnumeric=train.select_dtypes(include='number').drop(columns=['ID','_row'],errors='ignore')\ndisplay(numeric.corr().round(3))")])

write('03_Standard_Robust_Preprocessing.ipynb', [md('# 03 Menyiapkan data Standard dan Robust\n\n**Tujuan:** membandingkan dua cara membersihkan data pada pembagian waktu yang sama. Training memakai sekitar 60% tanggal awal, validasi 20% berikutnya, dan test 20% terakhir. Persentase jumlah baris dapat berbeda karena tanggal tidak dipisah.'), code(SETUP),
    md('## Perbedaan pendekatan\n\n| Langkah | Standard | Robust |\n|---|---|---|\n| Konversi angka | Konversi sederhana | Bersihkan simbol, koma pemisah ribuan, dan spasi |\n| Kategori | Pertahankan penulisan | Huruf kecil dan pangkas spasi |\n| Nilai kosong | Median/modus training | Median/modus training |\n| Nilai ekstrem fitur | Dipertahankan | Batasi dengan IQR training |\n| Skala LSTM | StandardScaler | RobustScaler |\n| Target aktual | Tidak diubah | Tidak diubah |\n\nDuplikat persis dihapus untuk kedua pendekatan sebelum split demi menjaga identitas observasi. Batas IQR yang dipelajari dari training diterapkan juga ke validasi/test; **target validasi/test tidak dipotong**. Model pohon tidak memerlukan scaling. CatBoost menerima kategori asli setelah pembersihan; model lainnya memakai one-hot encoding.'),
    code("audit_rows=[]\nfor method in ['standard','robust']:\n    df, prep, idx, ys, x, xs, native=prepare(method)\n    assert np.isfinite(x.to_numpy()).all() and np.isfinite(xs).all()\n    assert not set(['ID','waste_category','past_waste_kg','food_waste_kg']).intersection(x.columns)\n    for split, ix in idx.items():\n        folder=ROOT/'dataset/processed'; folder.mkdir(parents=True,exist_ok=True)\n        x.iloc[ix].to_csv(folder/f'validated_{method}_{split}_features.csv',index=False)\n        df.iloc[ix][['_row','date','food_waste_kg']].to_csv(folder/f'validated_{method}_{split}_target.csv',index=False)\n    audit_rows.append({'metode':method,'fitur':x.shape[1], **{s:len(ix) for s,ix in idx.items()},'missing_setelah':int(x.isna().sum().sum())})\n    display(Markdown(f'### Contoh hasil {method}')); display(native.head())\n    display(prep.bounds)\ndisplay(pd.DataFrame(audit_rows))"),
    md('## Memahami fitur turunan dan sequence\n`staff_per_portion` adalah staf dibagi jumlah porsi, `portion_per_staff` adalah porsi per staf, dan `special_event_portion` adalah interaksi acara dengan porsi. Bulan diubah ke sinus/kosinus agar Desember dekat dengan Januari.\n\nLSTM memakai jendela **7 observasi**, termasuk input operasional hari yang hendak direncanakan. Ini bukan jaminan 7 hari berurutan. Tidak ada target aktual yang dimasukkan ke jendela. Konteks validasi/test boleh berisi fitur observasi sebelumnya, tanpa mengambil label atau baris masa depan. Enam baris awal dihilangkan dari evaluasi semua model agar perbandingannya setara.'),
    code("import inspect\nfrom src.experiment import FoodPreprocessor, sequence\ndisplay(Code(inspect.getsource(FoodPreprocessor),language='python'))\ndisplay(Code(inspect.getsource(sequence),language='python'))")])

models = [('04_lstm_model.ipynb','LSTM','LSTM membaca urutan fitur operasional untuk menemukan pola. Adam memperbarui bobot menggunakan gradien, yaitu arah perubahan error. Target diskalakan dari training agar pelatihan stabil, lalu hasil dikembalikan ke kilogram. Dua kandidat: 24 unit dengan learning rate 0,001 dan 48 unit dengan learning rate 0,003. Pelatihan maksimal 160 epoch dan berhenti jika error validasi tidak membaik selama 20 epoch.'),
('05_random_forest_model.ipynb','RandomForest','Random Forest menggabungkan prediksi banyak pohon keputusan. Setiap pohon mempelajari aturan seperti pembagian jumlah porsi. Kandidat membandingkan kedalaman tak dibatasi/10 dan minimal isi daun 1/3. Jumlah pohon bertambah 20, 60, 120, 200 untuk memperlihatkan kestabilan error. Model ini tidak memakai gradient descent.'),
('06_xgboost_model.ipynb','XGBoost','XGBoost menambah pohon secara bertahap untuk memperbaiki kesalahan model sebelumnya. Dua kandidat memakai kedalaman 3/5 dengan regularisasi 5/10. Learning rate 0,04, maksimal 500 tahap, dan early stopping 40 tahap. Gradient boosting memakai gradien loss untuk menyusun pohon baru; prosesnya berbeda dari pembaruan bobot jaringan saraf.'),
('07_catboost_model.ipynb','CatBoost','CatBoost adalah gradient boosting yang mendukung kategori teks secara langsung. Kolom pengalaman staf diberikan melalui cat_features. Dua kandidat memakai kedalaman 4/6 dengan regularisasi 5/10. Learning rate 0,04, maksimal 500 tahap, early stopping 40 tahap. Kurva menunjukkan error training/validasi setiap tahap boosting.')]
for filename,name,description in models:
    write(filename,model_cells(name, description, md, code, SETUP))

write('08_model_evaluation.ipynb', [md('# 08 Perbandingan delapan eksperimen dan pemilihan model terbaik\n\n**Tujuan:** menggabungkan seluruh hasil, memilih model berdasarkan validasi, menjelaskan metrik akhir dan keterbatasannya. Jalankan notebook 04–07 terlebih dahulu. Pemenang adalah MAE validasi terkecil; jika seri, gunakan RMSE validasi lalu latensi validasi. Test tidak dipakai untuk mengubah keputusan.'),code(SETUP),
    code("hasil=evaluate()\ndisplay(hasil[['validation_rank','model','preprocessing','validation_MAE','validation_RMSE','validation_R2','test_MAE','test_RMSE','test_R2','test_MedAE','test_Bias','test_WAPE_percent','train_time_s','tuning_total_time_s','test_ms_per_row']])\nbest=json.loads((OUT/'best_model.json').read_text(encoding='utf-8'))\ndisplay(best)"),
    md('## Perbandingan seluruh metrik\nR² yang lebih tinggi lebih baik; MAE, RMSE, dan waktu yang lebih rendah lebih baik. Bias ideal mendekati nol. Pemenang validasi belum tentu memiliki MAE test terkecil karena data test berasal dari periode berbeda.'),
    code("display(Image(filename=str(OUT/'comparison_metrics.png')))\ndisplay(json.loads((OUT/'baseline_metrics.json').read_text()))"),
    md('## Pengaruh preprocessing\nAngka positif pada tabel berikut berarti Robust mengurangi error dibanding Standard. Peningkatan tidak dijamin; pemotongan outlier bisa membuang sinyal yang benar-benar penting.'),
    code("pivot=hasil.pivot(index='model',columns='preprocessing',values=['validation_MAE','test_MAE'])\ndelta=pd.DataFrame({'pengurangan_MAE_validasi_kg':pivot['validation_MAE']['standard']-pivot['validation_MAE']['robust'], 'pengurangan_MAE_test_kg':pivot['test_MAE']['standard']-pivot['test_MAE']['robust']})\ndisplay(delta)"),
    md('## Diagnostik model terpilih\nTitik dekat garis diagonal berarti prediksi mendekati kenyataan. Residual positif berarti model meremehkan limbah. Kesalahan besar perlu diperiksa agar rata-rata metrik tidak menutupi kasus sulit.'),
    code("display(Image(filename=str(OUT/'best_model_diagnostics.png')))\ndisplay(Image(filename=str(OUT/'best_model_importance.png')))\nlabel=f\"{best['model']}_{best['preprocessing']}\"\npred=pd.read_csv(OUT/f'{label}_test_predictions.csv')\ndisplay(pred.assign(error_absolut=pred.residual.abs()).nlargest(15,'error_absolut'))"),
    md('## Rentang estimasi dan risiko\nRadius interval dihitung dari persentil 90% error absolut validasi. Coverage test dilaporkan apa adanya. Karena validasi juga digunakan memilih model, interval ini bersifat empiris/eksploratif dan tidak menjamin coverage 90%. Batas risiko menggunakan kuantil training, belum menjadi batas operasional restoran yang disepakati.'),
    code("display(pd.DataFrame([{'radius_interval_kg':best['empirical_90_percent_interval_radius_kg'], 'cakupan_test':best['test_interval_coverage'], 'batas_risiko_kg':best['risk_thresholds_train_kg']}]))"),
    md('## Batasan dan cara mengulang\nHasil berasal dari satu pembagian kronologis dan satu seed. Pencarian parameter terbatas dua kandidat per eksperimen; model terbaik berarti terbaik dalam rancangan ini, bukan terbaik untuk semua kondisi. Data belum memiliki ID restoran dan observasi tidak selalu harian. LSTM adalah eksperimen urutan observasi, bukan bukti kemampuan meramal tujuh hari. Fitur operasional target diasumsikan tersedia saat perencanaan. Suhu/kelembapan aktual yang belum diketahui harus diganti perkiraan. Semua model memakai fitur aman tanpa waste_category/past_waste_kg.\n\nJalankan ulang melalui `python -m src.experiment --model all`. Menjalankan notebook model akan melatih ulang dan memperbarui hasil. Jalankan kembali evaluasi dan laporan setelah hasil berubah. Jangan mengubah model berdasarkan test lalu tetap menyebut test tersebut evaluasi independen.')])

def extend(name, extra):
    path=NOTEBOOKS/name
    nb=json.loads(path.read_text(encoding='utf-8'))
    for i,c in enumerate(extra):
        c['id']=f'foodsave-insight-{i:03d}'
        c['metadata']['foodsave_added']=True
    nb['cells'].extend(extra)
    path.write_text(json.dumps(nb,indent=1,ensure_ascii=False),encoding='utf-8')

extend('01_data_understanding.ipynb',[
    md('## Langkah tambahan 1 Kamus kolom untuk pembaca awam\nKamus ini membedakan angka yang ingin diprediksi, calon input, dan penanda. Nama kolom mengikuti file yang benar-benar tersedia, tanpa menambahkan variabel restoran buatan.'),
    code("""kamus = {
'ID':'Penanda baris; bukan input model.', 'date':'Tanggal observasi; dipakai mengurutkan waktu dan membuat kalender.',
'meals_served':'Jumlah porsi; diasumsikan diketahui saat perencanaan.', 'kitchen_staff':'Jumlah staf dapur.',
'temperature_C':'Suhu Celsius; harus berupa perkiraan jika nilai aktual belum diketahui.',
'humidity_percent':'Kelembapan persen; asumsi ketersediaan sama dengan suhu.',
'day_of_week':'Hari yang tercatat; model menghitung ulang dari tanggal.', 'special_event':'Penanda acara khusus.',
'past_waste_kg':'Limbah sebelumnya; dikeluarkan sampai asal periode/restoran jelas.',
'staff_experience':'Tingkat pengalaman staf, kategori teks.', 'waste_category':'Kategori limbah; dikeluarkan karena mungkin baru diketahui setelah limbah terjadi.',
'food_waste_kg':'Target: jumlah limbah dalam kilogram.'}
display(pd.DataFrame({'kolom':list(kamus),'arti':list(kamus.values())}))
"""),
    md('## Langkah tambahan 2 Memeriksa isi file test Kaggle\nNama test pada arsip tidak otomatis berarti holdout independen penelitian. Kode berikut memeriksa tumpang tindih ID dan tanggal. Kita tetap membuat test kronologis dari data berlabel agar metrik dapat dihitung dengan target yang benar. Submission bukan sumber observasi tambahan.'),
    code("""kaggle_test=pd.read_csv(ROOT/'dataset/raw/test.csv')
print('Ukuran train asli:',raw.shape,'| test Kaggle:',kaggle_test.shape)
print('Target tersedia di test Kaggle:', 'food_waste_kg' in kaggle_test)
shared=raw[['ID','date']].merge(kaggle_test[['ID','date']],on=['ID','date']).drop_duplicates()
print('Pasangan ID/tanggal yang juga muncul di train:',len(shared))
if len(shared):print('Ada tumpang tindih; jangan menganggap kedua file sebagai dua sumber independen.')
"""),
    md('## Langkah tambahan 3 Menemukan duplikat dan format angka\nDuplikat persis diperiksa tanpa ID karena salinan observasi bisa diberi ID baru. Nilai ekstrem tidak otomatis salah; yang diperiksa terlebih dahulu adalah format dan konteksnya. Konversi angka yang gagal akan menjadi kosong dan nantinya diimputasi dari training.'),
    code("""keys=[c for c in raw if c!='ID']
display(raw.loc[raw.duplicated(keys,keep=False)].head(10))
conversion=[]
for col in ['meals_served','kitchen_staff','temperature_C','humidity_percent']:
    s=pd.to_numeric(raw[col],errors='coerce')
    conversion.append({'kolom':col,'kosong_asli':int(raw[col].isna().sum()),'gagal_konversi_tambahan':int((s.isna() & raw[col].notna()).sum()),'minimum_terbaca':s.min(),'maksimum_terbaca':s.max()})
display(pd.DataFrame(conversion))
"""),
    md('## Langkah tambahan 4 Memeriksa apakah data benar-benar harian\nLSTM membutuhkan urutan yang bermakna. Beberapa baris pada tanggal yang sama atau jarak tanggal yang tidak selalu satu hari membatasi klaim temporal. Dataset tidak memiliki ID restoran; kita tidak boleh mengarang identitas restoran untuk membentuk seri.'),
    code("""counts=df.groupby('date').size()
dates=df.date.drop_duplicates().sort_values()
gaps=dates.diff().dt.days.dropna()
display(counts.describe().to_frame('observasi per tanggal'))
display(gaps.value_counts().sort_index().to_frame('frekuensi jarak hari'))
print('Tanggal dengan lebih dari satu observasi:',int((counts>1).sum()))
print('Kolom ID restoran tersedia:',any(c.lower() in ['restaurant_id','restoran_id'] for c in raw.columns))
"""),
    md('## Insight data understanding dari hasil aktual'),
    code("""display(Markdown(f'Data berlabel memiliki **{len(raw)} baris awal** dan **{len(df)} observasi setelah audit**. Terdapat **{df.date.nunique()} tanggal unik**. Sebanyak **{int((counts>1).sum())} tanggal memiliki lebih dari satu observasi**. Karena itu, satu baris tidak boleh otomatis disebut satu hari restoran.'))
display(Markdown('Langkah berikutnya adalah EDA training. Jangan menggunakan test untuk memilih fitur, mengubah batas outlier, atau mencoba parameter berulang kali.'))
""")])

extend('02_eda.ipynb',[
    md('## Langkah tambahan 1 Membersihkan salinan training untuk eksplorasi\nSalinan ini hanya membantu membaca pola. Pipeline pemodelan tetap dipasang ulang pada training dan tidak mengambil statistik dari test. Pada scatter, satu titik mewakili satu observasi, bukan satu restoran terverifikasi.'),
    code("""from src.experiment import FoodPreprocessor
prep=FoodPreprocessor('robust').fit(train)
view=prep.native(train)
view['food_waste_kg']=train.food_waste_kg.to_numpy()
view['date']=train.date.to_numpy()
fig,axes=plt.subplots(1,3,figsize=(15,4))
for ax,col in zip(axes,['meals_served','kitchen_staff','temperature_C']):
    ax.scatter(view[col],view.food_waste_kg,alpha=.5,s=14)
    ax.set(xlabel=col,ylabel='Limbah kg',title=f'Hubungan {col} dan limbah')
fig.tight_layout();display(fig);plt.close(fig)
"""),
    md('## Langkah tambahan 2 Membaca hubungan angka secara hati-hati\nKoefisien korelasi dekat +1 berarti dua variabel cenderung naik bersama, dekat −1 bergerak berlawanan, dan dekat 0 tidak menunjukkan hubungan linear kuat. Korelasi bisa dipengaruhi outlier atau hubungan fitur turunan; ini bukan bukti sebab-akibat. Tabel berikut menghindari ID sebagai fitur.'),
    code("""corr=view.select_dtypes(include='number').corr()
display(corr.food_waste_kg.drop('food_waste_kg').sort_values(ascending=False).to_frame('korelasi_dengan_target'))
fig,ax=plt.subplots(figsize=(10,8));im=ax.imshow(corr,vmin=-1,vmax=1,cmap='coolwarm')
ax.set_xticks(range(len(corr)),corr.columns,rotation=90);ax.set_yticks(range(len(corr)),corr.columns)
fig.colorbar(im,ax=ax,label='Korelasi');fig.tight_layout();display(fig);plt.close(fig)
"""),
    md('## Langkah tambahan 3 Acara khusus dan pengalaman staf\nRata-rata kelompok dapat berbeda karena jumlah porsi atau kondisi lain juga berbeda. Bandingkan jumlah observasi, median, dan variasi, bukan hanya rata-rata. Tidak ada uji kausal pada analisis ini.'),
    code("""for col in ['special_event','staff_experience']:
    display(view.groupby(col).food_waste_kg.agg(['count','mean','median','std']).round(3))
    groups=list(view.groupby(col))
    fig,ax=plt.subplots(figsize=(7,4))
    ax.boxplot([g.food_waste_kg.to_numpy() for _,g in groups],tick_labels=[str(k) for k,_ in groups])
    ax.set(xlabel=col,ylabel='Limbah kg',title=f'Distribusi limbah menurut {col}')
    fig.tight_layout();display(fig);plt.close(fig)
"""),
    md('## Langkah tambahan 4 Menilai outlier tanpa membuang target\nIQR adalah rentang antara kuartil 25% dan 75%. Nilai di luar Q1 − 1,5 IQR atau Q3 + 1,5 IQR ditandai ekstrem secara statistik. Ekstrem bukan berarti pasti salah. Tabel target hanya untuk diagnosis; target training/validasi/test tidak di-clipping oleh eksperimen.'),
    code("""outliers=[]
for col in ['meals_served','kitchen_staff','temperature_C','humidity_percent','food_waste_kg']:
    s=pd.to_numeric(train[col],errors='coerce');q1,q3=s.quantile([.25,.75]);iqr=q3-q1
    low,high=q1-1.5*iqr,q3+1.5*iqr
    outliers.append({'kolom':col,'batas_bawah':low,'batas_atas':high,'jumlah_ekstrem':int(((s<low)|(s>high)).sum())})
display(pd.DataFrame(outliers))
"""),
    md('## Langkah tambahan 5 Variasi kalender dan perubahan di dalam training\nKita membandingkan dua bagian training untuk melihat indikasi perubahan distribusi tanpa mengintip test. Pola kalender tidak boleh disebut pola satu restoran karena identitas restoran belum tersedia. Bulan dengan data sedikit dapat menghasilkan rata-rata yang tidak stabil.'),
    code("""calendar=train.assign(hari=train.date.dt.dayofweek,bulan=train.date.dt.month)
display(calendar.groupby('hari').food_waste_kg.agg(['count','mean','median']))
display(calendar.groupby('bulan').food_waste_kg.agg(['count','mean','median']))
middle=len(view)//2
display(pd.DataFrame({'median_training_awal':view.iloc[:middle].select_dtypes('number').median(),'median_training_akhir':view.iloc[middle:].select_dtypes('number').median()}))
"""),
    md('## Insight EDA dan konsekuensi untuk pemodelan'),
    code("""top=corr.food_waste_kg.drop('food_waste_kg').abs().sort_values(ascending=False).head(3)
display(Markdown('Tiga hubungan linear terkuat pada salinan training: '+', '.join(f'**{k}** (|r|={v:.3f})' for k,v in top.items())+'. Hubungan ini perlu diuji melalui model dan tidak membuktikan pengaruh kausal.'))
display(Markdown('Nilai ekstrem tetap diuji secara jujur: Standard mempertahankan fitur ekstrem, Robust membatasi fitur memakai IQR training. Target evaluasi tetap aktual. Kita belum menyimpulkan Robust lebih baik sampai metrik validasi dihitung.'))
""")])

extend('03_Standard_Robust_Preprocessing.ipynb',[
    md('## Audit tambahan sebelum dan sesudah pembersihan\nTabel berikut menampilkan contoh mentah dan hasil pembersihan tanpa mengganti file processed lama. Kolom `validated_` dipakai untuk keluaran tambahan. Semua input akhir harus finite, urutan fitur sama antarpartisi, dan target tetap sama untuk kedua pendekatan.'),
    code("""df=load_data()
summary=[]
for method in ['standard','robust']:
    prep=FoodPreprocessor(method).fit(df[df.split=='train'])
    cleaned=prep.native(df)
    display(Markdown(f'### {method}'))
    display(pd.concat([df[['meals_served','kitchen_staff','staff_experience']].head(8).add_prefix('asli_'),cleaned[['meals_served','kitchen_staff','staff_experience']].head(8).add_prefix('hasil_')],axis=1))
    transformed=prep.transform(df)
    for split in ['train','validation','test']:
        part=transformed.loc[df.split==split]
        summary.append({'metode':method,'partisi':split,'baris':len(part),'fitur':part.shape[1],'kosong':int(part.isna().sum().sum()),'finite':bool(np.isfinite(part.to_numpy()).all())})
display(pd.DataFrame(summary))
"""),
    md('## Menguji bahwa perubahan target masa depan tidak mengubah fitur\nTes berikut menyalin data lalu mengganti seluruh label validasi/test dengan angka sembarang. Hasil fitur harus tetap sama. Jika berubah, target bocor ke pipeline. Ini pemeriksaan kode; bukan bukti bahwa semua calon fitur pasti tersedia saat operasional.'),
    code("""changed=df.copy();changed.loc[changed.split!='train','food_waste_kg']=9999999
for method in ['standard','robust']:
    prep=FoodPreprocessor(method).fit(df[df.split=='train'])
    pd.testing.assert_frame_equal(prep.transform(df),prep.transform(changed))
    print(method,': LULUS, target masa depan tidak memengaruhi fitur')
""")])

extend('08_model_evaluation.ipynb',[
    md('## Pemeriksaan kesetaraan target delapan eksperimen\nPerbandingan yang adil memerlukan baris test dan label aktual yang identik, bukan sekadar jumlah baris sama. Sel berikut memeriksa identitas baris, menghitung ulang metrik, dan menolak nilai tidak finite.'),
    code("""from src.experiment import metrics
reference=None
for _,r in hasil.iterrows():
    label=f'{r.model}_{r.preprocessing}'
    p=pd.read_csv(OUT/f'{label}_test_predictions.csv')
    if reference is None:reference=p[['row','actual']]
    else:pd.testing.assert_frame_equal(reference,p[['row','actual']])
    for key,value in metrics(p.actual.to_numpy(),p.prediction.to_numpy()).items():
        assert np.isclose(value,r[f'test_{key}'])
assert len(hasil)==8 and np.isfinite(hasil.select_dtypes('number').to_numpy()).all()
print('LULUS: delapan eksperimen, baris test sama, dan metrik cocok dengan file prediksi.')
"""),
    md('## Kasus sulit menurut rentang target\nMetrik keseluruhan bisa menutupi prediksi buruk pada limbah besar. Batas kelompok diambil dari kuantil target training, bukan disesuaikan agar test terlihat baik. Kelompok kecil dapat menghasilkan skor yang tidak stabil.'),
    code("""df=load_data()
training=df.loc[df.split=='train','food_waste_kg']
q1,q2=training.quantile([1/3,2/3])
label=f\"{best['model']}_{best['preprocessing']}\"
p=pd.read_csv(OUT/f'{label}_test_predictions.csv')
p['kelompok']=pd.cut(p.actual,[-np.inf,q1,q2,np.inf],labels=['rendah','sedang','tinggi'])
groups=[]
for group,part in p.groupby('kelompok',observed=True):
    groups.append({'kelompok':str(group),'n':len(part),'MAE_kg':(part.actual-part.prediction).abs().mean(),'bias_kg':(part.prediction-part.actual).mean()})
display(pd.DataFrame(groups))
"""),
    md('## Membaca pemenang validasi dan pemenang test secara jujur\nKita mengunci aturan pemilihan sebelum membuka test. Pemenang test deskriptif boleh dilaporkan tetapi tidak menggantikan keputusan. Perbedaan keduanya menunjukkan bahwa hasil berubah menurut periode, bukan alasan untuk mencoba berulang kali pada test yang sama.'),
    code("""descriptive=hasil.loc[hasil.test_MAE.idxmin()]
display(Markdown(f\"**Keputusan penelitian:** {best['model']} {best['preprocessing']}, karena MAE validasi {best['validation_MAE']:.3f} kg. **MAE test model terpilih:** {best['test_MAE']:.3f} kg. **MAE test terkecil secara deskriptif:** {descriptive.model} {descriptive.preprocessing} ({descriptive.test_MAE:.3f} kg). Keputusan tetap berdasarkan validasi.\"))
gap=hasil.assign(gap_validasi_training=hasil.validation_MAE-hasil.train_MAE)
display(gap[['model','preprocessing','train_MAE','validation_MAE','test_MAE','gap_validasi_training']])
"""),
    md('## Kesalahan menurut kondisi operasional\nBatas porsi besar berasal dari persentil 95% jumlah porsi training. Data test hanya dikelompokkan untuk diagnosis, bukan menyesuaikan model. Rata-rata error kelompok kecil harus dibaca bersama jumlah observasinya. Perbedaan antara acara/tanpa acara bisa dipengaruhi faktor lain.'),
    code("""context=df[['_row','meals_served','special_event']].copy()
context['meals_served']=pd.to_numeric(context.meals_served,errors='coerce')
limit=pd.to_numeric(df.loc[df.split=='train','meals_served'],errors='coerce').quantile(.95)
operational=p.merge(context,left_on='row',right_on='_row',how='left')
operational['kategori_porsi']=np.where(operational.meals_served>limit,'di atas P95 training','sampai P95 training')
operational['error_absolut']=(operational.actual-operational.prediction).abs()
print('Batas P95 porsi training:',round(limit,2))
display(operational.groupby('kategori_porsi').error_absolut.agg(['count','mean','median','max']))
display(operational.groupby('special_event').error_absolut.agg(['count','mean','median','max']))
"""),
    md('## Kesimpulan yang dapat dipakai dalam laporan\nModel terbaik berarti terbaik pada empat model, dua preprocessing, dua kandidat per eksperimen, satu seed, dan satu split kronologis ini. Penelitian lanjutan perlu beberapa periode evaluasi bergulir, definisi restoran yang jelas, serta pemeriksaan ketersediaan fitur saat prediksi. Simulasi porsi perlu menghitung ulang fitur rasio dan interaksi. Korelasi/importance tidak membuktikan kausalitas.'),
    code("""base=json.loads((OUT/'baseline_metrics.json').read_text())
reduction=(base['test']['MAE']-best['test_MAE'])/base['test']['MAE']*100
display(Markdown(f\"Model terpilih menurunkan MAE test sebesar {reduction:.1f}% dibanding tebakan median training. MAE pembanding {base['test']['MAE']:.3f} kg. Nilai negatif berarti model tidak mengungguli pembanding. Coverage interval empiris pada test {best['test_interval_coverage']*100:.1f}%; jangan menjanjikan coverage 90% jika hasil pengujian berbeda.\"))
display(Markdown('File hasil tersedia di results/evaluation; model dan preprocessing di models/best_model. Model lama tim tetap disimpan. Laporan lokal dibuat dari angka hasil ini dan harus diperbarui bila eksperimen dijalankan ulang.'))
""")])

print('Delapan notebook dilengkapi; seluruh sel kode awal tetap dipertahankan.')
