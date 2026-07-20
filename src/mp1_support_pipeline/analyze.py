"""Step 5: Analysis and visualization.

This script aggregates Step 1-4 artifacts into segment-level metrics, agreement
diagnostics, trace records, and chart PNGs.

Inputs:
    data/raw/generated_baseline.jsonl
    data/validated/validated_baseline.jsonl
    logs/quality_gate_baseline.jsonl
    data/reports/quality_gate_baseline.json
    data/labels/human_labels_baseline.jsonl
    data/labels/llm_judge_labels_baseline.jsonl

Outputs:
    data/reports/analysis_<artifact_variant>_<run_id>.json
    data/reports/trace_records_<artifact_variant>_<run_id>.jsonl
    logs/analysis_<artifact_variant>_<run_id>.jsonl
    visualizations/<artifact_variant>_<run_id>_*.png
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from mp1_support_pipeline.artifacts import artifact_filename, artifact_slug, default_run_id
from mp1_support_pipeline.config import (
    CATEGORIES,
    LABELS_DIR,
    LOGS_DIR,
    QUALITY_DIMENSIONS,
    RAW_DIR,
    REPORTS_DIR,
    VALIDATED_DIR,
    VISUALIZATIONS_DIR,
)
from mp1_support_pipeline.models import GeneratedRecord, GateResult, QualityLabel, TraceRecord


DEFAULT_RAW_FILENAME = "generated_baseline.jsonl"
DEFAULT_VALIDATED_FILENAME = "validated_baseline.jsonl"
DEFAULT_GATE_LOG_FILENAME = "quality_gate_baseline.jsonl"
DEFAULT_GATE_REPORT_FILENAME = "quality_gate_baseline.json"
DEFAULT_HUMAN_LABELS_FILENAME = "human_labels_baseline.jsonl"
DEFAULT_JUDGE_LABELS_FILENAME = "llm_judge_labels_baseline.jsonl"
AGREEMENT_THRESHOLD = 0.80


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object. Missing optional reports are treated as empty."""
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a pretty JSON object."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows. Missing optional files are treated as empty."""
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc

    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one JSONL row."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ensure_output_dirs() -> None:
    """Create analysis output directories."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    VISUALIZATIONS_DIR.mkdir(parents=True, exist_ok=True)


def infer_artifact_variant(
    generated_records: dict[str, GeneratedRecord],
    judge_labels: dict[str, QualityLabel],
) -> str:
    """Infer the Step 5 artifact variant from generator and judge versions."""
    generator_variants = {
        artifact_slug(record.prompt_variant)
        for record in generated_records.values()
        if record.prompt_variant
    }
    judge_prompt_versions = {
        artifact_slug(label.judge_prompt_version or "unknown")
        for label in judge_labels.values()
    }

    generator_part = (
        next(iter(generator_variants)) if len(generator_variants) == 1 else "mixed"
    )
    judge_part = (
        next(iter(judge_prompt_versions)) if len(judge_prompt_versions) == 1 else "mixed"
    )

    return f"generator-{generator_part}_judge-{judge_part}"


def load_generated_records(path: Path) -> dict[str, GeneratedRecord]:
    """Load generated records keyed by trace_id."""
    records: dict[str, GeneratedRecord] = {}

    for row in read_jsonl(path):
        record = GeneratedRecord.model_validate(row)
        records[record.trace_id] = record

    return records


def load_gate_results(path: Path) -> dict[str, GateResult]:
    """Load Step 2 gate results keyed by trace_id."""
    results: dict[str, GateResult] = {}

    for row in read_jsonl(path):
        if "trace_id" not in row:
            continue

        results[str(row["trace_id"])] = GateResult(
            trace_id=str(row["trace_id"]),
            passed=bool(row.get("passed", False)),
            failed_checks=list(row.get("failed_checks", [])),
            timestamp=row.get("timestamp", datetime.now().isoformat()),
        )

    return results


def load_quality_labels(path: Path, labeler: str) -> dict[str, QualityLabel]:
    """Load quality labels for one labeler keyed by trace_id."""
    labels: dict[str, QualityLabel] = {}

    for row in read_jsonl(path):
        label = QualityLabel.model_validate(row)

        if label.labeler == labeler:
            labels[label.trace_id] = label

    return labels


def assemble_trace_records(
    generated_records: dict[str, GeneratedRecord],
    gate_results: dict[str, GateResult],
    human_labels: dict[str, QualityLabel],
    judge_labels: dict[str, QualityLabel],
) -> list[TraceRecord]:
    """Assemble per-item trace records across Steps 1-4."""
    trace_ids = sorted(
        set(generated_records)
        | set(gate_results)
        | set(human_labels)
        | set(judge_labels)
    )

    return [
        TraceRecord(
            trace_id=trace_id,
            generated=generated_records.get(trace_id),
            gate_result=gate_results.get(trace_id),
            human_label=human_labels.get(trace_id),
            judge_label=judge_labels.get(trace_id),
        )
        for trace_id in trace_ids
    ]


def label_pass_rates(labels: dict[str, QualityLabel]) -> dict[str, Any]:
    """Compute dimension pass rates for one labeler."""
    total = len(labels)
    rates: dict[str, Any] = {}

    for dimension in QUALITY_DIMENSIONS:
        passed = sum(getattr(label, dimension) for label in labels.values())
        rates[dimension] = {
            "pass_count": passed,
            "total": total,
            "pass_rate": round(passed / total, 4) if total else None,
        }

    overall_passed = sum(1 for label in labels.values() if label.overall_pass)
    rates["overall_pass"] = {
        "pass_count": overall_passed,
        "total": total,
        "pass_rate": round(overall_passed / total, 4) if total else None,
    }

    return rates


def agreement_metrics(
    human_labels: dict[str, QualityLabel],
    judge_labels: dict[str, QualityLabel],
) -> dict[str, Any]:
    """Compute human/LLM judge agreement on overlapping trace IDs."""
    overlap_trace_ids = sorted(set(human_labels) & set(judge_labels))
    agreement_evaluable = bool(overlap_trace_ids)
    by_dimension: dict[str, Any] = {}

    for dimension in QUALITY_DIMENSIONS:
        agree_count = sum(
            1
            for trace_id in overlap_trace_ids
            if getattr(human_labels[trace_id], dimension)
            == getattr(judge_labels[trace_id], dimension)
        )
        agreement_rate = agree_count / len(overlap_trace_ids) if overlap_trace_ids else None
        by_dimension[dimension] = {
            "agree_count": agree_count,
            "total": len(overlap_trace_ids),
            "agreement_rate": round(agreement_rate, 4) if agreement_rate is not None else None,
            "meets_threshold": (
                agreement_rate >= AGREEMENT_THRESHOLD if agreement_rate is not None else False
            ),
        }

    overall_agree_count = sum(
        1
        for trace_id in overlap_trace_ids
        if human_labels[trace_id].overall_pass == judge_labels[trace_id].overall_pass
    )
    overall_rate = overall_agree_count / len(overlap_trace_ids) if overlap_trace_ids else None

    by_dimension["overall_pass"] = {
        "agree_count": overall_agree_count,
        "total": len(overlap_trace_ids),
        "agreement_rate": round(overall_rate, 4) if overall_rate is not None else None,
        "meets_threshold": overall_rate >= AGREEMENT_THRESHOLD if overall_rate is not None else False,
    }

    dimensions_below_threshold = (
        [
            dimension
            for dimension, metrics in by_dimension.items()
            if dimension != "overall_pass" and not metrics["meets_threshold"]
        ]
        if agreement_evaluable
        else []
    )

    return {
        "threshold": AGREEMENT_THRESHOLD,
        "agreement_evaluable": agreement_evaluable,
        "overlap_count": len(overlap_trace_ids),
        "overlap_trace_ids": overlap_trace_ids,
        "by_dimension": by_dimension,
        "dimensions_below_threshold": dimensions_below_threshold,
        "judge_calibration_required": agreement_evaluable and bool(dimensions_below_threshold),
    }


def category_counts(records: dict[str, GeneratedRecord]) -> dict[str, Any]:
    """Compute category counts and shares."""
    counts = Counter(record.category for record in records.values())
    total = sum(counts.values())
    categories = list(CATEGORIES) + sorted(set(counts) - set(CATEGORIES))

    return {
        category: {
            "count": counts.get(category, 0),
            "share": round(counts.get(category, 0) / total, 4) if total else 0.0,
        }
        for category in categories
    }


def labels_by_category(
    labels: dict[str, QualityLabel],
    records: dict[str, GeneratedRecord],
) -> dict[str, Any]:
    """Compute dimension pass rates grouped by category."""
    grouped: dict[str, list[QualityLabel]] = defaultdict(list)

    for trace_id, label in labels.items():
        record = records.get(trace_id)
        category = record.category if record is not None else "unknown"
        grouped[category].append(label)

    categories = list(CATEGORIES) + sorted(set(grouped) - set(CATEGORIES))
    metrics: dict[str, Any] = {}

    for category in categories:
        category_labels = grouped.get(category, [])
        total = len(category_labels)
        dimension_rates: dict[str, Any] = {}

        for dimension in QUALITY_DIMENSIONS:
            passed = sum(getattr(label, dimension) for label in category_labels)
            dimension_rates[dimension] = round(passed / total, 4) if total else None

        overall_passed = sum(1 for label in category_labels if label.overall_pass)
        metrics[category] = {
            "count": total,
            "overall_pass_rate": round(overall_passed / total, 4) if total else None,
            "dimension_pass_rates": dimension_rates,
        }

    return metrics


def labels_by_prompt_variant(
    labels: dict[str, QualityLabel],
    records: dict[str, GeneratedRecord],
) -> dict[str, Any]:
    """Compute overall pass rates grouped by prompt variant."""
    grouped: dict[str, list[QualityLabel]] = defaultdict(list)

    for trace_id, label in labels.items():
        record = records.get(trace_id)
        prompt_variant = record.prompt_variant if record is not None else "unknown"
        grouped[prompt_variant].append(label)

    metrics: dict[str, Any] = {}

    for prompt_variant, variant_labels in sorted(grouped.items()):
        total = len(variant_labels)
        overall_passed = sum(1 for label in variant_labels if label.overall_pass)
        metrics[prompt_variant] = {
            "count": total,
            "overall_pass_rate": round(overall_passed / total, 4) if total else None,
        }

    return metrics


def labels_by_judge_prompt_version(labels: dict[str, QualityLabel]) -> dict[str, Any]:
    """Compute pass rates grouped by judge prompt version."""
    grouped: dict[str, list[QualityLabel]] = defaultdict(list)

    for label in labels.values():
        prompt_version = label.judge_prompt_version or "unknown"
        grouped[prompt_version].append(label)

    metrics: dict[str, Any] = {}

    for prompt_version, version_labels in sorted(grouped.items()):
        total = len(version_labels)
        dimension_rates: dict[str, Any] = {}

        for dimension in QUALITY_DIMENSIONS:
            passed = sum(getattr(label, dimension) for label in version_labels)
            dimension_rates[dimension] = round(passed / total, 4) if total else None

        overall_passed = sum(1 for label in version_labels if label.overall_pass)
        metrics[prompt_version] = {
            "count": total,
            "overall_pass_rate": round(overall_passed / total, 4) if total else None,
            "dimension_pass_rates": dimension_rates,
        }

    return metrics


def gate_by_category(
    gate_results: dict[str, GateResult],
    records: dict[str, GeneratedRecord],
) -> dict[str, Any]:
    """Compute Step 2 gate pass rates grouped by category."""
    grouped: dict[str, list[GateResult]] = defaultdict(list)

    for trace_id, gate_result in gate_results.items():
        record = records.get(trace_id)
        category = record.category if record is not None else "unknown"
        grouped[category].append(gate_result)

    categories = list(CATEGORIES) + sorted(set(grouped) - set(CATEGORIES))
    metrics: dict[str, Any] = {}

    for category in categories:
        category_results = grouped.get(category, [])
        total = len(category_results)
        passed = sum(1 for result in category_results if result.passed)
        failed_checks = Counter(
            failed_check
            for result in category_results
            for failed_check in result.failed_checks
        )
        metrics[category] = {
            "count": total,
            "pass_count": passed,
            "pass_rate": round(passed / total, 4) if total else None,
            "failed_check_counts": dict(sorted(failed_checks.items())),
        }

    return metrics


def gate_by_prompt_variant(
    gate_results: dict[str, GateResult],
    records: dict[str, GeneratedRecord],
) -> dict[str, Any]:
    """Compute Step 2 gate pass rates grouped by generator prompt variant."""
    grouped: dict[str, list[GateResult]] = defaultdict(list)

    for trace_id, gate_result in gate_results.items():
        record = records.get(trace_id)
        prompt_variant = record.prompt_variant if record is not None else "unknown"
        grouped[prompt_variant].append(gate_result)

    metrics: dict[str, Any] = {}

    for prompt_variant, variant_results in sorted(grouped.items()):
        total = len(variant_results)
        passed = sum(1 for result in variant_results if result.passed)
        metrics[prompt_variant] = {
            "count": total,
            "pass_count": passed,
            "pass_rate": round(passed / total, 4) if total else None,
        }

    return metrics


def agreement_by_judge_prompt_version(
    human_labels: dict[str, QualityLabel],
    judge_labels: dict[str, QualityLabel],
) -> dict[str, Any]:
    """Compute human/LLM agreement grouped by judge prompt version."""
    grouped_trace_ids: dict[str, list[str]] = defaultdict(list)

    for trace_id in sorted(set(human_labels) & set(judge_labels)):
        prompt_version = judge_labels[trace_id].judge_prompt_version or "unknown"
        grouped_trace_ids[prompt_version].append(trace_id)

    metrics: dict[str, Any] = {}

    for prompt_version, trace_ids in sorted(grouped_trace_ids.items()):
        by_dimension: dict[str, Any] = {}

        for dimension in QUALITY_DIMENSIONS:
            agree_count = sum(
                1
                for trace_id in trace_ids
                if getattr(human_labels[trace_id], dimension)
                == getattr(judge_labels[trace_id], dimension)
            )
            agreement_rate = agree_count / len(trace_ids) if trace_ids else None
            by_dimension[dimension] = {
                "agree_count": agree_count,
                "total": len(trace_ids),
                "agreement_rate": round(agreement_rate, 4)
                if agreement_rate is not None
                else None,
                "meets_threshold": (
                    agreement_rate >= AGREEMENT_THRESHOLD
                    if agreement_rate is not None
                    else False
                ),
            }

        metrics[prompt_version] = {
            "overlap_count": len(trace_ids),
            "by_dimension": by_dimension,
            "dimensions_below_threshold": [
                dimension
                for dimension, dimension_metrics in by_dimension.items()
                if not dimension_metrics["meets_threshold"]
            ],
        }

    return metrics


def worst_segments(category_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Rank categories by overall pass rate ascending."""
    segments: list[dict[str, Any]] = []

    for category, metrics in category_metrics.items():
        if metrics["count"] == 0 or metrics["overall_pass_rate"] is None:
            continue

        segments.append(
            {
                "category": category,
                "count": metrics["count"],
                "overall_pass_rate": metrics["overall_pass_rate"],
            }
        )

    return sorted(segments, key=lambda row: (row["overall_pass_rate"], -row["count"]))


def build_analysis_report(
    *,
    raw_records: dict[str, GeneratedRecord],
    validated_records: dict[str, GeneratedRecord],
    gate_report: dict[str, Any],
    gate_results: dict[str, GateResult],
    human_labels: dict[str, QualityLabel],
    judge_labels: dict[str, QualityLabel],
) -> dict[str, Any]:
    """Build the Step 5 metrics report."""
    human_category_metrics = labels_by_category(human_labels, raw_records)
    judge_category_metrics = labels_by_category(judge_labels, raw_records)
    agreement = agreement_metrics(human_labels, judge_labels)
    if not agreement["agreement_evaluable"]:
        next_recommended_step = (
            "Human/LLM agreement is not evaluable for this run because there are no "
            "overlapping trace IDs; use the previously calibrated judge for Phase B "
            "generator comparison or add human labels for this dataset."
        )
    elif agreement["judge_calibration_required"]:
        next_recommended_step = (
            "Step 6 Phase A: calibrate the LLM judge prompt before generator correction."
        )
    else:
        next_recommended_step = (
            "Step 6 Phase B: use the calibrated judge to guide generator correction."
        )

    return {
        "step": "step_5_analysis",
        "timestamp": datetime.now().isoformat(),
        "inputs": {
            "raw_records": len(raw_records),
            "validated_records": len(validated_records),
            "gate_results": len(gate_results),
            "human_labels": len(human_labels),
            "judge_labels": len(judge_labels),
            "human_judge_overlap": agreement["overlap_count"],
        },
        "category_distribution": {
            "raw": category_counts(raw_records),
            "validated": category_counts(validated_records),
        },
        "quality_gate": gate_report,
        "human_label_pass_rates": label_pass_rates(human_labels),
        "judge_label_pass_rates": label_pass_rates(judge_labels),
        "human_judge_agreement": agreement,
        "segments": {
            "gate_by_category": gate_by_category(gate_results, raw_records),
            "gate_by_prompt_variant": gate_by_prompt_variant(gate_results, raw_records),
            "human_by_category": human_category_metrics,
            "judge_by_category": judge_category_metrics,
            "human_by_prompt_variant": labels_by_prompt_variant(human_labels, raw_records),
            "judge_by_prompt_variant": labels_by_prompt_variant(judge_labels, raw_records),
            "judge_by_judge_prompt_version": labels_by_judge_prompt_version(judge_labels),
            "agreement_by_judge_prompt_version": agreement_by_judge_prompt_version(
                human_labels,
                judge_labels,
            ),
            "worst_human_categories": worst_segments(human_category_metrics),
            "worst_judge_categories": worst_segments(judge_category_metrics),
        },
        "diagnosis": {
            "agreement_evaluable": agreement["agreement_evaluable"],
            "judge_calibration_required": agreement["judge_calibration_required"],
            "dimensions_below_80pct_agreement": agreement["dimensions_below_threshold"],
            "next_recommended_step": next_recommended_step,
        },
    }


def pass_rate_chart_data(
    human_labels: dict[str, QualityLabel],
    judge_labels: dict[str, QualityLabel],
) -> pd.DataFrame:
    """Build pass-rate chart data."""
    rows: list[dict[str, Any]] = []

    for labeler, labels in (("human", human_labels), ("llm_judge", judge_labels)):
        rates = label_pass_rates(labels)
        for dimension in QUALITY_DIMENSIONS + ["overall_pass"]:
            rows.append(
                {
                    "labeler": labeler,
                    "dimension": dimension,
                    "pass_rate": rates[dimension]["pass_rate"],
                }
            )

    return pd.DataFrame(rows)


def agreement_chart_data(agreement: dict[str, Any]) -> pd.DataFrame:
    """Build agreement chart data."""
    rows = [
        {
            "dimension": dimension,
            "agreement_rate": metrics["agreement_rate"],
            "meets_threshold": metrics["meets_threshold"],
        }
        for dimension, metrics in agreement["by_dimension"].items()
    ]
    return pd.DataFrame(rows)


def category_distribution_chart_data(
    raw_records: dict[str, GeneratedRecord],
    validated_records: dict[str, GeneratedRecord],
) -> pd.DataFrame:
    """Build category distribution chart data."""
    rows: list[dict[str, Any]] = []

    for dataset_name, records in (("raw", raw_records), ("validated", validated_records)):
        counts = Counter(record.category for record in records.values())
        for category in CATEGORIES:
            rows.append(
                {
                    "dataset": dataset_name,
                    "category": category,
                    "count": counts.get(category, 0),
                }
            )

    return pd.DataFrame(rows)


def category_pass_chart_data(
    category_metrics: dict[str, Any],
    labeler: str,
) -> pd.DataFrame:
    """Build category overall pass-rate chart data."""
    rows = [
        {
            "labeler": labeler,
            "category": category,
            "overall_pass_rate": metrics["overall_pass_rate"],
            "count": metrics["count"],
        }
        for category, metrics in category_metrics.items()
        if metrics["count"] > 0
    ]
    return pd.DataFrame(rows)


def gate_category_chart_data(category_metrics: dict[str, Any]) -> pd.DataFrame:
    """Build Step 2 gate category pass-rate chart data."""
    rows = [
        {
            "category": category,
            "pass_rate": metrics["pass_rate"],
            "count": metrics["count"],
        }
        for category, metrics in category_metrics.items()
        if metrics["count"] > 0
    ]
    return pd.DataFrame(rows)


def judge_prompt_version_chart_data(version_metrics: dict[str, Any]) -> pd.DataFrame:
    """Build judge prompt version pass-rate chart data."""
    rows = [
        {
            "judge_prompt_version": prompt_version,
            "overall_pass_rate": metrics["overall_pass_rate"],
            "count": metrics["count"],
        }
        for prompt_version, metrics in version_metrics.items()
        if metrics["count"] > 0
    ]
    return pd.DataFrame(rows)


def dimension_heatmap_data(category_metrics: dict[str, Any]) -> pd.DataFrame:
    """Build category x dimension pass-rate heatmap data."""
    rows: list[dict[str, Any]] = []

    for category, metrics in category_metrics.items():
        if metrics["count"] == 0:
            continue

        row: dict[str, Any] = {"category": category}
        row.update(metrics["dimension_pass_rates"])
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["category", *QUALITY_DIMENSIONS])

    return pd.DataFrame(rows).set_index("category")


def save_bar_chart(
    *,
    data: pd.DataFrame,
    x: str,
    y: str,
    path: Path,
    title: str,
    hue: str | None = None,
    ylim: tuple[float, float] | None = None,
    rotation: int = 30,
) -> None:
    """Save a bar chart PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, 6))
    sns.barplot(data=data, x=x, y=y, hue=hue)
    plt.title(title)
    plt.xlabel(x.replace("_", " ").title())
    plt.ylabel(y.replace("_", " ").title())

    if ylim is not None:
        plt.ylim(*ylim)

    plt.xticks(rotation=rotation, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def save_agreement_chart(data: pd.DataFrame, path: Path) -> None:
    """Save human/LLM agreement chart with the 80% threshold."""
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, 6))
    sns.barplot(data=data, x="dimension", y="agreement_rate", hue="meets_threshold")
    plt.axhline(AGREEMENT_THRESHOLD, color="red", linestyle="--", linewidth=1.5)
    plt.title("Human vs LLM Judge Agreement by Dimension")
    plt.xlabel("Dimension")
    plt.ylabel("Agreement Rate")
    plt.ylim(0, 1)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def save_heatmap(data: pd.DataFrame, path: Path, title: str) -> None:
    """Save category x dimension heatmap."""
    if data.empty:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, 7))
    sns.heatmap(data, annot=True, vmin=0, vmax=1, cmap="RdYlGn", fmt=".2f")
    plt.title(title)
    plt.xlabel("Dimension")
    plt.ylabel("Category")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def save_visualizations(
    *,
    report: dict[str, Any],
    raw_records: dict[str, GeneratedRecord],
    validated_records: dict[str, GeneratedRecord],
    human_labels: dict[str, QualityLabel],
    judge_labels: dict[str, QualityLabel],
    output_dir: Path,
    artifact_stem: str,
) -> list[str]:
    """Create Step 5 visualization PNGs."""
    sns.set_theme(style="whitegrid")
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_paths = {
        "labeler_dimension_pass_rates": output_dir
        / f"{artifact_stem}_labeler_dimension_pass_rates.png",
        "human_judge_agreement": output_dir
        / f"{artifact_stem}_human_judge_agreement_by_dimension.png",
        "category_distribution": output_dir
        / f"{artifact_stem}_category_distribution_raw_vs_validated.png",
        "human_category_pass_rates": output_dir
        / f"{artifact_stem}_human_category_overall_pass_rates.png",
        "judge_category_pass_rates": output_dir
        / f"{artifact_stem}_judge_category_overall_pass_rates.png",
        "judge_category_dimension_heatmap": output_dir
        / f"{artifact_stem}_judge_category_dimension_pass_rates.png",
        "human_category_dimension_heatmap": output_dir
        / f"{artifact_stem}_human_category_dimension_pass_rates.png",
        "gate_category_pass_rates": output_dir / f"{artifact_stem}_gate_category_pass_rates.png",
        "judge_prompt_version_pass_rates": output_dir
        / f"{artifact_stem}_judge_prompt_version_pass_rates.png",
    }

    save_bar_chart(
        data=pass_rate_chart_data(human_labels, judge_labels),
        x="dimension",
        y="pass_rate",
        hue="labeler",
        path=chart_paths["labeler_dimension_pass_rates"],
        title="Pass Rates by Dimension: Human vs LLM Judge",
        ylim=(0, 1),
    )
    save_agreement_chart(
        agreement_chart_data(report["human_judge_agreement"]),
        chart_paths["human_judge_agreement"],
    )
    save_bar_chart(
        data=category_distribution_chart_data(raw_records, validated_records),
        x="category",
        y="count",
        hue="dataset",
        path=chart_paths["category_distribution"],
        title="Category Distribution: Raw vs Validated",
    )
    save_bar_chart(
        data=category_pass_chart_data(report["segments"]["human_by_category"], "human"),
        x="category",
        y="overall_pass_rate",
        path=chart_paths["human_category_pass_rates"],
        title="Human Overall Pass Rate by Category",
        ylim=(0, 1),
    )
    save_bar_chart(
        data=category_pass_chart_data(report["segments"]["judge_by_category"], "llm_judge"),
        x="category",
        y="overall_pass_rate",
        path=chart_paths["judge_category_pass_rates"],
        title="LLM Judge Overall Pass Rate by Category",
        ylim=(0, 1),
    )
    save_heatmap(
        dimension_heatmap_data(report["segments"]["judge_by_category"]),
        chart_paths["judge_category_dimension_heatmap"],
        "LLM Judge Dimension Pass Rates by Category",
    )
    save_heatmap(
        dimension_heatmap_data(report["segments"]["human_by_category"]),
        chart_paths["human_category_dimension_heatmap"],
        "Human Dimension Pass Rates by Category",
    )
    save_bar_chart(
        data=gate_category_chart_data(report["segments"]["gate_by_category"]),
        x="category",
        y="pass_rate",
        path=chart_paths["gate_category_pass_rates"],
        title="Step 2 Gate Pass Rate by Category",
        ylim=(0, 1),
    )
    save_bar_chart(
        data=judge_prompt_version_chart_data(
            report["segments"]["judge_by_judge_prompt_version"]
        ),
        x="judge_prompt_version",
        y="overall_pass_rate",
        path=chart_paths["judge_prompt_version_pass_rates"],
        title="LLM Judge Overall Pass Rate by Judge Prompt Version",
        ylim=(0, 1),
        rotation=0,
    )

    return [str(path) for path in chart_paths.values() if path.exists()]


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Analyze baseline pipeline outputs.")

    parser.add_argument("--raw", default=DEFAULT_RAW_FILENAME)
    parser.add_argument("--validated", default=DEFAULT_VALIDATED_FILENAME)
    parser.add_argument("--gate-log", default=DEFAULT_GATE_LOG_FILENAME)
    parser.add_argument("--gate-report", default=DEFAULT_GATE_REPORT_FILENAME)
    parser.add_argument("--human-labels", default=DEFAULT_HUMAN_LABELS_FILENAME)
    parser.add_argument("--judge-labels", default=DEFAULT_JUDGE_LABELS_FILENAME)
    parser.add_argument(
        "--artifact-variant",
        default=None,
        help=(
            "Semantic variant used in generated artifact filenames. "
            "Default: inferred as generator-<prompt_variant>_judge-<judge_prompt_version>."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier used in artifact filenames. Default: timestamp YYYYMMDD_HHMMSS.",
    )
    parser.add_argument(
        "--report-output",
        default=None,
        help="Optional explicit report filename. Default: analysis_<variant>_<run_id>.json.",
    )
    parser.add_argument(
        "--trace-output",
        default=None,
        help=(
            "Optional explicit trace filename. "
            "Default: trace_records_<variant>_<run_id>.jsonl."
        ),
    )
    parser.add_argument(
        "--log-output",
        default=None,
        help="Optional explicit log filename. Default: analysis_<variant>_<run_id>.jsonl.",
    )
    parser.add_argument(
        "--visualization-dir",
        default=str(VISUALIZATIONS_DIR),
        help="Directory for chart PNGs. Default: visualizations/.",
    )

    return parser.parse_args()


def main() -> None:
    """Run Step 5 analysis and visualization."""
    ensure_output_dirs()
    args = parse_args()
    run_id = args.run_id or default_run_id()

    raw_path = RAW_DIR / args.raw
    validated_path = VALIDATED_DIR / args.validated
    gate_log_path = LOGS_DIR / args.gate_log
    gate_report_path = REPORTS_DIR / args.gate_report
    human_labels_path = LABELS_DIR / args.human_labels
    judge_labels_path = LABELS_DIR / args.judge_labels
    visualization_dir = Path(args.visualization_dir)

    raw_records = load_generated_records(raw_path)
    validated_records = load_generated_records(validated_path)
    gate_results = load_gate_results(gate_log_path)
    gate_report = read_json(gate_report_path)
    human_labels = load_quality_labels(human_labels_path, "human")
    judge_labels = load_quality_labels(judge_labels_path, "llm_judge")
    artifact_variant = args.artifact_variant or infer_artifact_variant(
        raw_records,
        judge_labels,
    )
    artifact_stem = f"{artifact_variant}_{run_id}"
    report_output = args.report_output or artifact_filename(
        artifact_name="analysis",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="json",
    )
    trace_output = args.trace_output or artifact_filename(
        artifact_name="trace_records",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="jsonl",
    )
    log_output = args.log_output or artifact_filename(
        artifact_name="analysis",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="jsonl",
    )
    report_path = REPORTS_DIR / report_output
    trace_path = REPORTS_DIR / trace_output
    log_path = LOGS_DIR / log_output

    trace_records = assemble_trace_records(
        generated_records=raw_records,
        gate_results=gate_results,
        human_labels=human_labels,
        judge_labels=judge_labels,
    )
    report = build_analysis_report(
        raw_records=raw_records,
        validated_records=validated_records,
        gate_report=gate_report,
        gate_results=gate_results,
        human_labels=human_labels,
        judge_labels=judge_labels,
    )
    chart_paths = save_visualizations(
        report=report,
        raw_records=raw_records,
        validated_records=validated_records,
        human_labels=human_labels,
        judge_labels=judge_labels,
        output_dir=visualization_dir,
        artifact_stem=artifact_stem,
    )
    report["artifact_variant"] = artifact_variant
    report["run_id"] = run_id
    report["artifact_stem"] = artifact_stem
    report["outputs"] = {
        "report": str(report_path),
        "trace_records": str(trace_path),
        "analysis_log": str(log_path),
        "visualizations": chart_paths,
    }
    report["visualizations"] = chart_paths

    write_json(report_path, report)
    write_jsonl(
        trace_path,
        [trace_record.model_dump(mode="json") for trace_record in trace_records],
    )
    append_jsonl(
        log_path,
        {
            "step": "step_5_analysis",
            "timestamp": report["timestamp"],
            "status": "success",
            "artifact_variant": artifact_variant,
            "run_id": run_id,
            "artifact_stem": artifact_stem,
            "report_output": str(report_path),
            "trace_output": str(trace_path),
            "log_output": str(log_path),
            "visualizations": chart_paths,
            "inputs": report["inputs"],
            "judge_calibration_required": report["diagnosis"]["judge_calibration_required"],
            "dimensions_below_80pct_agreement": report["diagnosis"][
                "dimensions_below_80pct_agreement"
            ],
        },
    )

    print("Step 5: Analysis and visualization")
    print("----------------------------------")
    print(f"Artifact variant: {artifact_variant}")
    print(f"Run ID: {run_id}")
    print(f"Raw records: {len(raw_records)}")
    print(f"Validated records: {len(validated_records)}")
    print(f"Human labels: {len(human_labels)}")
    print(f"LLM judge labels: {len(judge_labels)}")
    print(f"Human/judge overlap: {report['inputs']['human_judge_overlap']}")
    print(
        "Judge calibration required: "
        f"{report['diagnosis']['judge_calibration_required']}"
    )
    print(
        "Dimensions below 80% agreement: "
        f"{', '.join(report['diagnosis']['dimensions_below_80pct_agreement'])}"
    )
    print()
    print(f"Wrote report to: {report_path}")
    print(f"Wrote trace records to: {trace_path}")
    print(f"Wrote analysis log to: {log_path}")
    print(f"Wrote visualizations: {len(chart_paths)}")


if __name__ == "__main__":
    main()
