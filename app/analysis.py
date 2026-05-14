from pathlib import Path
import traceback

from .nmr_processing import process_pseudo2d_logp


def fmt(value, decimals: int = 3) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def analyse_file(
    file_path: Path,
    molecule_name: str = "CMPD1",
    p0_phase: float = 74.0,
    p1_phase: float = 0.0,
) -> str:
    try:
        result = process_pseudo2d_logp(
            input_path=file_path,
            molecule_name=molecule_name,
            output_dir="storage/analysis",
            integration_half_width_points=30,
            p0=p0_phase,
            p1=p1_phase,
        )

        logp_text = fmt(result.logp, 3)

        lines = [
            "NMR LOGP ANALYSIS REPORT",
            "=" * 28,
            "",
            f"Molecule: {result.molecule_name}",
            f"Status: {result.notes}",
            "",
            "PROCESSING PARAMETERS",
            "-" * 28,
            f"P0 phase: {fmt(p0_phase)}",
            f"P1 phase: {fmt(p1_phase)}",
            "LB: 1.000 Hz",
            "Zero fill: 32768",
            "",
            "RESULT",
            "-" * 28,
            f"logP: {logp_text}",
            "",
            "RAW INTEGRALS",
            "-" * 28,
            f"RAW1: {fmt(result.raw1_integral)}",
            f"RAW2: {fmt(result.raw2_integral)}",
            f"RAW3: {fmt(result.raw3_integral)}",
            f"RAW4: {fmt(result.raw4_integral)}",
            "",
            "FIGURE",
            "-" * 28,
            f"{result.figure_path}",
        ]

        return "\n".join(lines)

    except Exception as e:
        return (
            "NMR ANALYSIS FAILED\n"
            "===================\n\n"
            f"Error type: {type(e).__name__}\n"
            f"Error message: {e}\n\n"
            "The uploaded file was accepted, but the NMR processing failed.\n"
            "Possible causes include Bruker file structure, pseudo-2D shape handling, or missing acquisition files.\n\n"
            "Full traceback:\n"
            + traceback.format_exc()
        )
