"""Klien WebHDFS diuji terhadap server WebHDFS tiruan (perilaku Hadoop 3).

Tidak membutuhkan database maupun Hadoop sungguhan.
"""

import json
from urllib.parse import unquote, urlparse

import httpx
import pytest

from foodsave_core.storage import (
    RAW_SEED,
    LocalStorage,
    WebHDFSStorage,
    ensure_layout,
    normalize,
)


class FakeHDFS:
    """Namenode menjawab CREATE dengan 307 (atau JSON bila noredirect), datanode menerima data."""

    def __init__(self, honour_noredirect=True, live_datanodes=1, safemode=False):
        self.files: dict[str, bytes] = {}
        self.dirs = {"/"}
        self.honour_noredirect = honour_noredirect
        self.users = set()
        self.live_datanodes = live_datanodes
        self.safemode = safemode
        self.jmx_calls = 0
        self.on_jmx = None  # fungsi opsional untuk mengubah status kluster

    @staticmethod
    def remote_error(status, exception, message):
        return httpx.Response(status, json={"RemoteException": {
            "exception": exception, "message": message}})

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        params = dict(request.url.params)
        path = unquote(url.path.removeprefix("/webhdfs/v1")) or "/"
        op = params.get("op")
        if url.path == "/jmx":
            self.jmx_calls += 1
            if self.on_jmx:
                self.on_jmx(self)
            if "FSNamesystemState" in params.get("qry", ""):
                return httpx.Response(200, json={"beans": [
                    {"NumLiveDataNodes": self.live_datanodes, "FSState": "Operational"}]})
            return httpx.Response(200, json={"beans": [
                {"Safemode": "Safe mode is ON." if self.safemode else ""}]})
        if url.netloc == "datanode:9864":
            self.files[path] = request.content
            return httpx.Response(201)
        self.users.add(params.get("user.name"))  # hanya permintaan ke namenode
        if op in ("CREATE", "MKDIRS") and self.safemode:
            return self.remote_error(403, "SafeModeException", "Name node is in safe mode.")
        if op == "CREATE" and self.live_datanodes < 1:
            return self.remote_error(403, "IOException", "Failed to find datanode.")
        if op == "CREATE":
            if path in self.files and params.get("overwrite") == "false":
                return httpx.Response(403, json={"RemoteException": {
                    "exception": "FileAlreadyExistsException", "message": f"{path} already exists"}})
            location = f"http://datanode:9864/webhdfs/v1{path}?op=CREATE"
            if self.honour_noredirect and params.get("noredirect") == "true":
                return httpx.Response(200, json={"Location": location})
            return httpx.Response(307, headers={"Location": location})
        if op == "OPEN":
            if path not in self.files:
                return httpx.Response(404, json={"RemoteException": {"message": "not found"}})
            return httpx.Response(200, content=self.files[path])
        if op == "GETFILESTATUS":
            exists = path in self.files or path in self.dirs
            return httpx.Response(200 if exists else 404, json={})
        if op == "MKDIRS":
            parts = path.strip("/").split("/")
            for i in range(1, len(parts) + 1):
                self.dirs.add("/" + "/".join(parts[:i]))
            return httpx.Response(200, json={"boolean": True})
        if op == "LISTSTATUS":
            if path not in self.dirs:
                return httpx.Response(404, json={})
            children = {}
            for name in list(self.files) + list(self.dirs):
                if name != path and name.startswith(path.rstrip("/") + "/"):
                    child = name[len(path.rstrip("/")) + 1:].split("/")[0]
                    is_dir = "/" in name[len(path.rstrip("/")) + 1:] or name in self.dirs
                    children[child] = is_dir
            statuses = [{"pathSuffix": n, "type": "DIRECTORY" if d else "FILE",
                         "length": 0 if d else len(self.files.get(f"{path}/{n}", b""))}
                        for n, d in children.items()]
            return httpx.Response(200, content=json.dumps(
                {"FileStatuses": {"FileStatus": statuses}}))
        if op == "DELETE":
            self.files = {k: v for k, v in self.files.items() if not k.startswith(path)}
            self.dirs = {d for d in self.dirs if not d.startswith(path)}
            return httpx.Response(200, json={"boolean": True})
        return httpx.Response(400)


@pytest.mark.parametrize("noredirect", [True, False])
def test_webhdfs_roundtrip(noredirect):
    fake = FakeHDFS(honour_noredirect=noredirect)
    storage = WebHDFSStorage("http://namenode:9870", "foodsave",
                             transport=httpx.MockTransport(fake.handler))
    ensure_layout(storage)
    storage.write_bytes(RAW_SEED, b"date,food_waste_kg\n2024-01-01,10\n")
    assert storage.exists(RAW_SEED) and not storage.exists("/foodsave/raw/tidak_ada.csv")
    assert storage.read_bytes(RAW_SEED).startswith(b"date,")
    names = [e.name for e in storage.list("/foodsave/raw")]
    assert "train.csv" in names and "actuals" in names
    with pytest.raises(FileExistsError):
        storage.write_bytes(RAW_SEED, b"x", overwrite=False)
    with pytest.raises(FileNotFoundError):
        storage.read_bytes("/foodsave/models/v0/model_rf_optimize.pkl")
    storage.delete("/foodsave/raw/train.csv")
    assert not storage.exists(RAW_SEED)
    assert fake.users == {"foodsave"}


def test_paths_cannot_escape_foodsave_root(tmp_path):
    with pytest.raises(ValueError):
        normalize("/etc/passwd")
    with pytest.raises(ValueError):
        normalize("/foodsave/../etc/passwd")
    storage = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.write_bytes("/foodsave/../../escape.txt", b"x")
    storage.write_bytes("/foodsave/raw/a.csv", b"ok")
    assert (tmp_path / "foodsave/raw/a.csv").read_bytes() == b"ok"


def test_bootstrap_waits_for_datanode_and_safemode(monkeypatch, tmp_path):
    """Halaman namenode sudah hidup, tetapi HDFS belum bisa ditulis: bootstrap harus menunggu."""
    import foodsave_ml.bootstrap as bootstrap

    fake = FakeHDFS(live_datanodes=0, safemode=True)

    def recover(cluster):  # datanode terdaftar setelah beberapa pemeriksaan
        if cluster.jmx_calls >= 6:
            cluster.live_datanodes, cluster.safemode = 1, False

    fake.on_jmx = recover
    storage = WebHDFSStorage("http://namenode:9870", "root",
                             transport=httpx.MockTransport(fake.handler))
    monkeypatch.setattr(bootstrap, "storage_from_env", lambda: storage)
    seed = tmp_path / "train.csv"
    seed.write_bytes(b"date,food_waste_kg\n2024-01-01,10\n")
    bootstrap.main(["--seed", str(seed)], delay=0)
    assert fake.files[RAW_SEED] == seed.read_bytes()
    assert fake.jmx_calls >= 6
    bootstrap.main(["--seed", str(seed)], delay=0)  # kedua kali: tidak diunggah ulang


def test_bootstrap_gives_up_with_clear_message(monkeypatch, tmp_path):
    import foodsave_ml.bootstrap as bootstrap

    fake = FakeHDFS(live_datanodes=0)
    storage = WebHDFSStorage("http://namenode:9870", "root",
                             transport=httpx.MockTransport(fake.handler))
    with pytest.raises(SystemExit, match="HDFS tidak siap"):
        bootstrap.wait_for(storage, attempts=3, delay=0)


def test_cluster_status_reads_jmx():
    fake = FakeHDFS(live_datanodes=2, safemode=False)
    storage = WebHDFSStorage("http://namenode:9870", transport=httpx.MockTransport(fake.handler))
    assert storage.cluster_status() == {"live_datanodes": 2, "safemode": False}
