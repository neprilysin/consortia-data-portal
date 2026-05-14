from pathlib import Path
import math
import tempfile
import zipfile
from dataclasses import dataclass

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nmrglue as ng


@dataclass
class SpectrumResult:
    row: int
    integral: float
    peak_index: int
    peak_ppm: float
    spectrum_min: float
    spectrum_max: float


@dataclass
class LogPResult:
    molecule_name: str
    logp: float | None
    raw1_integral: float | None
    raw2_integral: float | None
    raw3_integral: float | None
    raw4_integral: float | None
    figure_path: Path
    notes: str


DEFAULT_EXPECTED_ROWS = 4
DEFAULT_LB = 1.0
DEFAULT_LB_UNIT = "hz"
DEFAULT_P0 = 74.0
DEFAULT_P1 = 0.0
DEFAULT_ZERO_FILL = 32768
DEFAULT_REVERSE = True
DEFAULT_DIGITAL_FILTER = True
DEFAULT_BASELINE = False
DEFAULT_BASELINE_WD = 20


def unzip_if_needed(input_path: Path) -> Path:
    if input_path.suffix.lower() != ".zip":
        return input_path

    tmpdir = Path(tempfile.mkdtemp())

    with zipfile.ZipFile(input_path, "r") as z:
        z.extractall(tmpdir)

    for p in tmpdir.rglob("*"):
        if p.name in {"fid", "ser"}:
            return p.parent

    raise ValueError("No Bruker fid or ser file found inside ZIP.")


def calculate_ppm(dic, npoints):
    sw = float(dic["acqus"]["SW"])
    o1 = float(dic["acqus"]["O1"])
    bf1 = float(dic["acqus"]["BF1"])

    offset = (sw / 2) - (o1 / bf1)
    start = sw - offset
    end = -offset
    step = sw / npoints

    ppm = np.arange(start, end, -step)[:npoints]

    if ppm.size != npoints:
        ppm = np.linspace(start, end, npoints)

    return ppm.astype(np.float64)


def get_acqus_float(dic, key, default=None):
    value = dic.get("acqus", {}).get(key, default)
    try:
        return float(value)
    except Exception:
        return default


def convert_lb_to_point_scale(dic, lb_value: float, lb_unit: str) -> float:
    lb_unit = lb_unit.lower()

    sw_h = get_acqus_float(dic, "SW_h")
    sfo1 = get_acqus_float(dic, "SFO1")

    if lb_unit == "points":
        return lb_value

    if sw_h is None or sw_h <= 0:
        raise ValueError("Cannot convert LB because SW_h was not found in acqus.")

    if lb_unit == "hz":
        lb_hz = lb_value
    elif lb_unit == "ppm":
        if sfo1 is None or sfo1 <= 0:
            raise ValueError("Cannot convert ppm LB because SFO1 was not found in acqus.")
        lb_hz = lb_value * sfo1
    else:
        raise ValueError("Unknown LB unit. Use points, hz, or ppm.")

    return lb_hz / sw_h


def read_pseudo2d_bruker(input_path: Path, expected_rows: int = DEFAULT_EXPECTED_ROWS):
    bruker_dir = unzip_if_needed(input_path)

    dic, data = ng.bruker.read(str(bruker_dir), cplex=True)
    data = np.asarray(data)

    if data.ndim == 1:
        if data.size % expected_rows == 0:
            data = data.reshape(expected_rows, data.size // expected_rows)
        else:
            raise ValueError(
                f"Cannot reshape 1D data of size {data.size} into {expected_rows} rows."
            )

    elif data.ndim == 3:
        data = data[0]

    if data.ndim != 2:
        raise ValueError(f"Expected 2D pseudo-2D data. Got shape: {data.shape}")

    return dic, data


def process_single_fid_std_style(
    fid,
    dic,
    p0: float = DEFAULT_P0,
    p1: float = DEFAULT_P1,
    lb: float = DEFAULT_LB,
    lb_unit: str = DEFAULT_LB_UNIT,
    zero_fill_size: int = DEFAULT_ZERO_FILL,
    remove_digital_filter: bool = DEFAULT_DIGITAL_FILTER,
    reverse: bool = DEFAULT_REVERSE,
    baseline_correct: bool = DEFAULT_BASELINE,
    baseline_wd: int = DEFAULT_BASELINE_WD,
):
    fid = np.asarray(fid)

    if remove_digital_filter:
        try:
            fid = ng.bruker.remove_digital_filter(dic, fid)
        except Exception:
            pass

    lb_points = convert_lb_to_point_scale(dic, lb, lb_unit)

    fid = ng.proc_base.em(fid, lb=lb_points)
    fid = ng.proc_base.zf_size(fid, zero_fill_size)

    spec = ng.proc_base.fft(fid)
    spec = ng.proc_base.ps(spec, p0=p0, p1=p1)
    spec = ng.proc_base.di(spec)

    if reverse:
        spec = ng.proc_base.rev(spec)

    if baseline_correct:
        try:
            spec = ng.proc_bl.baseline_corrector(spec, wd=baseline_wd)
        except Exception:
            pass

    ppm = calculate_ppm(dic, len(spec))

    return spec.astype(np.float64), ppm.astype(np.float64)


def find_main_peak(spectrum):
    y = np.abs(np.asarray(spectrum).flatten())

    if y.size == 0:
        raise ValueError("Spectrum is empty, cannot find peak.")

    return int(np.argmax(y))


def integrate_peak(spectrum, peak_index, half_width_points=30) -> float:
    spectrum = np.asarray(spectrum).flatten()

    if spectrum.size == 0:
        raise ValueError("Spectrum is empty, cannot integrate peak.")

    peak_index = int(np.clip(peak_index, 0, spectrum.size - 1))

    start = max(0, peak_index - half_width_points)
    end = min(spectrum.size, peak_index + half_width_points + 1)

    region = spectrum[start:end]

    if region.size < 2:
        return abs(float(region[0]))

    baseline = np.linspace(region[0], region[-1], region.size)
    corrected = region - baseline

    return abs(float(np.trapz(corrected)))


def plot_combined_spectra(
    spectra,
    ppm_axes,
    results,
    molecule_name,
    output_path,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 8))

    for i, spectrum in enumerate(spectra):
        ppm = ppm_axes[i]

        y = spectrum.copy()
        max_abs = np.max(np.abs(y))

        if max_abs != 0:
            y = y / max_abs

        offset = i * 1.3

        plt.plot(ppm, y + offset, linewidth=1.0)
        plt.axvline(results[i].peak_ppm, linestyle="--", linewidth=0.8)

        plt.text(
            ppm[0],
            offset + 0.75,
            f"RAW{i + 1} integral = {results[i].integral:.3f}",
            fontsize=9,
        )

    plt.title(f"{molecule_name} pseudo-2D spectra")
    plt.xlabel("ppm")
    plt.ylabel("Normalised intensity + offset")
    plt.gca().invert_xaxis()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()


def process_pseudo2d_logp(
    input_path: str | Path,
    molecule_name: str = "CMPD1",
    output_dir: str | Path = "storage/analysis",
    integration_half_width_points: int = 30,
    p0: float = DEFAULT_P0,
    p1: float = DEFAULT_P1,
) -> LogPResult:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dic, raw_data = read_pseudo2d_bruker(input_path)

    rows_to_process = min(raw_data.shape[0], DEFAULT_EXPECTED_ROWS)

    spectra = []
    ppm_axes = []
    results = []

    for i in range(rows_to_process):
        spectrum, ppm = process_single_fid_std_style(
            raw_data[i],
            dic=dic,
            p0=p0,
            p1=p1,
        )

        peak_index = find_main_peak(spectrum)
        peak_ppm = float(ppm[peak_index])

        integral = integrate_peak(
            spectrum,
            peak_index,
            half_width_points=integration_half_width_points,
        )

        result = SpectrumResult(
            row=i + 1,
            integral=integral,
            peak_index=peak_index,
            peak_ppm=peak_ppm,
            spectrum_min=float(np.min(spectrum)),
            spectrum_max=float(np.max(spectrum)),
        )

        spectra.append(spectrum)
        ppm_axes.append(ppm)
        results.append(result)

    raw1 = results[0].integral if len(results) >= 1 else None
    raw2 = results[1].integral if len(results) >= 2 else None
    raw3 = results[2].integral if len(results) >= 3 else None
    raw4 = results[3].integral if len(results) >= 4 else None

    logp = None

    if all(v is not None for v in [raw1, raw2, raw3, raw4]):
        numerator = raw4 + raw1
        denominator = raw2 + raw3

        if denominator > 0:
            logp = math.log10(numerator / denominator)
            notes = "logP calculated successfully."
        else:
            notes = "logP could not be calculated because denominator was zero."
    else:
        notes = "Fewer than four pseudo-2D rows were available. Partial report generated."

    figure_path = (output_dir / f"{molecule_name}_combined_spectra_ppm.png").resolve()

    plot_combined_spectra(
        spectra=spectra,
        ppm_axes=ppm_axes,
        results=results,
        molecule_name=molecule_name,
        output_path=figure_path,
    )

    if not figure_path.exists():
        raise RuntimeError(f"Spectrum figure was not created: {figure_path}")

    return LogPResult(
        molecule_name=molecule_name,
        logp=logp,
        raw1_integral=raw1,
        raw2_integral=raw2,
        raw3_integral=raw3,
        raw4_integral=raw4,
        figure_path=figure_path,
        notes=notes,
    )
