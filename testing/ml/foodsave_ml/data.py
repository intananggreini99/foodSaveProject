"""Membaca data mentah dari HDFS, membersihkan, dan membagi menurut waktu."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import numpy as np
import pandas as pd

from foodsave_core.features import RAW_COLUMNS
from foodsave_core.preprocessing import TARGET
from foodsave_core.storage import RAW_ACTUALS_DIR, RAW_SEED, Storage, sha256


@dataclass
class Source:
    path: str
    sha256: str
    rows: int
    kind: str  # "seed" (train.csv awal) atau "actuals" (ekspor aplikasi)


def read_sources(storage: Storage) -> tuple[list[pd.DataFrame], list[Source]]:
    frames, sources = [], []
    if not storage.exists(RAW_SEED):
        raise FileNotFoundError(
            f"{RAW_SEED} belum ada. Jalankan 'python -m foodsave_ml.bootstrap' terlebih dahulu."
        )
    seed_bytes = storage.read_bytes(RAW_SEED)
    seed = pd.read_csv(io.BytesIO(seed_bytes))
    seed["source"] = "seed"
    frames.append(seed)
    sources.append(Source(RAW_SEED, sha256(seed_bytes), len(seed), "seed"))
    if storage.exists(RAW_ACTUALS_DIR):
        for entry in storage.list(RAW_ACTUALS_DIR):
            if entry.is_dir or not entry.name.endswith(".csv"):
                continue
            content = storage.read_bytes(entry.path)
            frame = pd.read_csv(io.BytesIO(content))
            frame["source"] = "actuals"
            frames.append(frame)
            sources.append(Source(entry.path, sha256(content), len(frame), "actuals"))
    return frames, sources


def clean(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Baris tanpa tanggal/target valid dibuang; duplikat persis dihapus.

    Data aktual dari aplikasi bisa terekspor lebih dari sekali (misalnya setelah
    koreksi). Untuk setiap operation_id hanya ekspor terbaru yang dipakai.
    """
    combined = pd.concat(frames, ignore_index=True, sort=False)
    raw_rows = len(combined)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined[TARGET] = pd.to_numeric(combined[TARGET], errors="coerce")
    valid = combined["date"].notna() & combined[TARGET].notna() & (combined[TARGET] >= 0)
    df = combined.loc[valid].copy()
    invalid = int((~valid).sum())

    duplicates = 0
    if "operation_id" in df.columns:
        actuals = df[df["source"] == "actuals"].copy()
        if len(actuals):
            actuals["exported_at"] = pd.to_datetime(actuals["exported_at"], errors="coerce")
            before = len(actuals)
            actuals = actuals.sort_values("exported_at").drop_duplicates(
                "operation_id", keep="last"
            )
            duplicates += before - len(actuals)
        df = pd.concat([df[df["source"] != "actuals"], actuals], ignore_index=True)

    key = [c for c in RAW_COLUMNS if c not in ("ID",) and c in df.columns]
    before = len(df)
    df = df.drop_duplicates(key, keep="first")
    duplicates += before - len(df)

    df = df.reset_index(drop=True)
    df["_order"] = np.arange(len(df))
    df = df.sort_values(["date", "_order"], kind="stable").reset_index(drop=True)
    audit = {
        "raw_rows": raw_rows,
        "usable_rows": len(df),
        "invalid_removed": invalid,
        "duplicates_removed": int(duplicates),
        "date_start": df["date"].min().date(),
        "date_end": df["date"].max().date(),
    }
    return df, audit


def temporal_split(df: pd.DataFrame, test_fraction: float) -> pd.DataFrame:
    """Tanggal paling akhir (test_fraction dari tanggal unik) menjadi data test.

    Semua baris pada satu tanggal selalu berada di bagian yang sama, sehingga
    tidak ada informasi dari tanggal test yang masuk ke pelatihan.
    """
    dates = np.sort(df["date"].unique())
    cut = dates[int(len(dates) * (1 - test_fraction))]
    out = df.copy()
    out["split"] = np.where(out["date"] < cut, "dev", "test")
    dev, test = out[out.split == "dev"], out[out.split == "test"]
    assert dev["date"].max() < test["date"].min(), "Split waktu bocor."
    return out


def fingerprint(sources: list[Source]) -> str:
    text = "|".join(sorted(f"{s.path}:{s.sha256}" for s in sources))
    return hashlib.sha256(text.encode()).hexdigest()
