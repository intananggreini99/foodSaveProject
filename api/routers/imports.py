import csv
import hashlib
import io
import uuid
import zipfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select
from api.auth import CurrentUser, Db, Manager
from api.config import get_settings
from api.models import DailyOperation, DataImport
from api.schemas import DailyInput
from api.services import owned, restaurant_settings, serialize

router = APIRouter(prefix="/imports", tags=["Unggah CSV dan Excel"])
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000


def storage_file(key):
    root = get_settings().storage_path.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(404, "File tidak ditemukan.")
    return path


def parse_rows(content, suffix):
    try:
        if suffix == ".csv":
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(set(h.strip() for h in headers)):
                raise ValueError("Header CSV tidak boleh duplikat.")
            result = []
            for row in reader:
                result.append(row)
                if len(result) > MAX_ROWS:
                    raise ValueError("Maksimal 10.000 baris per file.")
            return result
        from openpyxl import load_workbook

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError("Isi Excel setelah ekstraksi terlalu besar.")
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            rows = book.active.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                raise ValueError("Excel tidak memiliki header.")
            names = [str(h).strip() if h is not None else "" for h in headers]
            if len(names) != len(set(names)):
                raise ValueError("Header Excel tidak boleh duplikat.")
            result = []
            for row in rows:
                if not any(v is not None for v in row):
                    continue
                result.append(dict(zip(names, row)))
                if len(result) > MAX_ROWS:
                    raise ValueError("Maksimal 10.000 baris per file.")
            return result
        finally:
            book.close()
    except (UnicodeError, ValueError, zipfile.BadZipFile, KeyError, TypeError, csv.Error) as exc:
        raise HTTPException(422, f"File tidak dapat dibaca: {exc}") from exc


def normalize(row):
    aliases = {
        "date": "operation_date",
        "meals_served": "meals_prepared",
        "temperature_C": "temperature_c",
        "past_waste_kg": "previous_waste_kg",
        "food_waste_kg": "actual_waste_kg",
    }
    if None in row:
        raise ValueError("Jumlah kolom baris tidak sesuai header.")
    value = {}
    for key, item in row.items():
        key = str(key).strip()
        if key in ["ID", "day_of_week"]:
            continue
        key = aliases.get(key, key)
        if key in value:
            raise ValueError("Kolom alias dan kolom utama tidak boleh ditulis bersamaan.")
        value[key] = item
    for key in list(value):
        if value[key] == "":
            value[key] = None
    experience = str(value.get("staff_experience", "")).strip().lower()
    value["staff_experience"] = {
        "pemula": "beginner",
        "menengah": "intermediate",
        "ahli": "expert",
    }.get(experience, experience)
    operation_date = value.get("operation_date")
    if hasattr(operation_date, "date"):
        value["operation_date"] = operation_date.date()
    return value


@router.post("", status_code=201)
def upload(db: Db, user: Manager, file: UploadFile = File(...), apply: bool = False):
    original = Path((file.filename or "upload").replace("\\", "/")).name[:255]
    suffix = Path(original).suffix.lower()
    if suffix not in [".csv", ".xlsx"]:
        raise HTTPException(415, "Gunakan CSV UTF-8 atau Excel .xlsx.")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Ukuran file maksimal 5 MB.")
    rows = parse_rows(content, suffix)
    if not rows:
        raise HTTPException(422, "File tidak berisi data.")
    settings = restaurant_settings(db, user)
    existing = set(
        db.scalars(
            select(DailyOperation.operation_date).where(
                DailyOperation.restaurant_id == user.restaurant_id
            )
        ).all()
    )
    valid = []
    findings = []
    invalid = 0
    unusual = 0
    for number, row in enumerate(rows, start=2):
        try:
            value = DailyInput.model_validate(normalize(row))
            if value.meals_prepared > settings.max_portions:
                raise ValueError("Jumlah porsi melebihi kapasitas restoran.")
            if value.operation_date in existing:
                raise ValueError("Tanggal sudah ada atau duplikat dalam file.")
            existing.add(value.operation_date)
            warnings = []
            if value.temperature_c < 0 or value.temperature_c > 50:
                warnings.append("Suhu tidak lazim untuk dapur; periksa kembali.")
            if value.meals_prepared and value.kitchen_staff > value.meals_prepared:
                warnings.append("Staf lebih banyak daripada porsi.")
            if (
                value.actual_waste_kg is not None
                and value.meals_prepared == 0
                and value.actual_waste_kg > 0
            ):
                warnings.append("Ada limbah pada rencana nol porsi.")
            if warnings:
                unusual += 1
            if warnings and len(findings) < 500:
                findings.append({"row": number, "status": "unusual", "messages": warnings})
            valid.append(value)
        except (ValidationError, ValueError) as exc:
            invalid += 1
            if len(findings) < 500:
                messages = (
                    [error["msg"] for error in exc.errors()]
                    if isinstance(exc, ValidationError)
                    else [str(exc)]
                )
                findings.append({"row": number, "status": "invalid", "messages": messages})
    identifier = uuid.uuid4()
    key = f"imports/{identifier}{suffix}"
    path = storage_file(key)
    record = DataImport(
        id=identifier,
        restaurant_id=user.restaurant_id,
        created_by=user.id,
        file_name=original,
        file_type=suffix[1:],
        storage_key=key,
        file_sha256=hashlib.sha256(content).hexdigest(),
        status="applied" if apply and valid else "validated",
        total_rows=len(rows),
        valid_rows=len(valid),
        invalid_rows=invalid,
        unusual_rows=unusual,
        applied_rows=len(valid) if apply else 0,
        validation_results=findings,
    )
    try:
        db.add(record)
        db.flush()
        if apply:
            for value in valid:
                db.add(
                    DailyOperation(
                        restaurant_id=user.restaurant_id,
                        created_by=user.id,
                        updated_by=user.id,
                        source="import",
                        import_id=record.id,
                        **value.model_dump(),
                    )
                )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
        db.commit()
    except Exception:
        db.rollback()
        if path.exists():
            path.unlink()
        raise
    return serialize(record)


@router.get("")
def list_imports(
    db: Db, user: CurrentUser, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)
):
    return [
        serialize(row)
        for row in db.scalars(
            select(DataImport)
            .where(DataImport.restaurant_id == user.restaurant_id)
            .order_by(DataImport.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    ]


@router.get("/{import_id}")
def detail(import_id: uuid.UUID, db: Db, user: CurrentUser):
    return serialize(owned(db, DataImport, import_id, user))


@router.get("/{import_id}/file")
def download(import_id: uuid.UUID, db: Db, user: CurrentUser):
    row = owned(db, DataImport, import_id, user)
    path = storage_file(row.storage_key)
    if not path.exists():
        raise HTTPException(404, "File tidak tersedia.")
    return FileResponse(path, filename=row.file_name)
