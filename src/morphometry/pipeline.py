from __future__ import annotations

import hashlib
import json
import math
import re
import warnings
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from skimage import color, exposure, feature, filters, measure, morphology, segmentation, util
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

IMAGE_SUFFIXES = {".tif", ".tiff", ".png"}
PALETTE = {"navy": "#16324F", "blue": "#2F6690", "teal": "#3A7D7C", "gold": "#D9A441", "red": "#B55245", "gray": "#6B7280"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_condition(relative_path: str, is_image: bool = False) -> dict[str, Any]:
    """Parse only source-encoded preparation fields; unknowns remain explicit."""
    s = relative_path.replace("\\", "/")
    low = s.lower()
    top = s.split("/")[0]
    primer = "PUR" if (top == "Figure 6" or "figure s7" in low or "figure s9" in low or "figure s10" in low or "_pur" in low) else (
        "PDMS" if (top in {"Figure 4", "Figure 5"} or "figure s6" in low or "pdms" in low) else "unknown"
    )
    if "binder" in low:
        material = "binder"
    elif "900c" in low or "900 c" in low:
        material = "900C"
    elif "500c" in low or "500 c" in low:
        material = "500C"
    elif "unsintered" in low or "no calcination" in low:
        material = "unsintered"
    else:
        material = "base"
    if "unsieved" in low or "unsiev" in low or "-uns-" in low:
        sieving = "unsieved"
    elif "sieved" in low:
        sieving = "sieved"
    else:
        sieving = "unknown"
    spray_default_folders = {"Figure 3", "Figure 4", "Figure 5", "Figure 6", "Supplementary Figure S7", "Supplementary Figure S9", "Supplementary Figure S10"}
    method = "dip" if "dip" in low else ("spray" if "spray" in low or "coating" in low or top in spray_default_folders else "unknown")
    filename_low = Path(s).name.lower()
    if "abrasion" in filename_low:
        test_type = "abrasion"
    elif "tape" in filename_low:
        test_type = "tape"
    elif ("abrasion" in low) ^ ("tape" in low):
        test_type = "abrasion" if "abrasion" in low else "tape"
    else:
        test_type = "none"
    cycle_matches = re.findall(r"cycle[_ ]?(\d+)", low)
    cycle = int(cycle_matches[-1]) if cycle_matches else None

    # The manuscript-linked folder descriptions identify these post-test images.
    if is_image:
        if top == "Figure 5" and "900c" in low and "sem" in low:
            test_type, cycle = "tape", 5
        elif top == "Figure 5" and "unsintered" in low and "sem" in low:
            test_type, cycle = "tape", 1
        elif top == "Figure 6" and "900c" in low and "failure" in low:
            test_type, cycle = "abrasion", 15
        elif top == "Figure 6" and "binder" in low and "failure" in low:
            test_type, cycle = "tape", 25

    spray_cycle = None
    m = re.search(r"coating[_ ](\d+) spray cycle", low)
    if m:
        spray_cycle = int(m.group(1))

    if "side-view" in low or "side_view" in low:
        view = "side"
    else:
        view = "top"
    if "lotus" in low:
        role = "reference"
    elif "coating" in low:
        role = "coating"
    elif "particle" in low or " sp" in f" {low}" or "sps_" in low:
        role = "particle"
    else:
        role = "other"

    key_parts = [material, primer, sieving, method, test_type, str(cycle) if cycle is not None else "na",
                 f"spray{spray_cycle}" if spray_cycle is not None else "sprayna"]
    return {
        "figure_folder": top,
        "primer": primer,
        "material": material,
        "sieving": sieving,
        "coating_method": method,
        "test_type": test_type,
        "cycle": cycle,
        "spray_cycle": spray_cycle,
        "view": view,
        "image_role": role,
        "condition_key": "|".join(key_parts),
    }


def _manual_calibration(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    table = pd.read_csv(path)
    return {str(r.relative_path).replace("\\", "/"): r._asdict() for r in table.itertuples(index=False)}


def extract_pixel_size_um(image: Image.Image) -> tuple[float | None, str]:
    """Read Zeiss private TIFF metadata. Pixel size is stored in metres."""
    if not hasattr(image, "tag_v2") or 34118 not in image.tag_v2:
        return None, "missing"
    raw = str(image.tag_v2.get(34118, "")).replace("\x00", "")
    numbers = []
    for token in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw):
        try:
            value = float(token)
        except ValueError:
            continue
        if 1e-10 <= value <= 1e-3:
            numbers.append(value)
    if not numbers:
        return None, "missing"
    return numbers[0] * 1e6, "tiff_metadata"


def load_sem(path: Path, manual: dict[str, Any] | None = None) -> tuple[np.ndarray, float | None, str, int]:
    image = Image.open(path)
    pixel_size, source = extract_pixel_size_um(image)
    if pixel_size is None and manual:
        pixel_size = float(manual["pixel_size_um"])
        source = str(manual.get("calibration_source", "manual"))
    gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    h = gray.shape[0]
    crop_y = h
    if path.suffix.lower() in {".tif", ".tiff"}:
        white_fraction = (gray > 0.93).mean(axis=1)
        candidates = np.where((np.arange(h) > int(0.62 * h)) & (white_fraction > 0.43))[0]
        if len(candidates):
            crop_y = int(candidates[0])
    else:
        # Source PNGs embed a scale bar in the bottom band, not TIFF metadata.
        crop_y = max(1, h - 58)
    roi = gray[:crop_y].copy()
    lo, hi = np.percentile(roi, [1, 99])
    roi = exposure.rescale_intensity(roi, in_range=(lo, hi), out_range=(0, 1)).astype(np.float32)
    return roi, pixel_size, source, crop_y


def otsu_value(image: np.ndarray) -> float:
    return float(filters.threshold_otsu(np.asarray(image, dtype=float)))


def segment_classical(image: np.ndarray, threshold_factor: float = 1.0) -> tuple[np.ndarray, np.ndarray, float]:
    smooth = filters.gaussian(image, sigma=1.0, preserve_range=True)
    threshold = float(np.clip(otsu_value(smooth) * threshold_factor, 0.02, 0.98))
    mask = smooth > threshold
    min_size = max(12, int(mask.size * 1.5e-5))
    mask = morphology.remove_small_objects(mask, max_size=min_size - 1)
    mask = morphology.remove_small_holes(mask, max_size=min_size - 1)
    mask = morphology.opening(mask, morphology.disk(1))
    distance = ndi.distance_transform_edt(mask)
    coords = feature.peak_local_max(distance, min_distance=max(2, int(min(image.shape) / 180)), labels=mask)
    markers = np.zeros_like(mask, dtype=np.int32)
    if len(coords):
        markers[tuple(coords.T)] = np.arange(1, len(coords) + 1)
        labels = segmentation.watershed(-distance, markers, mask=mask, compactness=0.001)
    else:
        labels = measure.label(mask)
    labels = morphology.remove_small_objects(labels, max_size=min_size - 1)
    labels = measure.label(labels > 0)
    return mask.astype(bool), labels.astype(np.int32), threshold


def _region_summary(labels: np.ndarray, pixel_size_um: float | None) -> dict[str, float]:
    props = measure.regionprops(labels)
    if not props:
        return {k: np.nan for k in ["object_count", "eq_diameter_median_um", "eq_diameter_iqr_um", "circularity_median", "aspect_ratio_median"]}
    px = pixel_size_um if pixel_size_um and pixel_size_um > 0 else 1.0
    eq = np.asarray([p.equivalent_diameter_area * px for p in props if p.area >= 8], dtype=float)
    circularity = np.asarray([4 * np.pi * p.area / (p.perimeter ** 2) for p in props if p.perimeter > 0 and p.area >= 8])
    aspect = np.asarray([p.axis_major_length / max(p.axis_minor_length, 1e-9) for p in props if p.area >= 8])
    return {
        "object_count": float(len(props)),
        "eq_diameter_median_um": float(np.median(eq)) if len(eq) else np.nan,
        "eq_diameter_iqr_um": float(np.subtract(*np.percentile(eq, [75, 25]))) if len(eq) else np.nan,
        "circularity_median": float(np.median(np.clip(circularity, 0, 1))) if len(circularity) else np.nan,
        "aspect_ratio_median": float(np.median(aspect)) if len(aspect) else np.nan,
    }


def _texture_features(image: np.ndarray, pixel_size_um: float | None) -> dict[str, float]:
    small = util.img_as_ubyte(np.clip(image, 0, 1))
    quantized = np.minimum(small // 32, 7).astype(np.uint8)
    if pixel_size_um and pixel_size_um > 0:
        distances = sorted(set(max(1, min(64, int(round(u / pixel_size_um)))) for u in (1, 5, 20)))
    else:
        distances = [1, 4, 16]
    glcm = feature.graycomatrix(quantized, distances=distances, angles=[0, np.pi / 4], levels=8, symmetric=True, normed=True)
    contrast = feature.graycoprops(glcm, "contrast").mean(axis=1)
    homogeneity = feature.graycoprops(glcm, "homogeneity").mean(axis=1)
    lbp = feature.local_binary_pattern(small, P=8, R=1, method="uniform")
    hist, _ = np.histogram(lbp, bins=np.arange(11), density=True)
    hist = hist[hist > 0]
    out = {
        "texture_glcm_contrast_mean": float(np.mean(contrast)),
        "texture_glcm_homogeneity_mean": float(np.mean(homogeneity)),
        "texture_lbp_entropy": float(-(hist * np.log2(hist)).sum()),
        "texture_laplacian_variance": float(ndi.laplace(image).var()),
    }
    for i, value in enumerate(contrast):
        out[f"texture_contrast_scale_{i+1}"] = float(value)
    return out


def extract_features(image: np.ndarray, mask: np.ndarray, labels: np.ndarray, pixel_size_um: float | None) -> dict[str, float]:
    px = pixel_size_um if pixel_size_um and pixel_size_um > 0 else 1.0
    pore = ~mask
    edges = feature.canny(image, sigma=1.2)
    pore_components = measure.label(pore, connectivity=2)
    centroids = np.asarray([p.centroid for p in measure.regionprops(labels) if p.area >= 8])
    spacing = np.nan
    if len(centroids) >= 2:
        distances, _ = cKDTree(centroids).query(centroids, k=2)
        spacing = float(np.median(distances[:, 1]) * px)
    result = {
        "solid_area_fraction": float(mask.mean()),
        "pore_area_fraction": float(pore.mean()),
        "pore_component_density_per_mm2": float((pore_components.max() / (pore.size * px * px)) * 1e6),
        "pore_euler_density_per_mm2": float((measure.euler_number(pore) / (pore.size * px * px)) * 1e6),
        "edge_density_per_um": float(edges.sum() / (edges.size * px)),
        "nearest_neighbor_spacing_um": spacing,
    }
    result.update(_region_summary(labels, pixel_size_um))
    result.update(_texture_features(image, pixel_size_um))
    return result


def build_image_manifest(data_root: Path, calibration_path: Path) -> tuple[pd.DataFrame, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    manual = _manual_calibration(calibration_path)
    rows: list[dict[str, Any]] = []
    cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    paths = sorted(p for p in data_root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    for path in paths:
        rel = path.relative_to(data_root).as_posix()
        roi, pixel_size, cal_source, crop_y = load_sem(path, manual.get(rel))
        mask, labels, threshold = segment_classical(roi)
        meta = parse_condition(rel, is_image=True)
        rows.append({
            "relative_path": rel,
            "width_px": roi.shape[1], "height_px": roi.shape[0], "crop_y_px": crop_y,
            "pixel_size_um": pixel_size, "calibration_source": cal_source,
            "field_width_um": roi.shape[1] * pixel_size if pixel_size else np.nan,
            "otsu_threshold": threshold,
            **meta,
        })
        cache[rel] = (roi, mask, labels)
    return pd.DataFrame(rows), cache


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"\s*(-?\d+(?:\.\d+)?)", value.replace(",", "."))
        if m:
            return float(m.group(1))
    return None


def _ratio(value: Any) -> float | None:
    if isinstance(value, str):
        m = re.search(r"(\d+)\s*/\s*(\d+)", value)
        if m and int(m.group(2)):
            return int(m.group(1)) / int(m.group(2))
    return None


def parse_property_workbook(path: Path, data_root: Path) -> dict[str, Any] | None:
    rel = path.relative_to(data_root).as_posix()
    if path.name.startswith("._"):
        return None
    try:
        book = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:
        return None
    sheet = book.worksheets[0]
    values = [list(row) for row in sheet.iter_rows(values_only=True)]
    if not values:
        return None
    ca_values: list[float] = []
    ca_summary_values: list[float] = []
    ca_summary_sd_values: list[float] = []
    hyst_values: list[float] = []
    roll_values: list[float] = []
    pin_values: list[float] = []
    ca_summary_row = next(
        (row_index for row_index, row in enumerate(values)
         if any(str(value).strip().lower().startswith("ca/stabw") for value in row if value is not None)),
        len(values),
    )
    for row_index, row in enumerate(values):
        lowrow = [str(v).lower() if v is not None else "" for v in row]
        for i, text in enumerate(lowrow):
            if text.strip().startswith("ca/stabw"):
                numeric_after_label = [_numeric(row[j]) for j in range(i + 1, len(row))]
                numeric_after_label = [value for value in numeric_after_label if value is not None]
                means = [value for value in numeric_after_label if 30 <= value <= 180]
                if means:
                    ca_summary_values.append(means[0])
                    mean_position = numeric_after_label.index(means[0])
                    sd_candidates = [value for value in numeric_after_label[mean_position + 1:] if 0 <= value <= 30]
                    if sd_candidates:
                        ca_summary_sd_values.append(sd_candidates[0])
        method_cols = [i for i, v in enumerate(lowrow) if v.strip() in {"t-1", "t-2"}]
        for i in method_cols:
            candidates = [_numeric(row[j]) for j in range(i + 1, min(i + 4, len(row)))]
            angles = [v for v in candidates if v is not None and 30 <= v <= 180]
            # Rows after the reported CA/Stabw summary are time-series traces for
            # advancing/receding-angle measurements, not independent static CA
            # replicates. Count only the static block above the summary row.
            if row_index < ca_summary_row and len(angles) >= 2:
                ca_values.append(float(np.mean(angles[:2])))
        for i, text in enumerate(lowrow):
            if text.strip().startswith("hysterese:") or text.strip().startswith("hysteresis:"):
                for j in range(i + 1, min(i + 3, len(row))):
                    value = _numeric(row[j])
                    if value is not None and 0 <= value <= 90:
                        hyst_values.append(value); break
            if "pinning fraction" in text:
                for below in values[row_index: row_index + 4]:
                    for j in range(max(0, i - 1), min(len(below), i + 2)):
                        value = _ratio(below[j])
                        if value is not None:
                            pin_values.append(value)
            if "roll-off" in text or "roll off" in text:
                for below in values[row_index: row_index + 4]:
                    for j in range(max(0, i - 1), min(len(below), i + 2)):
                        value = _numeric(below[j])
                        if value is not None and 0 <= value <= 90:
                            roll_values.append(value)
    if not any((ca_values, hyst_values, roll_values, pin_values)):
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    meta = parse_condition(rel, is_image=False)
    return {
        "relative_path": rel, "sha256": digest,
        "contact_angle_deg": float(np.mean(ca_summary_values)) if ca_summary_values else (float(np.mean(ca_values)) if ca_values else np.nan),
        "contact_angle_sd_deg": float(np.mean(ca_summary_sd_values)) if ca_summary_sd_values else (float(np.std(ca_values, ddof=1)) if len(ca_values) > 1 else np.nan),
        "n_contact_angle": len(ca_values),
        "contact_angle_value_source": "reported_CA_Stabw" if ca_summary_values else "computed_static_replicates",
        "hysteresis_deg": float(np.mean(hyst_values)) if hyst_values else np.nan,
        "rolloff_angle_deg": float(np.mean(roll_values)) if roll_values else np.nan,
        "pinning_fraction": float(np.mean(pin_values)) if pin_values else np.nan,
        **meta,
    }


def build_properties(data_root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(data_root.rglob("*.xlsx")):
        parsed = parse_property_workbook(path, data_root)
        if parsed:
            rows.append(parsed)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["duplicate_sha256"] = frame.duplicated("sha256", keep="first")
    return frame.loc[~frame["duplicate_sha256"]].reset_index(drop=True)


FEATURES = [
    "solid_area_fraction", "eq_diameter_median_um", "circularity_median", "aspect_ratio_median",
    "pore_component_density_per_mm2", "edge_density_per_um", "nearest_neighbor_spacing_um",
    "texture_glcm_contrast_mean", "texture_glcm_homogeneity_mean", "texture_lbp_entropy",
    "texture_laplacian_variance",
]
TARGETS = ["contact_angle_deg", "hysteresis_deg", "rolloff_angle_deg", "pinning_fraction"]


def build_morphometry(manifest: pd.DataFrame, cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]) -> pd.DataFrame:
    rows = []
    for record in manifest.to_dict("records"):
        image, mask, labels = cache[record["relative_path"]]
        values = extract_features(image, mask, labels, record.get("pixel_size_um"))
        sensitivity = []
        diameter_sensitivity = []
        for factor in (0.90, 0.95, 1.00, 1.05, 1.10):
            m, lab, _ = segment_classical(image, factor)
            sensitivity.append(float(m.mean()))
            diameter_sensitivity.append(_region_summary(lab, record.get("pixel_size_um"))["eq_diameter_median_um"])
        values.update({
            "solid_fraction_sensitivity_min": float(np.nanmin(sensitivity)),
            "solid_fraction_sensitivity_max": float(np.nanmax(sensitivity)),
            "diameter_sensitivity_min_um": float(np.nanmin(diameter_sensitivity)),
            "diameter_sensitivity_max_um": float(np.nanmax(diameter_sensitivity)),
        })
        sensitivity_width = values["solid_fraction_sensitivity_max"] - values["solid_fraction_sensitivity_min"]
        flags = []
        if not np.isfinite(record.get("pixel_size_um", np.nan)): flags.append("missing_calibration")
        if values["solid_area_fraction"] < 0.05 or values["solid_area_fraction"] > 0.95: flags.append("extreme_area_fraction")
        if values["object_count"] < 3: flags.append("few_objects")
        if sensitivity_width > 0.15: flags.append("threshold_sensitive")
        rows.append({**record, **values, "failure_flags": ";".join(flags), "analysis_inclusion": len(flags) == 0})
    return pd.DataFrame(rows)


def build_modeling_table(morph: pd.DataFrame, properties: pd.DataFrame) -> pd.DataFrame:
    if properties.empty:
        return pd.DataFrame()
    property_agg = properties.groupby("condition_key", as_index=False)[TARGETS].mean()
    eligible = morph[
        (morph["image_role"] == "coating")
        & (morph["view"] == "top")
        & (morph["analysis_inclusion"])
    ].copy()
    return eligible.merge(property_agg, on="condition_key", how="inner", suffixes=("", "_property"))


def evaluate_models(modeling: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries, predictions = [], []
    if modeling.empty:
        return pd.DataFrame(), pd.DataFrame()
    for target in TARGETS:
        subset = modeling.loc[modeling[target].notna()].copy()
        groups = subset["condition_key"].astype(str).to_numpy()
        n_groups = len(np.unique(groups))
        if len(subset) < 6 or n_groups < 4:
            continue
        X = subset[FEATURES]
        y = subset[target].to_numpy(float)
        cv = GroupKFold(n_splits=min(5, n_groups))
        models = {
            "Ridge": TransformedTargetRegressor(
                regressor=Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", Ridge(alpha=100.0))]),
                transformer=StandardScaler(),
            ),
            "Random Forest": Pipeline([("impute", SimpleImputer(strategy="median")), ("model", RandomForestRegressor(n_estimators=400, min_samples_leaf=2, max_features=0.7, random_state=seed))]),
        }
        for name, model in models.items():
            pred = np.full(len(subset), np.nan)
            for train, test in cv.split(X, y, groups):
                model.fit(X.iloc[train], y[train])
                pred[test] = model.predict(X.iloc[test])
            mae = mean_absolute_error(y, pred)
            iqr = float(np.subtract(*np.percentile(y, [75, 25])))
            summaries.append({"target": target, "model": name, "n_images": len(subset), "n_groups": n_groups,
                              "mae": mae, "normalized_mae_iqr": mae / max(iqr, 1e-9),
                              "r2_oof": r2_score(y, pred) if len(y) >= 3 else np.nan})
            for i, value in enumerate(pred):
                predictions.append({"target": target, "model": name, "condition_key": groups[i], "observed": y[i], "predicted": value})
    return pd.DataFrame(summaries), pd.DataFrame(predictions)


def bootstrap_associations(modeling: pd.DataFrame, seed: int, n_boot: int = 1000) -> pd.DataFrame:
    if modeling.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    condition = modeling.groupby("condition_key", as_index=False)[FEATURES + TARGETS].mean(numeric_only=True)
    rows = []
    for target in TARGETS:
        valid_target = condition[target].notna()
        for feat in FEATURES:
            valid = valid_target & condition[feat].notna()
            data = condition.loc[valid, [feat, target]].to_numpy(float)
            if len(data) < 5 or np.unique(data[:, 0]).size < 3:
                continue
            rho = spearmanr(data[:, 0], data[:, 1]).statistic
            boot = []
            for _ in range(n_boot):
                sample = data[rng.integers(0, len(data), len(data))]
                if np.unique(sample[:, 0]).size >= 2 and np.unique(sample[:, 1]).size >= 2:
                    boot.append(spearmanr(sample[:, 0], sample[:, 1]).statistic)
            rows.append({"target": target, "feature": feat, "n_conditions": len(data), "spearman_rho": rho,
                         "ci_low": float(np.nanpercentile(boot, 2.5)) if boot else np.nan,
                         "ci_high": float(np.nanpercentile(boot, 97.5)) if boot else np.nan})
    return pd.DataFrame(rows)


def magnification_consistency(morph: pd.DataFrame) -> pd.DataFrame:
    rows = []
    coating = morph[morph["image_role"] == "coating"]
    for key, group in coating.groupby("condition_key"):
        if len(group) < 2 or group["field_width_um"].nunique() < 2:
            continue
        ordered = group.sort_values("field_width_um")
        for feat in FEATURES:
            values = ordered[feat].dropna()
            if len(values) >= 2:
                rows.append({"condition_key": key, "feature": feat, "small_field_value": values.iloc[0], "large_field_value": values.iloc[-1],
                             "relative_difference": abs(values.iloc[-1] - values.iloc[0]) / (abs(values.mean()) + 1e-12)})
    return pd.DataFrame(rows)


def _savefig(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_figures(output_root: Path, manifest: pd.DataFrame, morph: pd.DataFrame, properties: pd.DataFrame,
                 cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], models: pd.DataFrame,
                 consistency: pd.DataFrame) -> list[Path]:
    figdir = output_root / "figures"; figdir.mkdir(parents=True, exist_ok=True)
    paths = []
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold"})

    # Figure 1: transparent dataset audit.
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.1))
    counts = manifest["image_role"].value_counts().reindex(["coating", "particle", "reference", "other"]).fillna(0)
    axes[0].bar(counts.index, counts.values, color=[PALETTE["blue"], PALETTE["teal"], PALETTE["gold"], PALETTE["gray"]])
    axes[0].set_ylabel("Image count"); axes[0].set_title("A. SEM inventory by analytical role")
    for i, v in enumerate(counts.values): axes[0].text(i, v + .2, str(int(v)), ha="center")
    cal = manifest.dropna(subset=["pixel_size_um"])
    for role, g in cal.groupby("image_role"):
        axes[1].scatter(g["field_width_um"], g["pixel_size_um"], label=role, s=50, alpha=.8)
    axes[1].set_xscale("log"); axes[1].set_yscale("log"); axes[1].set_xlabel("Calibrated field width (µm)"); axes[1].set_ylabel("Pixel size (µm/px)")
    axes[1].set_title("B. Physical scale coverage"); axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Dataset audit: image count is not the independent sample count", fontsize=13, fontweight="bold")
    p = figdir / "figure_1_dataset_audit.png"; _savefig(fig, p); paths.append(p)

    # Figure 2: segmentation comparison plus honest U-Net gate.
    preferred = [k for k in cache if "Coating top-view SEM.tif" in k]
    rel = preferred[0] if preferred else next(iter(cache))
    image, mask, labels = cache[rel]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.5))
    axes[0].imshow(image, cmap="gray"); axes[0].set_title("Raw calibrated ROI")
    axes[1].imshow(mask, cmap="gray"); axes[1].set_title("Otsu + morphology")
    axes[2].imshow(np.clip(color.label2rgb(labels, image=image, bg_label=0, alpha=.45), 0, 1)); axes[2].set_title(f"Watershed: {labels.max()} objects")
    axes[3].axis("off"); axes[3].text(.5, .63, "U-Net comparison gated", ha="center", fontsize=13, fontweight="bold", color=PALETTE["red"])
    axes[3].text(.5, .42, "0 expert masks in source archive\nDice / IoU not estimable\nAnnotation protocol included", ha="center", va="center", fontsize=10)
    for ax in axes[:3]: ax.axis("off")
    fig.suptitle("Segmentation methods and validation status", fontsize=13, fontweight="bold")
    p = figdir / "figure_2_segmentation_comparison.png"; _savefig(fig, p); paths.append(p)

    # Figure 3: coating feature map.
    coat = morph[(morph["image_role"] == "coating") & morph["analysis_inclusion"]].copy()
    show_features = [f for f in FEATURES if f in coat and coat[f].notna().sum() >= 3][:9]
    if len(coat) and show_features:
        z = coat[show_features].apply(lambda x: (x - x.mean()) / (x.std(ddof=0) + 1e-12)).clip(-2.5, 2.5)
        labels_y = [Path(x).stem[:28] for x in coat["relative_path"]]
        fig, ax = plt.subplots(figsize=(11, max(4.8, .31 * len(coat))))
        im = ax.imshow(z.to_numpy(), aspect="auto", cmap="coolwarm", vmin=-2.5, vmax=2.5)
        ax.set_xticks(range(len(show_features)), [_slug(x).replace("_", " ") for x in show_features], rotation=48, ha="right", fontsize=8)
        ax.set_yticks(range(len(labels_y)), labels_y, fontsize=7); ax.set_title("Condition-resolved morphology (column z-scores)")
        fig.colorbar(im, ax=ax, label="z score", shrink=.75)
    else:
        fig, ax = plt.subplots(figsize=(10, 4)); ax.text(.5, .5, "No coating feature rows passed QC", ha="center"); ax.axis("off")
    p = figdir / "figure_3_morphology_feature_map.png"; _savefig(fig, p); paths.append(p)

    # Figure 4: durability curves.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=False)
    durable = properties[(properties["cycle"].notna()) & properties["contact_angle_deg"].notna()].copy()
    durable["series"] = durable["primer"] + " / " + durable["material"] + " / " + durable["test_type"]
    ranked = durable.groupby("series")["cycle"].count().sort_values(ascending=False).head(7).index
    for name, g in durable[durable["series"].isin(ranked)].groupby("series"):
        summary = g.groupby("cycle", as_index=False).agg(contact_angle_deg=("contact_angle_deg", "mean"), hysteresis_deg=("hysteresis_deg", "mean"))
        axes[0].plot(summary["cycle"], summary["contact_angle_deg"], marker="o", ms=3, label=name)
        axes[1].plot(summary["cycle"], summary["hysteresis_deg"], marker="o", ms=3, label=name)
    axes[0].set_title("A. Contact angle retention"); axes[0].set_ylabel("Contact angle (°)")
    axes[1].set_title("B. Hysteresis evolution"); axes[1].set_ylabel("Hysteresis (°)")
    for ax in axes: ax.set_xlabel("Test cycle"); ax.grid(alpha=.2)
    axes[1].legend(frameon=False, fontsize=6, bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.suptitle("Wetting durability is a trajectory, not a single label", fontsize=13, fontweight="bold")
    p = figdir / "figure_4_wetting_durability.png"; _savefig(fig, p); paths.append(p)

    # Figure 5: grouped model results and robustness diagnostics.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    if not models.empty:
        pivot = models.pivot(index="target", columns="model", values="normalized_mae_iqr")
        pivot.plot(kind="bar", ax=axes[0], color=[PALETTE["blue"], PALETTE["gold"]])
        axes[0].set_yscale("log"); axes[0].axhline(1.0, color=PALETTE["gray"], ls="--", lw=1, label="target IQR")
        axes[0].set_ylabel("Grouped OOF MAE / target IQR (log)"); axes[0].set_xlabel(""); axes[0].tick_params(axis="x", rotation=25); axes[0].legend(frameon=False)
    else:
        axes[0].text(.5, .55, "Model score withheld", ha="center", fontsize=13, fontweight="bold", color=PALETTE["red"])
        axes[0].text(.5, .38, "Fewer than 4 independent\nmatched condition groups", ha="center"); axes[0].axis("off")
    sensitivity = morph["solid_fraction_sensitivity_max"] - morph["solid_fraction_sensitivity_min"]
    axes[1].hist(sensitivity.dropna(), bins=10, color=PALETTE["teal"], alpha=.85, label="threshold span")
    if not consistency.empty:
        med = consistency["relative_difference"].median()
        axes[1].axvline(med, color=PALETTE["gold"], lw=2, label=f"median cross-mag Δ={med:.2f}")
    axes[1].set_xlabel("Relative / absolute robustness deviation"); axes[1].set_ylabel("Image count")
    axes[1].set_title("B. Threshold and magnification robustness"); axes[1].legend(frameon=False, fontsize=8)
    axes[0].set_title("A. Leakage-safe predictive evaluation")
    fig.suptitle("Small-data modeling: report uncertainty before accuracy", fontsize=13, fontweight="bold")
    p = figdir / "figure_5_models_and_robustness.png"; _savefig(fig, p); paths.append(p)
    return paths


def run_pipeline(data_root: Path, output_root: Path, calibration_path: Path, seed: int = 20260829) -> None:
    data_root, output_root = Path(data_root), Path(output_root)
    if not data_root.exists():
        raise FileNotFoundError(f"Dataset not found: {data_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest, cache = build_image_manifest(data_root, calibration_path)
    manifest.to_csv(output_root / "image_manifest.csv", index=False)
    properties = build_properties(data_root)
    properties.to_csv(output_root / "properties_clean.csv", index=False)
    morph = build_morphometry(manifest, cache)
    morph.to_csv(output_root / "morphometry_features.csv", index=False)
    morph.loc[morph["failure_flags"].astype(bool)].to_csv(output_root / "failure_cases.csv", index=False)
    modeling = build_modeling_table(morph, properties)
    modeling.to_csv(output_root / "modeling_dataset.csv", index=False)
    models, predictions = evaluate_models(modeling, seed)
    models.to_csv(output_root / "model_results.csv", index=False)
    predictions.to_csv(output_root / "oof_predictions.csv", index=False)
    bootstrap = bootstrap_associations(modeling, seed)
    bootstrap.to_csv(output_root / "bootstrap_intervals.csv", index=False)
    consistency = magnification_consistency(morph)
    consistency.to_csv(output_root / "magnification_consistency.csv", index=False)
    figures = make_figures(output_root, manifest, morph, properties, cache, models, consistency)
    summary = {
        "images_total": int(len(manifest)),
        "coating_images": int((manifest.image_role == "coating").sum()),
        "calibrated_images": int(manifest.pixel_size_um.notna().sum()),
        "unique_property_workbooks": int(len(properties)),
        "matched_modeling_images": int(len(modeling)),
        "matched_condition_groups": int(modeling.condition_key.nunique()) if not modeling.empty else 0,
        "failure_cases": int(morph.failure_flags.astype(bool).sum()),
        "unet_reference_masks": 0,
        "figure_files": [p.name for p in figures],
    }
    (output_root / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
