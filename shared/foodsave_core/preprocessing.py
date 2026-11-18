"""Preprocessing model FoodSave (pendekatan robust).

Semua statistik (median, modus, batas IQR, daftar kolom one-hot) dipelajari
hanya dari data yang diberikan ke fit(). Pipeline memanggil fit() di dalam
setiap lipatan validasi silang, lalu sekali lagi pada seluruh data untuk file
data_preprocessing.pkl versi produksi.

Fitur yang dipakai model hanya data rencana yang sudah diketahui sebelum hari
operasional: tanggal, jumlah porsi, jumlah staf, pengalaman staf, acara
khusus, suhu, dan kelembapan. waste_category dan past_waste_kg tidak dipakai.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET = "food_waste_kg"
NUMERIC = ["meals_served", "kitchen_staff", "temperature_C", "humidity_percent", "special_event"]
CATEGORICAL = ["staff_experience"]
RAW_INPUT_COLUMNS = ["date", *NUMERIC, *CATEGORICAL]
CLIPPED = ["meals_served", "kitchen_staff", "temperature_C", "humidity_percent"]
EXPERIENCE_LEVELS = ["beginner", "intermediate", "expert"]


class FoodPreprocessor:
    """Membersihkan data mentah dan membentuk matriks fitur numerik."""

    def __init__(self, method: str = "robust"):
        if method not in {"robust", "standard"}:
            raise ValueError("method harus 'robust' atau 'standard'.")
        self.method = method

    # -- tahap pembersihan -------------------------------------------------
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in RAW_INPUT_COLUMNS if c not in df.columns]
        if missing:
            raise KeyError(f"Kolom input tidak lengkap: {missing}")
        d = df[NUMERIC + CATEGORICAL].copy()
        for column in NUMERIC:
            series = d[column]
            if self.method == "robust":
                series = (
                    series.astype("string")
                    .str.strip()
                    .str.replace(",", "", regex=False)
                    .str.replace(r"[^0-9.eE+\-]", "", regex=True)
                )
            d[column] = (
                pd.to_numeric(series, errors="coerce")
                .astype("float64")
                .replace([np.inf, -np.inf], np.nan)
            )
        for column in CATEGORICAL:
            series = d[column].astype("string")
            if self.method == "robust":
                series = (
                    series.str.strip()
                    .str.lower()
                    .replace({"nan": pd.NA, "none": pd.NA, "": pd.NA})
                )
            d[column] = series
        date = pd.to_datetime(df["date"])
        d["is_weekend"] = (date.dt.day_of_week >= 5).astype(float)
        d["month_sin"] = np.sin(2 * np.pi * date.dt.month / 12)
        d["month_cos"] = np.cos(2 * np.pi * date.dt.month / 12)
        return d

    # -- belajar statistik dari data latih ---------------------------------
    def fit(self, df: pd.DataFrame) -> "FoodPreprocessor":
        d = self.clean(df)
        self.numerics = d.select_dtypes(include="number").columns.tolist()
        self.medians = d[self.numerics].median().fillna(0)
        self.modes = {
            c: (d[c].dropna().mode().iloc[0] if d[c].notna().any() else "unknown")
            for c in CATEGORICAL
        }
        self.bounds: dict[str, tuple[float, float]] = {}
        if self.method == "robust":
            for column in CLIPPED:
                q1, q3 = d[column].quantile([0.25, 0.75])
                iqr = q3 - q1
                self.bounds[column] = (float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr))
        self.columns = pd.get_dummies(
            self.native(df), columns=CATEGORICAL, dtype=float
        ).columns.tolist()
        return self

    def native(self, df: pd.DataFrame) -> pd.DataFrame:
        d = self.clean(df)
        d[self.numerics] = d[self.numerics].fillna(self.medians)
        for column, bounds in self.bounds.items():
            d[column] = d[column].clip(*bounds)
        for column in CATEGORICAL:
            d[column] = d[column].fillna(self.modes[column]).astype(str)
        # Rasio dihitung setelah imputasi dan penanganan outlier.
        d["staff_per_portion"] = d.kitchen_staff / d.meals_served.clip(lower=1)
        d["portion_per_staff"] = d.meals_served / d.kitchen_staff.clip(lower=1)
        d["special_event_portion"] = d.special_event * d.meals_served
        return d

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        encoded = pd.get_dummies(self.native(df), columns=CATEGORICAL, dtype=float)
        return encoded.reindex(columns=self.columns, fill_value=0).astype(float)

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.fit(df).transform(df)

    def training_range(self) -> dict[str, tuple[float, float]]:
        """Rentang nilai yang dianggap wajar oleh model (batas IQR data latih)."""
        return dict(self.bounds)
