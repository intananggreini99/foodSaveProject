"""Akses penyimpanan file FoodSave: Hadoop HDFS (WebHDFS) atau folder lokal.

Di Docker Compose, semua file data dan model berada di HDFS:

    /foodsave/raw/train.csv                  data mentah awal (Kaggle)
    /foodsave/raw/actuals/*.csv              data aktual hasil ekspor aplikasi
    /foodsave/processed/<run>/data_bersih.csv  hasil data_preprocessing
    /foodsave/models/<versi>/                data_preprocessing.pkl,
                                             model_rf_optimize.pkl, manifest.json
    /foodsave/reports/evaluasi/<versi>/      laporan evaluasi XLSX dan PDF

Backend "local" memakai struktur path yang sama di dalam satu folder, untuk
pengembangan tanpa Hadoop dan untuk pengujian otomatis.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

ROOT = "/foodsave"
RAW_DIR = f"{ROOT}/raw"
RAW_SEED = f"{RAW_DIR}/train.csv"
RAW_ACTUALS_DIR = f"{RAW_DIR}/actuals"
PROCESSED_DIR = f"{ROOT}/processed"
MODELS_DIR = f"{ROOT}/models"
EVAL_REPORTS_DIR = f"{ROOT}/reports/evaluasi"
ALL_DIRS = [ROOT, RAW_DIR, RAW_ACTUALS_DIR, PROCESSED_DIR, MODELS_DIR, EVAL_REPORTS_DIR]


class StorageError(RuntimeError):
    """Penyimpanan tidak bisa dihubungi atau menolak permintaan."""


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int


class Storage(Protocol):
    kind: str

    def write_bytes(self, path: str, data: bytes, overwrite: bool = True) -> None: ...
    def read_bytes(self, path: str) -> bytes: ...
    def exists(self, path: str) -> bool: ...
    def list(self, path: str) -> list[Entry]: ...
    def makedirs(self, path: str) -> None: ...
    def delete(self, path: str, recursive: bool = False) -> None: ...
    def ping(self) -> None: ...
    def cluster_status(self) -> dict | None: ...


def normalize(path: str) -> str:
    """Path HDFS absolut tanpa '..' agar tidak keluar dari /foodsave."""
    clean = posixpath.normpath("/" + str(path).replace("\\", "/").lstrip("/"))
    if clean != ROOT and not clean.startswith(ROOT + "/"):
        raise ValueError(f"Path harus berada di bawah {ROOT}: {path}")
    return clean


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalStorage:
    """Folder lokal yang meniru struktur HDFS (untuk dev dan tes)."""

    kind = "local"

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _local(self, path: str) -> Path:
        target = (self.root / normalize(path).lstrip("/")).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Path keluar dari folder penyimpanan.")
        return target

    def write_bytes(self, path, data, overwrite=True):
        target = self._local(path)
        if target.exists() and not overwrite:
            raise FileExistsError(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)

    def read_bytes(self, path):
        target = self._local(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        return target.read_bytes()

    def exists(self, path):
        return self._local(path).exists()

    def list(self, path):
        target = self._local(path)
        if not target.is_dir():
            raise FileNotFoundError(path)
        base = normalize(path)
        return [
            Entry(p.name, f"{base}/{p.name}", p.is_dir(), p.stat().st_size if p.is_file() else 0)
            for p in sorted(target.iterdir())
            if not p.name.endswith(".tmp")
        ]

    def makedirs(self, path):
        self._local(path).mkdir(parents=True, exist_ok=True)

    def delete(self, path, recursive=False):
        target = self._local(path)
        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
        elif target.exists():
            target.unlink()

    def ping(self):
        if not self.root.is_dir():
            raise StorageError("Folder penyimpanan lokal tidak ada.")

    def cluster_status(self):
        return None


class WebHDFSStorage:
    """Klien REST WebHDFS (Hadoop 3) tanpa dependensi native libhdfs.

    Unggah file memakai dua langkah standar WebHDFS: namenode menjawab 307
    dengan alamat datanode, lalu data dikirim ke datanode tersebut.
    """

    kind = "hdfs"

    def __init__(
        self,
        namenode_url: str,
        user: str = "foodsave",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base = namenode_url.rstrip("/") + "/webhdfs/v1"
        self.user = user
        self.timeout = timeout
        self._transport = transport  # hanya untuk tes (server WebHDFS tiruan)

    def _client(self, follow: bool = False) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout, follow_redirects=follow, transport=self._transport
        )

    def _url(self, path: str) -> str:
        return self.base + quote(normalize(path))

    def _params(self, op: str, **extra) -> dict:
        return {"op": op, "user.name": self.user, **extra}

    def _request(self, method, path, op, follow=False, content=None, **extra):
        try:
            with self._client(follow) as client:
                return client.request(
                    method, self._url(path), params=self._params(op, **extra), content=content
                )
        except httpx.HTTPError as exc:
            raise StorageError(f"HDFS tidak dapat dihubungi: {exc}") from exc

    @staticmethod
    def _raise(response, path):
        if response.status_code == 404:
            raise FileNotFoundError(path)
        if response.status_code >= 400:
            try:
                message = response.json()["RemoteException"]["message"]
            except Exception:  # noqa: BLE001 - pesan cadangan dari body
                message = response.text[:300]
            if "FileAlreadyExists" in message or "already exists" in message:
                raise FileExistsError(path)
            raise StorageError(f"HDFS menolak {path}: {response.status_code} {message}")

    def write_bytes(self, path, data, overwrite=True):
        first = self._request(
            "PUT", path, "CREATE", overwrite=str(overwrite).lower(), noredirect="true"
        )
        if first.status_code in (301, 302, 303, 307, 308):
            location = first.headers["location"]
        elif first.status_code == 200 and "Location" in first.text:
            location = first.json()["Location"]
        else:
            self._raise(first, path)
            raise StorageError(f"Jawaban CREATE tidak dikenal untuk {path}.")
        try:
            with self._client() as client:
                second = client.put(
                    location,
                    content=data,
                    headers={"Content-Type": "application/octet-stream"},
                )
        except httpx.HTTPError as exc:
            raise StorageError(f"Datanode HDFS tidak dapat dihubungi: {exc}") from exc
        self._raise(second, path)

    def read_bytes(self, path):
        response = self._request("GET", path, "OPEN", follow=True)
        self._raise(response, path)
        return response.content

    def exists(self, path):
        response = self._request("GET", path, "GETFILESTATUS")
        if response.status_code == 404:
            return False
        self._raise(response, path)
        return True

    def list(self, path):
        response = self._request("GET", path, "LISTSTATUS")
        self._raise(response, path)
        base = normalize(path)
        items = response.json()["FileStatuses"]["FileStatus"]
        return sorted(
            (
                Entry(
                    item["pathSuffix"],
                    f"{base}/{item['pathSuffix']}",
                    item["type"] == "DIRECTORY",
                    int(item.get("length", 0)),
                )
                for item in items
            ),
            key=lambda e: e.name,
        )

    def makedirs(self, path):
        response = self._request("PUT", path, "MKDIRS")
        self._raise(response, path)

    def delete(self, path, recursive=False):
        response = self._request("DELETE", path, "DELETE", recursive=str(recursive).lower())
        self._raise(response, path)

    def ping(self):
        response = self._request("GET", ROOT, "GETFILESTATUS")
        if response.status_code not in (200, 404):
            self._raise(response, ROOT)

    def cluster_status(self) -> dict | None:
        """Jumlah datanode hidup dan status safemode dari JMX namenode.

        Menulis file baru gagal bila belum ada datanode terdaftar atau namenode
        masih safemode, padahal halaman namenode sudah bisa diakses.
        """
        root = self.base.removesuffix("/webhdfs/v1")
        try:
            with self._client() as client:
                state = client.get(
                    f"{root}/jmx", params={"qry": "Hadoop:service=NameNode,name=FSNamesystemState"}
                )
                info = client.get(
                    f"{root}/jmx", params={"qry": "Hadoop:service=NameNode,name=NameNodeInfo"}
                )
            live = int(state.json()["beans"][0]["NumLiveDataNodes"])
            safemode = bool(str(info.json()["beans"][0].get("Safemode", "")).strip())
            return {"live_datanodes": live, "safemode": safemode}
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
            return None


def storage_from_env() -> Storage:
    """FOODSAVE_STORAGE=hdfs (Docker) atau local (dev/tes)."""
    kind = os.environ.get("FOODSAVE_STORAGE", "local").strip().lower()
    if kind == "hdfs":
        return WebHDFSStorage(
            os.environ.get("HDFS_NAMENODE_URL", "http://namenode:9870"),
            os.environ.get("HDFS_USER", "foodsave"),
            float(os.environ.get("HDFS_TIMEOUT_SECONDS", "30")),
        )
    if kind == "local":
        return LocalStorage(os.environ.get("LOCAL_STORAGE_ROOT", "./storage/hdfs"))
    raise ValueError("FOODSAVE_STORAGE harus 'hdfs' atau 'local'.")


def ensure_layout(storage: Storage) -> None:
    for directory in ALL_DIRS:
        storage.makedirs(directory)
