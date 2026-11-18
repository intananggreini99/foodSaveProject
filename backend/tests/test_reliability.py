"""Uji keandalan: cakupan login, input liar, database/HDFS mati, file model rusak."""

import io
import json
import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app
from app.services.prediction_service import prediction_service
from foodsave_core.storage import StorageError
from tests.conftest import register

PUBLIC = {("post", "/api/v1/auth/register"), ("post", "/api/v1/auth/login")}
SAFE_STATUS = {200, 201, 204, 400, 401, 403, 404, 405, 409, 413, 415, 422}


def api_operations():
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/v1"):
            for method in ops:
                yield method, path


def concrete(path: str) -> str:
    out = path
    while "{" in out:
        start, end = out.index("{"), out.index("}")
        out = out[:start] + str(uuid.uuid4()) + out[end + 1:]
    return out


def test_every_private_endpoint_requires_login(client):
    checked = 0
    for method, path in api_operations():
        if (method, path) in PUBLIC:
            continue
        response = client.request(method.upper(), concrete(path), json={})
        assert response.status_code == 401, f"{method.upper()} {path} -> {response.status_code}"
        checked += 1
    assert checked >= 55


WILD_VALUES = [
    None, "", "x" * 10_000, "😀 ąčę <script>", -1, 0, 10**12, -(10**12), 1.5e300, True, [],
    {}, "2026-02-30", "9999-12-31", "../../etc/passwd", "' OR 1=1 --", "=CMD()",
]


def wild_payloads(seed: int):
    rng = random.Random(seed)
    base = {
        "operation_date": "2026-11-11", "meals_prepared": 400, "kitchen_staff": 10,
        "staff_experience": "expert", "special_event": False, "temperature_c": 27,
        "humidity_percent": 60, "title": "x", "starts_on": "2026-11-16",
        "reduction_percent": 5, "daily_operation_id": str(uuid.uuid4()),
        "application_date": "2026-11-11", "expected_version": 1, "correction_reason": "abc",
        "file_format": "pdf", "ends_on": "2026-11-20", "email": "a@b.co", "password": "x" * 12,
        "name": "Nama", "safe_max_kg": 10, "warning_max_kg": 20, "max_portions": 100,
        "ingredient_cost_per_kg": 1, "reduction_target_percent": 5,
    }
    yield {}
    yield []
    yield "teks biasa"
    for _ in range(12):
        payload = dict(base)
        for key in rng.sample(list(base), k=rng.randint(1, 6)):
            payload[key] = rng.choice(WILD_VALUES)
        yield payload


def test_wild_input_never_causes_server_error(client, owner):
    app_client = TestClient(app, raise_server_exceptions=False)
    app_client.cookies = client.cookies
    failures, statuses = [], {}
    for seed, (method, path) in enumerate(api_operations()):
        if method not in ("post", "put", "patch") or path.endswith("/logout"):
            continue
        for payload in wild_payloads(seed):
            response = app_client.request(method.upper(), concrete(path), json=payload)
            statuses[response.status_code] = statuses.get(response.status_code, 0) + 1
            if response.status_code not in SAFE_STATUS:
                failures.append((method, path, response.status_code, json.dumps(payload)[:120]))
        raw = app_client.request(method.upper(), concrete(path), content=b"{rusak",
                                 headers={"content-type": "application/json"})
        if raw.status_code not in SAFE_STATUS:
            failures.append((method, path, raw.status_code, "json rusak"))
    assert not failures, failures[:10]
    # Uji tidak boleh kosong: sebagian besar permintaan harus melewati login.
    assert statuses.get(401, 0) < sum(statuses.values()) / 10, statuses
    assert statuses.get(422, 0) > 100, statuses


def test_wild_query_parameters_never_cause_server_error(client, owner):
    app_client = TestClient(app, raise_server_exceptions=False)
    app_client.cookies = client.cookies
    queries = [{"on": "kemarin"}, {"end": "2026-13-01", "days": 9999}, {"limit": -5, "offset": -1},
               {"starts_on": "2026-12-01", "ends_on": "2026-01-01"},
               {"staff_experience": "dewa", "special_event": "mungkin"},
               {"scope": "semua", "version_id": "bukan-uuid"}]
    failures = []
    for method, path in api_operations():
        if method != "get":
            continue
        for params in queries:
            response = app_client.get(concrete(path), params=params)
            if response.status_code not in SAFE_STATUS:
                failures.append((path, params, response.status_code))
    assert not failures, failures[:10]


def test_oversized_upload_is_rejected(client, owner):
    big = io.BytesIO(b"a" * (5 * 1024 * 1024 + 10))
    response = client.post("/api/v1/imports", files={"file": ("besar.csv", big, "text/csv")})
    assert response.status_code == 413


def test_database_outage_returns_503(client, owner):
    def broken():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken
    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/daily-operations", cookies=client.cookies
    )
    assert response.status_code == 503 and "Database" in response.json()["detail"]
    assert response.headers.get("retry-after") == "5"


class DownStorage:
    kind = "hdfs"

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise StorageError("HDFS tidak dapat dihubungi")
        return fail


def test_hdfs_outage_keeps_cached_model_serving(client, owner, operation_payload, monkeypatch):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    assert client.post(f"/api/v1/daily-operations/{op['id']}/predict").status_code == 201
    monkeypatch.setattr("app.services.prediction_service.model_storage", lambda: DownStorage())
    monkeypatch.setattr("app.main.model_storage", lambda: DownStorage())
    ready = client.get("/health/ready")
    assert ready.status_code == 503 and "HDFS" in ready.json()["detail"]
    reload = client.post("/api/v1/model/reload")
    assert reload.status_code == 503 and "tetap dipakai" in reload.json()["detail"]
    again = client.post(f"/api/v1/daily-operations/{op['id']}/predict")
    assert again.status_code == 201  # model di memori tetap melayani


def test_tampered_model_file_is_refused(client, owner, operation_payload, monkeypatch, prepared):
    real = prepared["storage"]

    class Tampered:
        kind = "local"

        def read_bytes(self, path):
            data = real.read_bytes(path)
            return data + b"x" if path.endswith("model_rf_optimize.pkl") else data

    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    monkeypatch.setattr("app.services.prediction_service.model_storage", lambda: Tampered())
    prediction_service.reset()
    try:
        refused = client.post(f"/api/v1/daily-operations/{op['id']}/predict")
        assert refused.status_code == 503
    finally:
        monkeypatch.undo()
        prediction_service.reset()
    assert client.post(f"/api/v1/daily-operations/{op['id']}/predict").status_code == 201


def test_unexpected_error_returns_safe_json(client, owner, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("rahasia internal")

    monkeypatch.setattr("app.routers.insights.select", explode)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/insights/operational",
        params={"starts_on": "2026-11-01", "ends_on": "2026-11-30"},
        cookies=client.cookies,
    )
    body = response.json()
    assert response.status_code == 500 and "error_id" in body
    assert "rahasia" not in response.text


def test_two_restaurants_never_see_each_others_lists(client, owner, operation_payload):
    client.post("/api/v1/daily-operations", json=operation_payload)
    other = TestClient(app)
    register(other, "kedua@example.test", "Restoran Kedua")
    for path in ["/api/v1/daily-operations", "/api/v1/predictions", "/api/v1/notifications",
                 "/api/v1/weekly-predictions", "/api/v1/portion-scenarios", "/api/v1/imports",
                 "/api/v1/report-exports"]:
        body = other.get(path).json()
        items = body["items"] if isinstance(body, dict) and "items" in body else body
        assert items == [] or items == {}, path
