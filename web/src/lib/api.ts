// Alamat layanan FoodSave di laptop ini (rilis lokal). Ditanam saat build lewat
// build args di compose.yaml, mengikuti FOODSAVE_*_PORT di .env.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export const LOCAL_SERVICES = [
  { label: "API FastAPI", note: "Dokumentasi interaktif semua endpoint", url: `${API_URL}/docs` },
  {
    label: "MLflow",
    note: "Riwayat pelatihan dan Model Registry",
    url: process.env.NEXT_PUBLIC_MLFLOW_URL ?? "http://localhost:5010",
  },
  {
    label: "Hadoop HDFS",
    note: "Data mentah, file .pkl, laporan evaluasi",
    url: process.env.NEXT_PUBLIC_HDFS_URL ?? "http://localhost:9871",
  },
  {
    label: "Mailpit",
    note: "Kotak masuk email laporan (lokal)",
    url: process.env.NEXT_PUBLIC_MAILPIT_URL ?? "http://localhost:8026",
  },
];
