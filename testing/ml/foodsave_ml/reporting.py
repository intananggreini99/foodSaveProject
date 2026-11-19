"""Laporan evaluasi model (XLSX dan PDF) yang disimpan ke HDFS /foodsave/reports/evaluasi."""

from __future__ import annotations

import io
import json
from xml.sax.saxutils import escape

from foodsave_ml.context import PipelineContext

METRIC_LABELS = [("mae", "MAE (kg)"), ("mse", "MSE"), ("rmse", "RMSE (kg)"),
                 ("mape", "MAPE (%)"), ("r2", "R2")]
SCOPE_LABELS = {
    "cv_dev": "Validasi silang (80% data awal)",
    "test": "Test 20% data terakhir",
    "baseline_test": "Pembanding median (test)",
}


def _summary_rows(ctx: PipelineContext) -> list[tuple[str, str]]:
    dev, test = ctx.dev, ctx.test
    return [
        ("Versi model", ctx.version_key),
        ("Algoritma", "Random Forest Regressor"),
        ("Parameter terpilih", json.dumps(ctx.best.params)),
        ("Jumlah pohon", str(ctx.config.n_estimators)),
        ("Baris data dipakai", str(ctx.audit["usable_rows"])),
        ("Data latih/validasi (80%)",
         f"{len(dev)} baris, {dev.date.min().date()} s.d. {dev.date.max().date()}"),
        ("Data test (20%)",
         f"{len(test)} baris, {test.date.min().date()} s.d. {test.date.max().date()}"),
        ("Validasi silang", f"TimeSeriesSplit {ctx.config.cv_folds} lipatan"),
        ("Rentang estimasi", f"± {ctx.interval_radius:.2f} kg (kuantil 90% |error| validasi)"),
        ("Cakupan rentang di test", f"{ctx.evaluation['test']['interval_coverage'] * 100:.1f}%"),
        ("Catatan", "Model produksi dilatih ulang dengan semua data setelah uji ini."),
    ]


def build_xlsx(ctx: PipelineContext) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    header_fill = PatternFill("solid", fgColor="E5F0E8")
    book = Workbook()
    sheet = book.active
    sheet.title = "Ringkasan"
    for label, value in _summary_rows(ctx):
        sheet.append([label, value])
    sheet.append([])
    sheet.append(["Evaluasi", *[label for _, label in METRIC_LABELS], "Baris"])
    for cell in sheet[sheet.max_row]:
        cell.font, cell.fill = Font(bold=True), header_fill
    for scope, values in ctx.evaluation.items():
        sheet.append([SCOPE_LABELS[scope], *[round(values[k], 4) for k, _ in METRIC_LABELS],
                      values["n_rows"]])
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 60

    tuning = book.create_sheet("Optimasi parameter")
    tuning.append(["Trial", "Tahap", "Parameter", "MAE CV", "MSE CV", "RMSE CV", "MAPE CV",
                   "R2 CV", "MAE per lipatan", "Terpilih"])
    for trial in ctx.trials:
        tuning.append([trial.number, trial.stage, json.dumps(trial.params),
                       round(trial.cv["mae"], 4), round(trial.cv["mse"], 4),
                       round(trial.cv["rmse"], 4), round(trial.cv["mape"], 4),
                       round(trial.cv["r2"], 4), ", ".join(map(str, trial.cv["fold_mae"])),
                       "Ya" if trial.is_best else ""])
    tuning.column_dimensions["C"].width = 60

    preds = book.create_sheet("Prediksi test")
    preds.append(["Tanggal", "Aktual (kg)", "Prediksi (kg)", "Error (kg)"])
    for row in ctx.test_predictions.itertuples():
        preds.append([row.date.date(), round(row.actual, 4), round(row.predicted, 4),
                      round(row.actual - row.predicted, 4)])

    factors = book.create_sheet("Faktor berpengaruh")
    factors.append(["Peringkat", "Fitur", "Kenaikan MAE bila diacak (kg)", "Simpangan"])
    for row in ctx.importances.itertuples():
        factors.append([row.rank, row.feature, round(row.importance_mae, 4),
                        round(row.importance_std, 4)])
    for ws in (tuning, preds, factors):
        for cell in ws[1]:
            cell.font, cell.fill = Font(bold=True), header_fill
        ws.freeze_panes = "A2"
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _chart(ctx: PipelineContext):
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors

    frame = ctx.test_predictions.reset_index(drop=True)
    drawing = Drawing(760, 190)
    plot = LinePlot()
    plot.x, plot.y, plot.width, plot.height = 40, 20, 700, 150
    plot.data = [
        [(i, float(v)) for i, v in enumerate(frame.actual)],
        [(i, float(v)) for i, v in enumerate(frame.predicted)],
    ]
    plot.lines[0].strokeColor = colors.HexColor("#4A4A4A")
    plot.lines[0].strokeWidth = 0.8
    plot.lines[1].strokeColor = colors.HexColor("#2E7D4F")
    plot.lines[1].strokeWidth = 1.4
    plot.xValueAxis.visibleLabels = False
    plot.yValueAxis.labels.fontSize = 7
    drawing.add(plot)
    return drawing


def build_pdf(ctx: PipelineContext) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    grid = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5F0E8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])
    story = [
        Paragraph("Laporan evaluasi model FoodSave", styles["Title"]),
        Paragraph(escape(f"Versi {ctx.version_key}"), styles["Normal"]),
        Spacer(1, 8),
    ]
    summary = Table([[Paragraph(escape(a), styles["Normal"]), Paragraph(escape(b), styles["Normal"])]
                     for a, b in _summary_rows(ctx)], colWidths=[200, 540])
    summary.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                 ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    story += [summary, Spacer(1, 10)]

    metric_rows = [["Evaluasi", *[label for _, label in METRIC_LABELS], "Baris"]]
    for scope, values in ctx.evaluation.items():
        metric_rows.append([SCOPE_LABELS[scope], *[f"{values[k]:.3f}" for k, _ in METRIC_LABELS],
                            str(values["n_rows"])])
    metrics_table = Table(metric_rows, hAlign="LEFT")
    metrics_table.setStyle(grid)
    story += [Paragraph("Metrik evaluasi", styles["Heading2"]), metrics_table, Spacer(1, 10)]

    trial_rows = [["Trial", "Tahap", "Parameter", "MAE CV", "RMSE CV", "MAPE CV", "Terpilih"]]
    for trial in ctx.trials:
        trial_rows.append([str(trial.number), trial.stage,
                           Paragraph(escape(json.dumps(trial.params)), styles["Normal"]),
                           f"{trial.cv['mae']:.3f}", f"{trial.cv['rmse']:.3f}",
                           f"{trial.cv['mape']:.2f}", "Ya" if trial.is_best else ""])
    trials_table = Table(trial_rows, colWidths=[35, 55, 330, 60, 60, 60, 50], hAlign="LEFT")
    trials_table.setStyle(grid)
    story += [Paragraph("Optimasi parameter", styles["Heading2"]), trials_table, Spacer(1, 10)]

    story += [Paragraph("Aktual (abu-abu) dan prediksi (hijau) pada data test", styles["Heading2"]),
              _chart(ctx), Spacer(1, 10)]

    factor_rows = [["Peringkat", "Fitur", "Kenaikan MAE bila diacak (kg)"]]
    for row in ctx.importances.head(10).itertuples():
        factor_rows.append([str(row.rank), row.feature, f"{row.importance_mae:.3f}"])
    factors_table = Table(factor_rows, hAlign="LEFT")
    factors_table.setStyle(grid)
    story += [Paragraph("Faktor berpengaruh (10 teratas)", styles["Heading2"]), factors_table]

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=36, rightMargin=36,
                      topMargin=30, bottomMargin=30, title="Laporan evaluasi FoodSave").build(story)
    return buffer.getvalue()
