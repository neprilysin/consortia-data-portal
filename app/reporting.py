from datetime import datetime
from pathlib import Path
import re
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


LEFT = 60
RIGHT = 60
TOP = 70
BOTTOM = 70


def _fmt(value, decimals: int = 3) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def _draw_wrapped_text(
    c,
    text,
    x,
    y,
    max_chars=95,
    line_height=14,
    font="Helvetica",
    size=10,
):
    c.setFont(font, size)

    for raw_line in str(text).splitlines():
        if not raw_line.strip():
            y -= line_height
            continue

        wrapped = textwrap.wrap(raw_line, width=max_chars) or [raw_line]

        for line in wrapped:
            if y < BOTTOM:
                c.showPage()
                y = A4[1] - TOP
                c.setFont(font, size)

            c.drawString(x, y, line)
            y -= line_height

    return y


def _draw_key_value_block(c, items, x, y, label_width=120, line_height=16):
    for label, value in items:
        if value is None or str(value).strip() == "":
            continue

        if y < BOTTOM:
            c.showPage()
            y = A4[1] - TOP

        c.setFont("Helvetica-Bold", 9)
        c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica", 9)
        c.drawString(x + label_width, y, str(value))
        y -= line_height

    return y


def _extract_figure_path(analysis_summary: str) -> Path | None:
    match = re.search(r"^FIGURE\s*\n[-=]+\s*\n(.+)$", analysis_summary, re.MULTILINE)
    if match:
        candidate = Path(match.group(1).strip())
        if candidate.exists():
            return candidate

    match = re.search(r"^Figure:\s*(.+)$", analysis_summary, re.MULTILINE)
    if match:
        candidate = Path(match.group(1).strip())
        if candidate.exists():
            return candidate

    return None


def _clean_analysis_summary(analysis_summary: str) -> str:
    cleaned = re.sub(
        r"\n?FIGURE\s*\n[-=]+\s*\n.+",
        "",
        analysis_summary,
        flags=re.MULTILINE,
    )
    cleaned = re.sub(
        r"\n?Figure:\s*.+",
        "",
        cleaned,
        flags=re.MULTILINE,
    )
    return cleaned.strip()


def _draw_image(c, image_path: Path, x, y, max_width, max_height):
    img = ImageReader(str(image_path))
    img_width, img_height = img.getSize()

    scale = min(max_width / img_width, max_height / img_height)
    draw_width = img_width * scale
    draw_height = img_height * scale

    if y - draw_height < BOTTOM:
        c.showPage()
        y = A4[1] - TOP

    c.drawImage(
        str(image_path),
        x,
        y - draw_height,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )

    return y - draw_height - 20


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

    c.setFont("Helvetica-Bold", 18)
    c.drawString(LEFT, y, "Certified Data Analysis Report")

    y -= 35

    metadata = [
        ("Certificate ID", certificate_id),
        ("Submission ID", submission_id),
        ("Submitted by", user_email),
        ("Original file", original_filename),
        ("Issued at", f"{datetime.utcnow().isoformat(timespec='seconds')} UTC"),
    ]

    y = _draw_key_value_block(c, metadata, LEFT, y, label_width=110)

    y -= 12
    c.setFont("Helvetica-Bold", 12)
    c.drawString(LEFT, y, "Submission Metadata")
    y -= 20

    submission_metadata = [
        ("Lab", lab_name),
        ("Project", project_name),
        ("Molecule", molecule_name),
        ("Experiment", experiment_type),
        ("Instrument", instrument),
        ("P0 phase", _fmt(p0_phase)),
        ("P1 phase", _fmt(p1_phase)),
    ]

    y = _draw_key_value_block(c, submission_metadata, LEFT, y, label_width=110)

    if notes:
        y -= 5
        c.setFont("Helvetica-Bold", 9)
        c.drawString(LEFT, y, "Notes:")
        y -= 14
        y = _draw_wrapped_text(
            c,
            notes,
            LEFT,
            y,
            max_chars=90,
            line_height=12,
            font="Helvetica",
            size=9,
        )

    y -= 15
    c.setFont("Helvetica-Bold", 12)
    c.drawString(LEFT, y, "Dataset SHA-256 Hash")

    y -= 18
    y = _draw_wrapped_text(
        c,
        file_hash,
        LEFT,
        y,
        max_chars=95,
        line_height=11,
        font="Helvetica",
        size=8,
    )

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(LEFT, y, "Analysis Summary")

    y -= 20

    figure_path = _extract_figure_path(analysis_summary)
    cleaned_summary = _clean_analysis_summary(analysis_summary)

    y = _draw_wrapped_text(
        c,
        cleaned_summary,
        LEFT,
        y,
        max_chars=88,
        line_height=14,
        font="Helvetica",
        size=10,
    )

    if figure_path is not None and figure_path.exists():
        y -= 15

        if y < 280:
            c.showPage()
            y = height - TOP

        c.setFont("Helvetica-Bold", 12)
        c.drawString(LEFT, y, "Processed NMR Spectra")
        y -= 15

        y = _draw_image(
            c,
            figure_path,
            LEFT,
            y,
            max_width=width - LEFT - RIGHT,
            max_height=360,
        )

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        LEFT,
        45,
        "This MVP report is not legally certified until proper signatures and governance are added.",
    )

    c.save()
