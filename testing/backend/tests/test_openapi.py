"""Swagger UI (/docs) bawaan hanya untuk Prediksi 7 Hari dan Simulasi Porsi (+ Login bila wajib); contoh valid."""

from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient

from app import openapi_docs, schemas
from app.main import app

REQUEST_MODELS = [
    schemas.Credentials,
    schemas.Register,
    schemas.UserCreate,
    schemas.ProfileUpdate,
    schemas.RestaurantUpdate,
    schemas.SettingsUpdate,
    schemas.DailyInput,
    schemas.DailyUpdate,
    schemas.PredictionPreview,
    schemas.WeeklyCreate,
    schemas.PlanDayUpdate,
    schemas.ScenarioCreate,
    schemas.ScenarioOptions,
    schemas.ApplyScenario,
    schemas.ReportRequest,
]


def full_spec():
    return get_openapi(title=app.title, version=app.version, routes=app.routes)


def check_shown(spec, expected):
    assert [t["name"] for t in spec["tags"]] == expected
    operations = [op for ops in spec["paths"].values() for op in ops.values()]
    assert {op["tags"][0] for op in operations} == set(expected)
    assert len(operations) == sum(1 for tag, _ in openapi_docs.ROUTES.values() if tag in expected)
    # Simulasi butuh rencana harian: "Simpan input harian" ikut tampil sebagai langkah 1.
    assert spec["paths"]["/api/v1/daily-operations"]["post"]["tags"] == [openapi_docs.SIMULASI]
    assert "get" not in spec["paths"]["/api/v1/daily-operations"]
    for hidden in ("/api/v1/predictions/preview", "/api/v1/imports", "/api/v1/dashboard"):
        assert hidden not in spec["paths"]


def test_docs_without_login_show_only_seven_day_plan_and_simulation():
    spec = openapi_docs.arrange(full_spec(), login_required=False)
    check_shown(spec, ["1. Prediksi 7 Hari", "2. Simulasi Porsi"])
    assert not any(path.startswith("/api/v1/auth") for path in spec["paths"])
    assert "Tidak perlu login" in spec["info"]["description"]


def test_docs_add_login_group_when_login_is_required():
    spec = app.openapi()  # nilai bawaan di kode: login diwajibkan
    check_shown(spec, ["Login", "1. Prediksi 7 Hari", "2. Simulasi Porsi"])
    assert "Daftar akun" in spec["info"]["description"]
    # Endpoint lain disembunyikan dari /docs, bukan dihapus: masih menjawab (401, bukan 404).
    assert TestClient(app).get("/api/v1/dashboard", params={"on": "2026-11-19"}).status_code == 401


def test_every_endpoint_has_a_group_when_showing_all():
    spec = openapi_docs.arrange(full_spec(), show_all=True)
    names = {t["name"] for t in openapi_docs.TAGS}
    total = 0
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            assert (method.upper(), path) in openapi_docs.ROUTES, f"{method.upper()} {path} belum dikelompokkan"
            assert op["tags"][0] in names
            total += 1
    assert total == len(openapi_docs.ROUTES)


def test_swagger_examples_are_valid_request_bodies():
    for model in REQUEST_MODELS:
        example = model.model_json_schema()["examples"][0]
        model.model_validate(example)
        assert model.model_config["extra"] == "forbid"
