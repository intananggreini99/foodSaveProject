"""Swagger UI (/docs) dipakai untuk mencoba fitur tanpa frontend: kelompok dan contoh harus benar."""

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


def test_every_endpoint_has_a_feature_group_and_title():
    spec = app.openapi()
    names = {t["name"] for t in openapi_docs.TAGS}
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            assert (method.upper(), path) in openapi_docs.ROUTES, f"{method.upper()} {path} belum dikelompokkan"
            assert op["tags"][0] in names


def test_swagger_examples_are_valid_request_bodies():
    for model in REQUEST_MODELS:
        example = model.model_json_schema()["examples"][0]
        model.model_validate(example)
        assert model.model_config["extra"] == "forbid"
