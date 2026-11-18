"""Mixin dan tipe kolom bersama untuk ketiga skema."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

JSON_DATA = JSON().with_variant(JSONB(), "postgresql")
MONEY = Numeric(18, 2)
KG = Numeric(12, 4)

OP = "operational"
PRED = "prediction"
MA = "model_analysis"


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(Identity):
    """Baris milik satu restoran; semua query wajib menyaring restaurant_id."""

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{OP}.restaurants.id", ondelete="RESTRICT"), index=True
    )
