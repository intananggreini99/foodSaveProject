"""Buat laporan Word lokal dari hasil eksperimen, tanpa angka buatan.

Jalankan dengan runtime dokumen yang menyediakan python-docx.
"""
from pathlib import Path
import csv
import json
import statistics
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/evaluation'
REPORT = ROOT/'results/FoodSave_Laporan_Perbandingan_Model.docx'


def read_csv(name):
    with (OUT/name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def read_json(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def num(value, digits=3):
    return f'{float(value):.{digits}f}'.replace('.', ',')


def paragraph(text, style=None):
    return doc.add_paragraph(text, style)


def heading(text):
    doc.add_heading(text, level=1)


def page(title):
    doc.add_page_break(); heading(title)


def table(headers, rows, widths=None):
    t=doc.add_table(rows=1, cols=len(headers)); t.style='Table Grid'
    t.autofit=False
    for cell, text in zip(t.rows[0].cells, headers):
        cell.text=str(text)
        cell._tc.get_or_add_tcPr().append(OxmlElement('w:shd'))
        cell._tc.tcPr[-1].set(qn('w:fill'),'E8EEF4')
        for run in cell.paragraphs[0].runs: run.bold=True
    repeat=OxmlElement('w:tblHeader'); repeat.set(qn('w:val'),'true');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for values in rows:
        cells=t.add_row().cells
        for cell,text in zip(cells,values): cell.text=str(text)
    for row in t.rows:
        no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
        if widths:
            for cell,width in zip(row.cells,widths): cell.width=Inches(width)
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(4)
                p.paragraph_format.space_before=Pt(4)
                for run in p.runs: run.font.size=Pt(9)
    paragraph('')
    return t


def picture(filename, caption, width=6.2):
    doc.add_picture(str(OUT/filename), width=Inches(width))
    p=paragraph(caption);p.paragraph_format.space_after=Pt(10)
    for r in p.runs:r.italic=True;r.font.size=Pt(9)


rows=read_csv('experiment_results.csv');best=read_json('best_model.json');audit=read_json('data_audit.json');baseline=read_json('baseline_metrics.json')
doc=Document(); section=doc.sections[0]
section.page_width=Inches(8.27);section.page_height=Inches(11.69)
section.top_margin=section.bottom_margin=Inches(.65)
section.left_margin=section.right_margin=Inches(.8)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2']:
    style=doc.styles[name];style.font.name='Calibri';style.font.color.rgb=RGBColor(0,0,0)
doc.styles['Normal'].font.size=Pt(11)
doc.styles['Normal'].paragraph_format.space_after=Pt(7)
doc.styles['Normal'].paragraph_format.line_spacing=1.1
doc.styles['Title'].font.size=Pt(26)
doc.styles['Heading 1'].font.size=Pt(17)
doc.styles['Heading 2'].font.size=Pt(13)
doc.core_properties.title='Laporan perbandingan model FoodSave Restaurant'
doc.core_properties.subject='Delapan eksperimen prediksi limbah makanan dengan evaluasi kronologis'
doc.add_heading('Laporan perbandingan model FoodSave Restaurant',0)
paragraph('Prediksi jumlah limbah makanan dalam kilogram', 'Subtitle')
paragraph('Hasil pelatihan lokal • 11 November 2026')
heading('Hasil utama')
paragraph(f"Model terpilih adalah {best['model']} dengan preprocessing {best['preprocessing']}. Model ini memiliki MAE validasi {num(best['validation_MAE'])} kg, paling kecil di antara delapan eksperimen. Pada periode test, MAE-nya {num(best['test_MAE'])} kg, RMSE {num(best['test_RMSE'])} kg, dan R² {num(best['test_R2'])}.")
paragraph('MAE dapat dibaca sebagai rata-rata selisih prediksi dari limbah aktual. Sebagai contoh, MAE 5 kg berarti kesalahan absolut rata-rata sekitar 5 kg per observasi. Angka tersebut bukan jaminan kesalahan setiap prediksi.')
improvement=(baseline['test']['MAE']-float(best['test_MAE']))/baseline['test']['MAE']*100
paragraph(f"Pembanding sederhana selalu menebak median limbah training. MAE test pembanding ini {num(baseline['test']['MAE'])} kg. Pengurangan MAE model terpilih terhadap pembanding adalah {num(improvement,1)}%. Nilai negatif berarti model lebih buruk daripada pembanding.")
heading('Tujuan penelitian')
paragraph('Menyelesaikan LSTM, Random Forest, XGBoost, dan CatBoost dengan dua pendekatan preprocessing; membandingkan hasil secara adil; serta menyediakan artefak model, metrik, grafik, dan penjelasan kode yang dapat diulang.')
paragraph('Pemilihan pemenang menggunakan data validasi. Data test dari periode terbaru dipakai untuk melaporkan kemampuan akhir, bukan memilih atau menyesuaikan model. Kesimpulan berlaku pada dataset dan rancangan eksperimen ini.')
table(['Keluaran','Lokasi di proyek'],[
    ['Notebook lengkap','notebooks/01 sampai 08'],['Hasil dan grafik','results/evaluation'],['Model dan preprocessing','models/best_model'],['Kode eksperimen','src/experiment.py'],['Laporan ini','results/FoodSave_Laporan_Perbandingan_Model.docx']], [1.6,4.9])

page('Data dan rancangan eksperimen')
paragraph(f"Dataset berasal dari train.csv dalam ZIP yang diberikan pengguna. Terdapat {audit['raw_rows']} baris awal, {audit['invalid_date_or_target_removed']} baris dengan tanggal/target tidak valid yang dikeluarkan, dan {audit['exact_duplicates_removed_for_all_models']} duplikat persis tanpa ID yang dihapus. Tersisa {audit['usable_rows']} observasi berlabel.")
table(['Partisi','Jumlah baris','Tanggal awal','Tanggal akhir'],[[s,str(v['n']),v['start'],v['end']] for s,v in audit['split'].items()],[1.2,1.1,2.1,2.1])
paragraph('Pembagian memakai sekitar 60% tanggal awal untuk training, 20% berikutnya untuk validasi, dan 20% terakhir untuk test. Seluruh baris bertanggal sama tetap berada pada satu partisi. Enam observasi training pertama tidak menjadi target pelatihan semua model agar sesuai kebutuhan konteks LSTM.')
paragraph('Median, modus, batas IQR, daftar kategori, dan skala dipelajari dari training saja. Tidak ada pencampuran tanggal antarpartisi. Seluruh model memakai target validasi/test dan indeks baris yang sama. Target kilogram yang ekstrem tidak dipotong atau diganti.')
heading('Fitur dan asumsi waktu prediksi')
paragraph('Input mencakup porsi, staf, suhu, kelembapan, acara khusus, pengalaman staf, kalender, rasio staf/porsi, dan interaksi acara dengan porsi. Suhu dan kelembapan harus berupa informasi/perkiraan yang sudah tersedia saat perencanaan. ID dikeluarkan. Hari dihitung ulang dari tanggal.')
paragraph('Kategori limbah dan past_waste_kg dikeluarkan karena waktu ketersediaan serta asal periode/restorannya belum terverifikasi. Keputusan konservatif ini mengurangi risiko membocorkan informasi yang baru diketahui setelah limbah terjadi.')
heading('Keterbatasan urutan LSTM')
paragraph('LSTM membaca tujuh observasi fitur, termasuk input operasional target yang diasumsikan sudah diketahui. Tidak ada target aktual dalam input. Jendela ini bukan tujuh hari: tanggal tidak selalu berjarak satu hari dan tidak tersedia ID restoran. Hasil LSTM tidak membuktikan pola harian satu restoran ataupun kemampuan prediksi tujuh hari ke depan.')

page('Kualitas data dan preprocessing')
table(['Langkah','Standard','Robust'],[
    ['Angka berupa teks','Konversi angka sederhana','Bersihkan simbol dan spasi, lalu konversi'],
    ['Kategori pengalaman','Penulisan dipertahankan','Huruf kecil dan pangkas spasi'],
    ['Nilai kosong','Median/modus training','Median/modus training'],
    ['Outlier fitur','Dipertahankan','Batas Q1 − 1,5 IQR dan Q3 + 1,5 IQR training'],
    ['Scaling LSTM','StandardScaler','RobustScaler'],
    ['Encoding','One-hot; CatBoost memakai kategori','One-hot; CatBoost memakai kategori'],
    ['Target evaluasi','Aktual tanpa clipping','Aktual tanpa clipping'],
    ['Duplikat persis','Dihapus sebelum split','Dihapus sebelum split']], [1.3,2.4,2.8])
paragraph('Batas outlier Robust diterapkan konsisten pada training, validasi, dan test menggunakan batas yang dipelajari dari training. Tidak ada penyesuaian batas berdasarkan test. Untuk model pohon, scaling tidak diperlukan. Kategori yang belum dikenal diabaikan pada one-hot; CatBoost dapat menerima kategori baru.')
missing=[(k,str(v)) for k,v in audit['missing_before'].items() if v]
if missing: table(['Kolom dengan nilai kosong asli','Jumlah'],missing,[4.5,2.0])
paragraph('Angka kosong setelah konversi juga diimputasi, sehingga jumlah kosong asli di atas belum mencakup semua teks angka yang gagal dibaca. Notebook 03 memeriksa bahwa matriks hasil preprocessing seluruhnya berisi nilai finite dan menyimpan contoh sebelum/sesudah. Tidak ada nilai kosong pada fitur akhir.')

page('Arti metrik dan hasil delapan eksperimen')
table(['Metrik','Cara membaca'],[
    ['MAE (kg)','Rata-rata kesalahan absolut. Lebih kecil lebih baik.'],
    ['RMSE (kg)','Lebih peka pada kesalahan yang sangat besar. Lebih kecil lebih baik.'],
    ['R²','Variasi target yang dijelaskan. Lebih tinggi lebih baik; bisa negatif.'],
    ['MedAE (kg)','Nilai tengah kesalahan absolut, lebih tahan pada error ekstrem.'],
    ['Bias (kg)','Rata-rata prediksi dikurangi aktual. Positif berarti terlalu tinggi.'],
    ['WAPE (%)','Total error absolut dibagi total limbah aktual, dikali 100. Bukan akurasi.']], [1.3,5.2])
table(['Urutan validasi','Model dan preprocessing','MAE validasi','MAE test','RMSE test','R² test'],
      [[r['validation_rank'],r['model']+' '+r['preprocessing'],num(r['validation_MAE']),num(r['test_MAE']),num(r['test_RMSE']),num(r['test_R2'])] for r in rows], [.55,2.05,.95,.95,1,1])
paragraph('Urutan ditentukan oleh MAE validasi. RMSE validasi dan waktu prediksi validasi menjadi pemecah seri. Kandidat terbaik tiap eksperimen dipilih dari dua konfigurasi. Model tidak dilatih ulang pada validasi sehingga metrik training/validasi merujuk model yang sama dengan model test.')
test_best=min(rows,key=lambda r:float(r['test_MAE']))
paragraph(f"MAE test terkecil secara deskriptif dimiliki {test_best['model']} {test_best['preprocessing']} ({num(test_best['test_MAE'])} kg). Informasi ini tidak digunakan untuk mengganti pemenang validasi.")

page('Perbandingan training dan validasi')
table(['Model dan preprocessing','MAE train','RMSE train','R² train','MAE validasi','RMSE validasi','R² validasi'],
      [[r['model']+' '+r['preprocessing'],num(r['train_MAE']),num(r['train_RMSE']),num(r['train_R2']),num(r['validation_MAE']),num(r['validation_RMSE']),num(r['validation_R2'])] for r in rows], [1.8,.75,.8,.75,.8,.85,.75])
paragraph('Training adalah data yang dipakai memperbarui parameter model. Validasi adalah periode sesudah training yang dipakai memilih konfigurasi dan menghentikan pelatihan. Error training yang jauh lebih rendah daripada validasi dapat menandakan model terlalu menyesuaikan data latihan, atau distribusi waktu berubah.')
paragraph('Semua nilai MAE dan RMSE pada tabel ini dalam kilogram, termasuk LSTM yang targetnya diskalakan saat pelatihan. Seluruh prediksi LSTM dikembalikan ke satuan asli sebelum menghitung metrik. R² tidak memakai satuan kilogram.')
heading('Konfigurasi yang terpilih')
table(['Model dan preprocessing','Parameter terpilih'],[[r['model']+' '+r['preprocessing'],r['config']] for r in rows],[2.1,4.4])
paragraph('Setiap eksperimen membandingkan dua konfigurasi pada training/validasi yang sama. Jumlah kandidat terbatas untuk menyediakan eksperimen yang dapat dijalankan di komputer lokal. Pencarian ini tidak membuktikan bahwa konfigurasi yang dipilih adalah optimum global.')

page('Metrik tambahan dan biaya komputasi')
table(['Model dan preprocessing','MedAE test','Bias test','WAPE test %','Training detik','Prediksi ms per baris'],
      [[r['model']+' '+r['preprocessing'],num(r['test_MedAE']),num(r['test_Bias']),num(r['test_WAPE_percent'],2),num(r['train_time_s'],2),num(r['test_ms_per_row'],4)] for r in rows], [2.0,.85,.8,.95,.95,1.05])
paragraph('Training di tabel mencakup pelatihan dan pemantauan kurva kandidat terpilih, bukan total pencarian parameter. Impor awal library dan pengukuran gradien dapat menambah biaya. CSV juga memuat total waktu tuning kedua kandidat. Waktu prediksi adalah satu batch test dibagi jumlah baris; ini bukan benchmark permintaan tunggal dan tidak memasukkan preprocessing, pemuatan model, atau komunikasi API. Kecepatan dipengaruhi perangkat dan beban komputer.')
picture('comparison_metrics.png','Perbandingan metrik test dan waktu training. Pemenang tetap dipilih dari validasi.',6.2)

page('LSTM dan gradient descent')
paragraph('LSTM memakai memori internal untuk membaca pola pada urutan observasi. Fitur dan target diskalakan dari training. Prediksi dikembalikan ke kilogram sebelum dihitung metriknya. Jaringan terdiri dari LSTM, Dense 16 unit ReLU, dan satu keluaran angka.')
paragraph('Gradient descent memperbaiki bobot sedikit demi sedikit dengan mengikuti arah yang mengurangi loss. Bentuk sederhananya adalah bobot baru = bobot lama − learning rate × gradien loss. Implementasi memakai Adam, yang menyesuaikan pembaruan berdasarkan riwayat gradien, dengan pembatasan norma gradien 1 untuk menstabilkan pembaruan.')
paragraph('Dua kandidat memakai 24 unit/laju belajar 0,001 dan 48 unit/laju belajar 0,003. Maksimal 160 epoch, batch 32, tanpa pengacakan urutan. Early stopping memantau MSE validasi selama 20 epoch dan mengembalikan bobot terbaik. Kurva MSE target terskala dikonversi menjadi RMSE dalam kg.')
picture('LSTM_standard_curve.png','RMSE LSTM Standard pada training dan validasi.',5.9)
picture('LSTM_robust_curve.png','RMSE LSTM Robust pada training dan validasi.',5.9)

page('Diagnostik gradien LSTM')
paragraph('Norma gradien mentah sebelum clipping diukur pada batch training tetap berisi maksimal 32 observasi setiap akhir epoch. Ini menunjukkan seberapa sensitif loss terhadap bobot pada batch tersebut. Nilai tidak dalam kg dan tidak harus turun terus. Grafik ini bukan kurva akurasi, bukan besar learning rate, dan bukan semua gradien mini-batch yang dipakai Adam.')
picture('LSTM_standard_gradient.png','Besar gradien MSE target terskala pada LSTM Standard.',6.1)
picture('LSTM_robust_gradient.png','Besar gradien MSE target terskala pada LSTM Robust.',6.1)

for name, title, explanation in [
    ('RandomForest','Random Forest dan pertambahan pohon','Random Forest menggabungkan banyak pohon keputusan yang dilatih menggunakan sampel/fitur berbeda. Model ini tidak menggunakan gradient descent. Grafik berikut adalah perubahan RMSE saat jumlah pohon bertambah 20, 60, 120, 200. Dua kandidat membandingkan kedalaman tak dibatasi/10, minimum isi daun 1/3, serta proporsi fitur 1,0/0,8. Kurva tidak harus turun terus.'),
    ('XGBoost','XGBoost dan gradient boosting','XGBoost menambah pohon untuk memperbaiki kesalahan tahap sebelumnya menggunakan gradien loss. Ini berbeda dari pembaruan bobot jaringan saraf. Dua kandidat memakai kedalaman 3/5 dan regularisasi 5/10. Learning rate 0,04, maksimal 500 tahap, dan early stopping 40 tahap berdasarkan RMSE validasi. Prediksi menggunakan iterasi terbaik.'),
    ('CatBoost','CatBoost dan kategori pengalaman staf','CatBoost adalah gradient boosting dengan dukungan kategori teks. Pengalaman staf diberikan sebagai fitur kategorikal asli setelah pembersihan. Dua kandidat memakai kedalaman 4/6 dan regularisasi 5/10. Learning rate 0,04, maksimal 500 tahap, dan early stopping 40 tahap. Model menggunakan tahap terbaik berdasarkan validasi.')]:
    page(title);paragraph(explanation)
    for method in ['standard','robust']:
        r=next(r for r in rows if r['model']==name and r['preprocessing']==method)
        paragraph(f"{method.capitalize()}: konfigurasi terpilih {r['config']}; MAE validasi {num(r['validation_MAE'])} kg dan MAE test {num(r['test_MAE'])} kg.")
        picture(f'{name}_{method}_curve.png',f'Kurva training dan validasi {name} {method}.',5.9)

page('Analisis model terpilih dan rentang estimasi')
paragraph(f"Model terpilih {best['model']} {best['preprocessing']} perlu dinilai juga dari pola kesalahannya. Scatter dekat garis diagonal berarti hasil mendekati aktual. Residual positif berarti prediksi terlalu rendah; residual negatif berarti terlalu tinggi. Kesalahan ekstrem tetap dihitung dalam metrik.")
picture('best_model_diagnostics.png','Aktual versus prediksi, distribusi residual, residual versus prediksi, dan urutan observasi test.',6.3)
paragraph(f"Radius interval empiris 90% dari error absolut validasi adalah ±{num(best['empirical_90_percent_interval_radius_kg'])} kg. Cakupan yang benar-benar terukur pada test adalah {num(best['test_interval_coverage']*100,1)}%. Karena validasi juga dipakai untuk pemilihan model, interval ini eksploratif dan tidak memiliki jaminan coverage 90%.")
threshold=best['risk_thresholds_train_kg']
paragraph(f"Batas risiko sementara dari kuantil training: Aman sampai {num(threshold[0])} kg, Waspada sampai {num(threshold[1])} kg, dan Tinggi di atasnya. Batas ini merupakan pembagian statistik, belum batas biaya/operasional yang disepakati restoran.")

page('Pengaruh fitur dan dampak preprocessing')
picture('best_model_importance.png','Pengaruh fitur diukur dari kenaikan MAE validasi ketika satu fitur diacak.',6.2)
paragraph('Jika pengacakan suatu fitur menaikkan MAE, model terbantu oleh fitur tersebut. Nilai negatif menunjukkan pengacakan justru memperbaiki hasil pada sampel ini. Fitur berkorelasi bisa saling berbagi pengaruh. Importance bukan bukti sebab-akibat dan tidak menjamin bahwa mengubah fitur tersebut akan mengurangi limbah.')
delta=[]
for name in ['LSTM','RandomForest','XGBoost','CatBoost']:
    a=next(r for r in rows if r['model']==name and r['preprocessing']=='standard')
    b=next(r for r in rows if r['model']==name and r['preprocessing']=='robust')
    delta.append([name,num(float(a['validation_MAE'])-float(b['validation_MAE'])),num(float(a['test_MAE'])-float(b['test_MAE']))])
table(['Model','Penurunan MAE validasi kg','Penurunan MAE test kg'],delta,[1.7,2.4,2.4])
paragraph('Selisih dihitung sebagai Standard dikurangi Robust. Positif berarti Robust lebih baik, negatif berarti Standard lebih baik. Pembersihan tambahan tidak selalu membantu karena nilai ekstrem dapat memuat sinyal nyata, bukan kesalahan pencatatan.')

page('Insight hasil dan rekomendasi penelitian')
rf_std=next(r for r in rows if r['model']=='RandomForest' and r['preprocessing']=='standard')
rf_rob=next(r for r in rows if r['model']=='RandomForest' and r['preprocessing']=='robust')
lst_std=next(r for r in rows if r['model']=='LSTM' and r['preprocessing']=='standard')
lst_rob=next(r for r in rows if r['model']=='LSTM' and r['preprocessing']=='robust')
gain=float(rf_std['validation_MAE'])-float(rf_rob['validation_MAE'])
paragraph(f"Robust pada Random Forest mengurangi MAE validasi sebesar {num(gain)} kg atau {num(gain/float(rf_std['validation_MAE'])*100,1)}%. Namun selisih MAE test hanya {num(float(rf_std['test_MAE'])-float(rf_rob['test_MAE']),4)} kg, sehingga hasil test keduanya praktis sama. Perbandingan juga mencakup konfigurasi terpilih yang berbeda; ini bukan isolasi pengaruh clipping saja.")
paragraph(f"Random Forest Robust memiliki MAE training {num(rf_rob['train_MAE'])} kg dan validasi {num(rf_rob['validation_MAE'])} kg. Selisih {num(float(rf_rob['validation_MAE'])-float(rf_rob['train_MAE']))} kg menunjukkan perlunya perhatian terhadap overfitting atau perubahan distribusi waktu. Pemenang validasi tetap memiliki kelemahan dan tidak menjamin semua prediksi mendekati aktual.")
paragraph(f"LSTM Robust memiliki MAE validasi {num(lst_rob['validation_MAE'])} kg, lebih tinggi daripada Standard {num(lst_std['validation_MAE'])} kg. Pada rancangan ini, kombinasi pembersihan dan scaling Robust belum membantu LSTM. Kurva training terus membaik ketika validasi cenderung mendatar; early stopping mengembalikan bobot dari epoch terbaik, bukan epoch terakhir yang terlihat pada grafik.")
importance=read_csv(f"{best['model']}_{best['preprocessing']}_importance.csv")
top_feature=max(importance,key=lambda r:float(r['MAE_increase']))
paragraph(f"Fitur yang paling membantu model terpilih adalah {top_feature['feature']}. Mengacak fitur itu menaikkan MAE validasi rata-rata {num(top_feature['MAE_increase'])} kg. Ini menunjukkan ketergantungan prediksi pada fitur tersebut. Perubahan jumlah porsi perlu tetap mempertimbangkan kebutuhan pelanggan; importance tidak membuktikan bahwa mengurangi porsi pasti mengurangi limbah.")
with (ROOT/'dataset/raw/train.csv').open(encoding='utf-8-sig',newline='') as stream:
    raw_rows=list(csv.DictReader(stream))
manifest=read_csv('split_manifest.csv')
training_portions=[float(raw_rows[int(r['_row'])]['meals_served']) for r in manifest if r['split']=='train']
portion_limit=statistics.quantiles(training_portions,n=100,method='inclusive')[94]
predictions=read_csv(f"{best['model']}_{best['preprocessing']}_test_predictions.csv")
groups={'Porsi sampai P95 training':[],'Porsi di atas P95 training':[],'Tanpa acara khusus':[],'Ada acara khusus':[]}
for r in predictions:
    context=raw_rows[int(r['row'])];error=float(r['prediction'])-float(r['actual'])
    groups['Porsi di atas P95 training' if float(context['meals_served'])>portion_limit else 'Porsi sampai P95 training'].append(error)
    groups['Ada acara khusus' if float(context['special_event'])==1 else 'Tanpa acara khusus'].append(error)
table(['Kondisi test','Jumlah','MAE kg','Bias kg'],[[label,len(errors),num(statistics.mean(map(abs,errors))) if errors else 'tidak ada',num(statistics.mean(errors)) if errors else 'tidak ada'] for label,errors in groups.items()],[2.9,.7,1.4,1.5])
paragraph(f"Batas porsi besar ditetapkan dari training, yaitu P95 = {num(portion_limit,1)} porsi. Kelompok sedikit observasi tidak cukup untuk kesimpulan umum. Diagnosis ini membantu mengenali kasus sulit; hasil test tidak dipakai menyetel ulang model. Evaluasi berikutnya sebaiknya menggunakan beberapa periode validasi bergulir dan test baru yang belum dilihat.")

page('Panduan kode dan cara melanjutkan')
table(['Notebook','Tujuan kode'],[
    ['01 Data understanding','Membaca data asli, tipe kolom, nilai kosong, duplikat, tanggal, dan asumsi input.'],
    ['02 EDA','Melihat distribusi target dan pola training tanpa memakai test untuk keputusan model.'],
    ['03 Preprocessing','Mempelajari median, modus, batas IQR, encoding, dan scaling dari training saja.'],
    ['04 LSTM','Membentuk sequence, melatih Adam, mencatat loss/gradien, dan menyimpan prediksi.'],
    ['05 Random Forest','Membandingkan aturan pohon dan melihat error ketika jumlah pohon bertambah.'],
    ['06 XGBoost','Melatih boosting dengan early stopping dan menyimpan error per tahap.'],
    ['07 CatBoost','Melatih boosting dengan kategori asli dan membandingkan dua preprocessing.'],
    ['08 Evaluasi','Menggabungkan delapan hasil, memilih pemenang validasi, dan menganalisis test.']], [1.5,5])
paragraph('Setiap notebook model berisi kode pelatihan langsung dalam fungsi latih_kandidat dan langkah terpisah untuk tuning, pemilihan, evaluasi, analisis error, importance, penyimpanan, serta pembukaan ulang artefak. Kode awal tim pada notebook yang sudah dikerjakan tetap dipertahankan; alur tambahan dapat dijalankan mulai sel setup bagian Tambahan eksperimen lengkap. Sel lama tidak dicampur ke evaluasi seragam karena prosedur dan asumsi fiturnya berbeda.')
paragraph('Kode bersama di src/experiment.py memastikan definisi data, preprocessing, metrik, dan evaluasi konsisten. load_data mengaudit dan membagi tanggal. FoodPreprocessor mempelajari statistik training. sequence membentuk jendela fitur. evaluate menyusun tabel dan memilih model. train_candidate/run_model menyediakan prosedur setara untuk eksekusi terminal.')
heading('Menjalankan ulang')
paragraph('Aktifkan .venv, pasang requirements.txt, pilih kernel Python FoodSave di VS Code, lalu jalankan notebook 01 sampai 08 dalam notebooks. Notebook lama tetap dipertahankan. Alternatif terminal: python -m src.experiment --model all. Setiap run menghasilkan angka baru dan waktu komputasi dapat berubah. Setelah eksperimen berubah, jalankan evaluasi dan pembuat laporan kembali.')
heading('Kesimpulan dan langkah berikutnya')
paragraph(f"Gunakan {best['model']} {best['preprocessing']} sebagai kandidat terbaik pada rancangan ini. Hasil berasal dari satu split waktu dan satu seed, dengan dua konfigurasi per eksperimen. Belum ada pembuktian stabilitas lintas periode/restoran. Evaluasi lanjutan sebaiknya memakai rolling-origin validation dan data restoran nyata dengan definisi input yang jelas.")
paragraph('Artefak baru belum diintegrasikan ke API/dashboard. Jika ingin digunakan dalam aplikasi, preprocessing yang sama harus dipakai saat prediksi dan seluruh fitur rasio harus dihitung ulang pada simulasi porsi. Simulasi merupakan estimasi model, bukan jaminan penghematan atau bukti sebab-akibat.')

page('Rujukan dan jejak hasil')
paragraph('Rancangan penelitian mengikuti plan FoodSave Restaurant: empat model, dua preprocessing, pembagian kronologis, dan evaluasi dalam kilogram. Laporan ini mendokumentasikan eksperimen, pemilihan model, serta kode notebook. Pengembangan dan integrasi dashboard merupakan tahap lanjutan.')
for text in [
    'Plan FoodSave (3).docx — dokumen proyek yang diberikan pengguna.',
    'messy-food-waste-prediction-dataset (1).zip — arsip data yang diberikan pengguna.',
    'TensorFlow EarlyStopping: https://www.tensorflow.org/api_docs/python/tf/keras/callbacks/EarlyStopping',
    'XGBoost Python API: https://xgboost.readthedocs.io/en/stable/python/python_api.html',
    'CatBoost fit: https://catboost.ai/docs/en/concepts/python-reference_catboostregressor_fit',
    'Scikit-learn metrics: https://scikit-learn.org/stable/modules/model_evaluation.html',
    'results/evaluation/experiment_results.csv — seluruh metrik delapan eksperimen.',
    'results/evaluation/split_manifest.csv — identitas observasi dan pembagian waktunya.',
    'results/evaluation/data_audit.json — audit kualitas data dan hash sumber.',
    'results/evaluation/*_tuning.csv — kandidat parameter dan skor validasi.',
    'results/evaluation/*_curve.csv — kurva pelatihan; LSTM juga memuat norma gradien.',
    'results/evaluation/*_predictions.csv — aktual, prediksi, residual, dan tanggal.',
    'models/best_model/selected_model.json — lokasi artefak model terpilih.'
]:paragraph(text)
paragraph('SHA-256 dataset train: '+audit['source_sha256'])
REPORT.parent.mkdir(parents=True,exist_ok=True)
# Hapus border bawaan template, termasuk garis biru di bawah gaya Title.
for style in doc.styles:
    for border in list(style.element.xpath('.//w:pBdr')):
        border.getparent().remove(border)
for border in list(doc.element.xpath('.//w:pBdr')):
    border.getparent().remove(border)
doc.save(REPORT)
print(REPORT)
