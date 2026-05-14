from datetime import datetime
from pathlib import Path
import re
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib import colors


LEFT = 54
RIGHT = 54
TOP = 54
BOTTOM = 54


def _fmt(value, decimals: int = 3) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def _extract_value(label: str, text: str) -> str | None:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_figure_path(analysis_summary: str) -> Path | None:
    match = re.search(r"^FIGURE\s*\n[-=]+\s*\n(.+)$", analysis_summary, re.MULTILINE)
    if match:
        p = Path(match.group(1).strip())
        return p if p.exists() else None
    match = re.search(r"^Figure:\s*(.+)$", analysis_summary, re.MULTILINE)
    if match:
        p = Path(match.group(1).strip())
        return p if p.exists() else None
    return None


def _draw_footer(c, width):
    c.setStrokeColor(colors.HexColor("#d1d5db"))
    c.line(LEFT, 42, width - RIGHT, 42)
    c.setFillColor(colors.HexColor("#6b7280"))
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(
        LEFT,
        28,
        "This MVP report is not legally certified until proper signatures and governance are added.",
    )
    c.setFillColor(colors.black)


def _new_page(c, width, height):
    c.showPage()
    _draw_footer(c, width)
    return height - TOP


def _section_title(c, title, y):
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(LEFT, y, title)
    y -= 6
    c.setStrokeColor(colors.HexColor("#2563eb"))
    c.setLineWidth(1.2)
    c.line(LEFT, y, LEFT + 170, y)
    c.setFillColor(colors.black)
    return y - 18


def _wrapped(c, text, x, y, width_chars=92, size=9, leading=12):
    c.setFont("Helvetica", size)
    for raw in str(text).splitlines():
        if not raw.strip():
            y -= leading
            continue
        for line in textwrap.wrap(raw, width=width_chars):
            if y < BOTTOM + 30:
                y = _new_page(c, A4[0], A4[1])
                c.setFont("Helvetica", size)
            c.drawString(x, y, line)
            y -= leading
    return y


def _key_values(c, items, x, y, label_w=105, value_w_chars=52, size=9, leading=15):
    for label, value in items:
        if value is None or str(value).strip() == "":
            continue
        if y < BOTTOM + 30:
            y = _new_page(c, A4[0], A4[1])

        c.setFont("Helvetica-Bold", size)
        c.setFillColor(colors.HexColor("#374151"))
        c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica", size)
        c.setFillColor(colors.HexColor("#111827"))

        value = str(value)
        lines = textwrap.wrap(value, width=value_w_chars) or [value]
        c.drawString(x + label_w, y, lines[0])
        y -= leading

        for extra in lines[1:]:
            c.drawString(x + label_w, y, extra)
            y -= leading

    c.setFillColor(colors.black)
    return y


def _card(c, x, y, w, h, fill="#f9fafb", stroke="#e5e7eb"):
    c.setFillColor(colors.HexColor(fill))
    c.setStrokeColor(colors.HexColor(stroke))
    c.roundRect(x, y - h, w, h, 8, fill=1, stroke=1)
    c.setFillColor(colors.black)


def _draw_integrals_table(c, rows, x, y):
    col_w = [70, 135, 100]
    row_h = 20
    table_w = sum(col_w)

    c.setFillColor(colors.HexColor("#eff6ff"))
    c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 8.5)
    headers = ["RAW", "Integral", "Role"]
    cx = x
    for i, h in enumerate(headers):
        c.drawString(cx + 6, y - 14, h)
        cx += col_w[i]

    y -= row_h
    c.setFont("Helvetica", 8.5)

    for raw, value, role in rows:
        c.setStrokeColor(colors.HexColor("#e5e7eb"))
        c.rect(x, y - row_h, table_w, row_h, fill=0, stroke=1)

        c.setFillColor(colors.HexColor("#111827"))
        c.drawString(x + 6, y - 14, raw)
        c.drawRightString(x + col_w[0] + col_w[1] - 8, y - 14, _fmt(value))
        c.drawString(x + col_w[0] + col_w[1] + 6, y - 14, role)

        y -= row_h

    return y - 10


def _draw_image(c, image_path: Path, x, y, max_width, max_height):
    img = ImageReader(str(image_path))
    iw, ih = img.getSize()
    scale = min(max_width / iw, max_height / ih)
    dw = iw * scale
    dh = ih * scale

    if y - dh < BOTTOM + 30:
        y = _new_page(c, A4[0], A4[1])

    c.drawImage(
        str(image_path),
        x,
        y - dh,
        width=dw,
        height=dh,
        preserveAspectRatio=True,
        mask="auto",
    )
    return y - dh - 18


def generate_report(
    output_path: Path,
    submission_id: int,
    user_email: str,
    original_filename: str,
    file_hash: str,
    analysis_summary: str,
    certificate_id: str,
    lab_name: str = "",
    project_name: str = "",
    molecule_name: str = "",
    experiment_type: str = "",
    instrument: str = "",
    notes: str = "",
    p0_phase: float | None = None,
    p1_phase: float | None = None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    y = height - TOP

    _draw_footer(c, width)

    # Header
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(LEFT, y, "Certified Data Analysis Report")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(LEFT, y - 16, "Consortia Data Portal - NMR logP analysis")
    c.setFillColor(colors.black)

    c.setFillColor(colors.HexColor("#dbeafe"))
    c.roundRect(width - RIGHT - 150, y - 26, 150, 26, 7, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1e3a8a"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(width - RIGHT - 75, y - 17, "REPORT READY")
    c.setFillColor(colors.black)

    y -= 52

    # Result card
    logp = _extract_value("logP", analysis_summary)
    status = _extract_value("Status", analysis_summary) or "Analysis completed"

    _card(c, LEFT, y, width - LEFT - RIGHT, 62, fill="#f8fafc", stroke="#cbd5e1")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(LEFT + 18, y - 20, "PRIMARY RESULT")
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(LEFT + 18, y - 48, f"logP = {logp or 'N/A'}")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawRightString(width - RIGHT - 18, y - 35, status)
    c.setFillColor(colors.black)

    y -= 84

    # Submission metadata
    y = _section_title(c, "Submission metadata", y)
    metadata = [
        ("Certificate ID", certificate_id),
        ("Submission ID", submission_id),
        ("Submitted by", user_email),
        ("Original file", original_filename),
        ("Issued at", f"{datetime.utcnow().isoformat(timespec='seconds')} UTC"),
        ("Lab", lab_name),
        ("Project", project_name),
        ("Molecule", molecule_name),
        ("Experiment", experiment_type),
        ("Instrument", instrument),
    ]
    y = _key_values(c, metadata, LEFT, y, label_w=105, value_w_chars=70)

    # Processing params
    y -= 8
    y = _section_title(c, "Processing parameters", y)
    params = [
        ("P0 phase", _fmt(p0_phase)),
        ("P1 phase", _fmt(p1_phase)),
        ("LB", "1.000 Hz"),
        ("Zero fill", "32768"),
    ]
    y = _key_values(c, params, LEFT, y, label_w=105, value_w_chars=70)

    # Integrals
    raw1 = _extract_value("RAW1", analysis_summary)
    raw2 = _extract_value("RAW2", analysis_summary)
    raw3 = _extract_value("RAW3", analysis_summary)
    raw4 = _extract_value("RAW4", analysis_summary)

    y -= 8
    y = _section_title(c, "Raw integrals", y)
    y = _draw_integrals_table(
        c,
        [
            ("RAW1", raw1, "Octanol phase"),
            ("RAW2", raw2, "Water phase"),
            ("RAW3", raw3, "Water phase"),
            ("RAW4", raw4, "Octanol phase"),
        ],
        LEFT,
        y,
    )

    # Notes
    if notes:
        y -= 4
        y = _section_title(c, "Submission notes", y)
        y = _wrapped(c, notes, LEFT, y, width_chars=90, size=9, leading=12)

    # Hash
    y -= 8
    y = _section_title(c, "Dataset SHA-256 hash", y)
    c.setFont("Courier", 7.5)
    y = _wrapped(c, file_hash, LEFT, y, width_chars=86, size=7.5, leading=10)

    # Spectra
    figure_path = _extract_figure_path(analysis_summary)
    if figure_path is not None and figure_path.exists():
        y -= 14
        y = _section_title(c, "Processed NMR spectra", y)
        y = _draw_image(
            c,
            figure_path,
            LEFT,
            y,
            max_width=width - LEFT - RIGHT,
            max_height=365,
        )

    c.save()
