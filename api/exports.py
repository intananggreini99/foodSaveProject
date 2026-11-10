"""Ekspor angka aktual dari daily_operations; tidak menggandakan agregat di DB."""

from decimal import Decimal
from xml.sax.saxutils import escape
from sqlalchemy import select
from api.models import DailyOperation, Restaurant
from api.routers.imports import storage_file


def export_rows(db, job):
    query = select(DailyOperation).where(
        DailyOperation.restaurant_id == job.restaurant_id,
        DailyOperation.operation_date >= job.starts_on,
        DailyOperation.operation_date <= job.ends_on,
    )
    if job.waste_category:
        query = query.where(DailyOperation.waste_category == job.waste_category)
    if job.search:
        query = query.where(DailyOperation.manager_notes.ilike("%" + job.search + "%"))
    order = {
        "date_asc": DailyOperation.operation_date.asc(),
        "date_desc": DailyOperation.operation_date.desc(),
        "waste_asc": DailyOperation.actual_waste_kg.asc().nulls_last(),
        "waste_desc": DailyOperation.actual_waste_kg.desc().nulls_last(),
    }
    return db.scalars(query.order_by(order[job.sort_order], DailyOperation.id)).all()


def text_cell(value):
    # Hindari formula aktif saat catatan/nama dari pengguna dibuka di Excel.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_export(db, job):
    rows = export_rows(db, job)
    restaurant = db.get(Restaurant, job.restaurant_id)
    key = f"reports/{job.id}.{job.file_format}"
    path = storage_file(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "Tanggal",
        "Porsi",
        "Staf",
        "Pengalaman staf",
        "Acara khusus",
        "Kategori",
        "Limbah aktual kg",
        "Catatan manager",
    ]
    values = [
        [
            r.operation_date,
            r.meals_prepared,
            r.kitchen_staff,
            r.staff_experience,
            "Ya" if r.special_event else "Tidak",
            r.waste_category,
            r.actual_waste_kg,
            r.manager_notes,
        ]
        for r in rows
    ]
    actuals = [r.actual_waste_kg for r in rows if r.actual_waste_kg is not None]
    total = sum(actuals, Decimal(0)) if actuals else None
    if job.file_format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        book = Workbook()
        sheet = book.active
        sheet.title = "Data operasional"
        sheet.append(headers)
        for row in values:
            sheet.append([text_cell(value) for value in row])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="E5F0E8")
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for letter, width in [
            ("A", 14),
            ("B", 12),
            ("C", 12),
            ("D", 20),
            ("E", 18),
            ("F", 22),
            ("G", 22),
            ("H", 45),
        ]:
            sheet.column_dimensions[letter].width = width
        summary = book.create_sheet("Ringkasan")
        summary.append(["Restoran", text_cell(restaurant.name)])
        summary.append(["Periode", f"{job.starts_on} s.d. {job.ends_on}"])
        summary.append(["Jumlah observasi", len(rows)])
        summary.append(["Limbah aktual diisi", len(actuals)])
        summary.append(["Limbah aktual belum diisi", len(rows) - len(actuals)])
        summary.append(["Total limbah aktual kg", total])
        summary.append(["Catatan", "Data aktual kosong tidak dianggap nol."])
        summary.column_dimensions["A"].width = 32
        summary.column_dimensions["B"].width = 55
        book.save(path)
        book.close()
    else:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        styles = getSampleStyleSheet()
        story = [
            Paragraph("Laporan operasional FoodSave", styles["Title"]),
            Paragraph(escape(restaurant.name), styles["Normal"]),
            Paragraph(f"Periode {job.starts_on} sampai {job.ends_on}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph(
                f"{len(rows)} observasi; {len(actuals)} aktual diisi; {len(rows)-len(actuals)} aktual belum diisi.",
                styles["Normal"],
            ),
            Paragraph(
                f'Total limbah aktual: {total if total is not None else "belum tersedia"} kg.',
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]
        # Catatan panjang tetap lengkap di Excel dan database; PDF memakai tabel ringkas.
        data = [headers[:7]] + [
            [str(v) if v is not None else "Belum diisi" for v in row[:7]] for row in values
        ]
        for row in data:
            for i, value in enumerate(row):
                row[i] = Paragraph(escape(value), styles["Normal"])
        table = Table(data, colWidths=[78, 50, 45, 115, 85, 130, 110], repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5F0E8")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend(
            [
                table,
                Spacer(1, 12),
                Paragraph(
                    "Nilai aktual kosong tidak dianggap nol. Laporan menggambarkan data saat file dibuat.",
                    styles["Normal"],
                ),
            ]
        )
        SimpleDocTemplate(
            str(path),
            pagesize=landscape(A4),
            leftMargin=35,
            rightMargin=35,
            topMargin=30,
            bottomMargin=30,
        ).build(story)
    return key, f"foodsave_{job.starts_on}_{job.ends_on}.{job.file_format}"
