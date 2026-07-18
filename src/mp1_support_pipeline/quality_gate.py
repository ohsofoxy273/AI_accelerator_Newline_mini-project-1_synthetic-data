"""Step 2: Data quality gate.

This script reads generated synthetic Q&A records from data/raw/, applies
schema validation and lightweight quality pre-checks, removes duplicates,
checks category distribution, and writes validated records plus reports.

Input:
    data/raw/generated_baseline.jsonl

Outputs:
    data/validated/validated_generator-<prompt_variant>_<run_id>.jsonl
    data/reports/quality_gate_generator-<prompt_variant>_<run_id>.json
    logs/quality_gate_generator-<prompt_variant>_<run_id>.jsonl

This is intentionally not the full quality judge. It is a first-pass gate
that catches obvious problems before human labeling and LLM-as-judge scoring.
"""

from __future__ import annotations

import argparse
import json
import re
import string
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from mp1_support_pipeline.artifacts import artifact_filename, artifact_slug, default_run_id
from mp1_support_pipeline.config import (
    CATEGORIES,
    LOGS_DIR,
    RAW_DIR,
    REPORTS_DIR,
    VALIDATED_DIR,
)
from mp1_support_pipeline.models import GeneratedRecord, GateResult


DEFAULT_INPUT_FILENAME = "generated_baseline.jsonl"

DEFAULT_MIN_CATEGORY_SHARE = 0.18
DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD = 0.92


GENERIC_SAFETY_PHRASES = {
    "be careful",
    "use caution",
    "stay safe",
    "follow safety guidelines",
    "protect your information",
    "protect user information",
    "do not share private information",
    "keep information safe",
}

DOMAIN_SAFETY_KEYWORDS = {
    "account",
    "password",
    "email",
    "billing",
    "payment",
    "card",
    "stripe",
    "refund",
    "subscription",
    "invoice",
    "privacy",
    "personal data",
    "customer data",
    "user data",
    "admin",
    "identity",
    "authentication",
    "authorization",
    "access",
    "phi",
    "hipaa",
    "patient",
    "patient-identifying",
    "clinical",
    "medical record",
    "credentials",
    "verification code",
    "one-time code",
    "screenshot",
    "redact",
}

UNREALISTIC_OR_UNHELPFUL_TOOLS = {
    "good communication",
    "patience",
    "customer service skills",
    "common sense",
    "professionalism",
    "notepad",
    "pen",
}

REALISTIC_SUPPORT_TOOL_KEYWORDS = {
    "admin",
    "dashboard",
    "stripe",
    "support inbox",
    "support email",
    "support contact form",
    "support help form",
    "support portal",
    "secure support",
    "logs",
    "server logs",
    "error logs",
    "screenshot",
    "browser details",
    "browser settings",
    "supported browser",
    "web browser",
    "chrome browser",
    "incognito",
    "private browsing",
    "cache",
    "cookies",
    "internet connection",
    "email inbox",
    "email access",
    "device details",
    "internet-connected device",
    "user email",
    "account email",
    "account settings",
    "account portal",
    "account dashboard",
    "account recovery",
    "password reset",
    "activation",
    "activation link",
    "order confirmation",
    "order number",
    "reference id",
    "subscription",
    "subscription settings",
    "invoice",
    "order history",
    "receipt",
    "payment",
    "billing",
    "billing portal",
    "billing settings",
    "billing history",
    "billing records",
    "tax",
    "authorization letter",
    "database",
    "django admin",
    "ticket",
    "crm",
    "institutional",
}

GENERIC_TIP_PHRASES = {
    "be polite",
    "be helpful",
    "respond promptly",
    "stay professional",
    "ensure customer satisfaction",
    "keep the customer happy",
    "provide good service",
    "communicate clearly",
    "follow up with the customer",
}


def ensure_dirs() -> None:
    """Create output directories if needed."""
    VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dictionaries."""
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
    """Write rows to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a dictionary to a pretty JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def infer_generator_variant(records: list[GeneratedRecord]) -> str:
    """Infer generator variant from generated records."""
    variants = {
        artifact_slug(record.prompt_variant)
        for record in records
        if record.prompt_variant
    }

    return next(iter(variants)) if len(variants) == 1 else "mixed"


def normalize_text(text: str) -> str:
    """Normalize text for duplicate detection."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def token_set(text: str) -> set[str]:
    """Return normalized token set."""
    return set(normalize_text(text).split())


def jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings."""
    a_tokens = token_set(a)
    b_tokens = token_set(b)

    if not a_tokens and not b_tokens:
        return 1.0

    if not a_tokens or not b_tokens:
        return 0.0

    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def contains_any(text: str, phrases: set[str]) -> bool:
    """Return True if text contains any phrase from the phrase set."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def contains_unnegated_phrase(text: str, phrases: set[str]) -> bool:
    """Return True if text contains a risky phrase outside a simple negation."""
    lowered = text.lower()

    for phrase in phrases:
        start = 0

        while True:
            index = lowered.find(phrase, start)
            if index == -1:
                break

            context = lowered[max(0, index - 32):index]
            negations = (
                "do not ",
                "don't ",
                "don\u2019t ",
                "never ",
                "not ",
                "can't ",
                "can\u2019t ",
                "cannot ",
            )
            if not any(negation in context for negation in negations):
                return True

            start = index + len(phrase)

    return False


def count_words(text: str) -> int:
    """Rough word count."""
    return len(re.findall(r"\b\w+\b", text))


def check_d1_answer_completeness(record: GeneratedRecord) -> list[str]:
    """Cheap D1 pre-check: answer should be substantial and supported by steps."""
    item = record.item
    failures: list[str] = []

    if count_words(item.answer) < 80:
        failures.append("d1_answer_too_short")

    if len(item.steps) < 3:
        failures.append("d1_too_few_steps")

    if len(item.tools_required) < 1:
        failures.append("d1_missing_tools_or_resources")

    if len(item.tips) < 1:
        failures.append("d1_missing_tips")

    return failures


def check_d2_safety_specificity(record: GeneratedRecord) -> list[str]:
    """Cheap D2 pre-check: safety_info should be specific to support risks."""
    item = record.item
    safety = item.safety_info.strip()
    failures: list[str] = []

    if len(safety) < 50:
        failures.append("d2_safety_info_too_short")

    has_generic_phrase = contains_any(safety, GENERIC_SAFETY_PHRASES)
    has_domain_keyword = contains_any(safety, DOMAIN_SAFETY_KEYWORDS)

    if has_generic_phrase and not has_domain_keyword:
        failures.append("d2_generic_safety_without_specific_risk")

    if not has_domain_keyword:
        failures.append("d2_missing_domain_specific_safety_keyword")

    return failures


def check_d3_tool_realism(record: GeneratedRecord) -> list[str]:
    """Cheap D3 pre-check: tools/resources should be realistic support resources."""
    item = record.item
    failures: list[str] = []

    tools_normalized = [normalize_text(tool) for tool in item.tools_required]

    blocked_tools = [
        tool
        for tool in tools_normalized
        if tool in UNREALISTIC_OR_UNHELPFUL_TOOLS
    ]

    if blocked_tools:
        failures.append("d3_unrealistic_or_unhelpful_tool")

    combined_tools = " ".join(tools_normalized)
    has_realistic_support_tool = contains_any(combined_tools, REALISTIC_SUPPORT_TOOL_KEYWORDS)

    if not has_realistic_support_tool:
        failures.append("d3_no_realistic_support_resource_detected")

    return failures


def check_d4_scope_appropriateness(record: GeneratedRecord) -> list[str]:
    """Cheap D4 pre-check: avoid obvious overpromising or unsafe support behavior."""
    item = record.item
    text = " ".join(
        [
            item.question,
            item.answer,
            item.equipment_problem,
            item.safety_info,
            " ".join(item.steps),
            " ".join(item.tips),
        ]
    ).lower()

    failures: list[str] = []

    overpromise_phrases = {
        "guarantee a refund",
        "guarantee access",
        "immediately refund",
        "share your password",
        "send your password",
        "send your credit card",
        "send your card number",
        "we can access any account",
        "ignore privacy",
        "bypass authentication",
    }

    if contains_unnegated_phrase(text, overpromise_phrases):
        failures.append("d4_scope_or_security_overpromise")

    return failures


def check_d5_context_clarity(record: GeneratedRecord) -> list[str]:
    """Cheap D5 pre-check: question and equipment_problem should contain context."""
    item = record.item
    failures: list[str] = []

    if count_words(item.question) < 12:
        failures.append("d5_question_too_short")

    if count_words(item.equipment_problem) < 3:
        failures.append("d5_equipment_problem_too_vague")

    vague_issue_phrases = {
        "problem",
        "issue",
        "help",
        "not working",
        "account issue",
        "website issue",
    }

    normalized_problem = normalize_text(item.equipment_problem)

    if normalized_problem in vague_issue_phrases:
        failures.append("d5_equipment_problem_generic")

    return failures


def check_d6_tip_usefulness(record: GeneratedRecord) -> list[str]:
    """Cheap D6 pre-check: tips should not be extremely short or generic."""
    item = record.item
    failures: list[str] = []

    for tip in item.tips:
        normalized_tip = normalize_text(tip)

        if count_words(tip) < 6:
            failures.append("d6_tip_too_short")
            break

        if contains_any(normalized_tip, GENERIC_TIP_PHRASES):
            failures.append("d6_generic_tip")
            break

    return failures


def run_per_item_checks(record: GeneratedRecord) -> list[str]:
    """Run all lightweight per-item quality checks."""
    failures: list[str] = []

    failures.extend(check_d1_answer_completeness(record))
    failures.extend(check_d2_safety_specificity(record))
    failures.extend(check_d3_tool_realism(record))
    failures.extend(check_d4_scope_appropriateness(record))
    failures.extend(check_d5_context_clarity(record))
    failures.extend(check_d6_tip_usefulness(record))

    return failures


def validate_raw_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[GeneratedRecord], list[dict[str, Any]]]:
    """Validate raw rows using Pydantic and run per-item gate checks."""
    accepted: list[GeneratedRecord] = []
    logs: list[dict[str, Any]] = []

    for row_index, row in enumerate(raw_rows, start=1):
        timestamp = datetime.now()

        try:
            record = GeneratedRecord.model_validate(row)
            failed_checks = run_per_item_checks(record)
            passed = len(failed_checks) == 0

            gate_result = GateResult(
                trace_id=record.trace_id,
                passed=passed,
                failed_checks=failed_checks,
                timestamp=timestamp,
            )

            logs.append(
                {
                    **gate_result.model_dump(mode="json"),
                    "row_index": row_index,
                    "category": record.category,
                    "stage": "per_item_gate",
                }
            )

            if passed:
                accepted.append(record)

        except ValidationError as exc:
            trace_id = str(row.get("trace_id", f"row_{row_index}"))

            gate_result = GateResult(
                trace_id=trace_id,
                passed=False,
                failed_checks=["schema_validation_failed"],
                timestamp=timestamp,
            )

            logs.append(
                {
                    **gate_result.model_dump(mode="json"),
                    "row_index": row_index,
                    "category": row.get("category"),
                    "stage": "schema_validation",
                    "error": exc.errors(),
                }
            )

    return accepted, logs


def deduplicate_records(
    records: list[GeneratedRecord],
    similarity_threshold: float,
) -> tuple[list[GeneratedRecord], list[dict[str, Any]]]:
    """Remove duplicate or near-duplicate questions."""
    kept: list[GeneratedRecord] = []
    duplicate_logs: list[dict[str, Any]] = []

    seen_questions: dict[str, str] = {}

    for record in records:
        question = record.item.question
        normalized_question = normalize_text(question)

        duplicate_of: str | None = None
        duplicate_reason: str | None = None

        if normalized_question in seen_questions:
            duplicate_of = seen_questions[normalized_question]
            duplicate_reason = "exact_normalized_question_duplicate"
        else:
            for kept_record in kept:
                similarity = jaccard_similarity(question, kept_record.item.question)

                if similarity >= similarity_threshold:
                    duplicate_of = kept_record.trace_id
                    duplicate_reason = f"near_duplicate_question_similarity_{similarity:.2f}"
                    break

        if duplicate_of is not None:
            timestamp = datetime.now()

            duplicate_logs.append(
                {
                    "trace_id": record.trace_id,
                    "passed": False,
                    "failed_checks": ["duplicate_question"],
                    "timestamp": timestamp.isoformat(),
                    "category": record.category,
                    "stage": "deduplication",
                    "duplicate_of": duplicate_of,
                    "duplicate_reason": duplicate_reason,
                }
            )
            continue

        seen_questions[normalized_question] = record.trace_id
        kept.append(record)

    return kept, duplicate_logs


def category_distribution_report(
    records: list[GeneratedRecord],
    min_category_share: float,
) -> dict[str, Any]:
    """Compute category distribution and benchmark-aligned pass/fail status."""
    total = len(records)
    counts = Counter(record.category for record in records)

    category_details: dict[str, dict[str, Any]] = {}

    for category in CATEGORIES:
        count = counts.get(category, 0)
        share = count / total if total > 0 else 0.0

        category_details[category] = {
            "count": count,
            "share": round(share, 4),
            "target_share": 0.20,
            "minimum_allowed_share": min_category_share,
            "passes_minimum_share": share >= min_category_share,
        }

    unexpected_categories = sorted(set(counts) - set(CATEGORIES))

    distribution_passed = (
        total > 0
        and all(details["passes_minimum_share"] for details in category_details.values())
        and not unexpected_categories
    )

    return {
        "total_validated_after_dedup": total,
        "category_details": category_details,
        "unexpected_categories": unexpected_categories,
        "distribution_passed": distribution_passed,
    }


def summarize_gate(
    *,
    raw_count: int,
    per_item_logs: list[dict[str, Any]],
    duplicate_logs: list[dict[str, Any]],
    validated_records: list[GeneratedRecord],
    min_category_share: float,
) -> dict[str, Any]:
    """Build the Step 2 quality gate report."""
    all_failure_logs = [
        log
        for log in per_item_logs + duplicate_logs
        if not log.get("passed", False)
    ]

    failed_check_counts: Counter[str] = Counter()

    for log in all_failure_logs:
        for check in log.get("failed_checks", []):
            failed_check_counts[check] += 1

    per_item_pass_count = sum(
        1
        for log in per_item_logs
        if log.get("stage") == "per_item_gate" and log.get("passed") is True
    )

    schema_failure_count = sum(
        1
        for log in per_item_logs
        if log.get("stage") == "schema_validation" and log.get("passed") is False
    )

    duplicate_count = len(duplicate_logs)

    distribution = category_distribution_report(
        records=validated_records,
        min_category_share=min_category_share,
    )

    structural_validation_pass_rate = (
        (raw_count - schema_failure_count) / raw_count if raw_count > 0 else 0.0
    )

    per_item_gate_pass_rate = (
        per_item_pass_count / raw_count if raw_count > 0 else 0.0
    )

    final_validated_rate = (
        len(validated_records) / raw_count if raw_count > 0 else 0.0
    )

    return {
        "step": "step_2_quality_gate",
        "timestamp": datetime.now().isoformat(),
        "input_count": raw_count,
        "schema_failure_count": schema_failure_count,
        "structural_validation_pass_rate": round(structural_validation_pass_rate, 4),
        "per_item_gate_pass_count_before_dedup": per_item_pass_count,
        "per_item_gate_pass_rate_before_dedup": round(per_item_gate_pass_rate, 4),
        "duplicate_count": duplicate_count,
        "final_validated_count": len(validated_records),
        "final_validated_rate": round(final_validated_rate, 4),
        "failed_check_counts": dict(sorted(failed_check_counts.items())),
        "category_distribution": distribution,
        "batch_gate_passed": distribution["distribution_passed"],
        "notes": [
            "This gate is a lightweight first-pass filter, not the full quality evaluator.",
            "Full semantic evaluation happens later through human labels and LLM-as-judge labels.",
            "If batch_gate_passed is false, inspect failed_check_counts and category_distribution before regenerating.",
        ],
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run Step 2 quality gate.")

    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT_FILENAME,
        help=f"Input JSONL filename in data/raw/. Default: {DEFAULT_INPUT_FILENAME}.",
    )
    parser.add_argument(
        "--validated-output",
        type=str,
        default=None,
        help=(
            "Validated output JSONL filename in data/validated/. "
            "Default: validated_generator-<prompt_variant>_<run_id>.jsonl."
        ),
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default=None,
        help=(
            "Report JSON filename in data/reports/. "
            "Default: quality_gate_generator-<prompt_variant>_<run_id>.json."
        ),
    )
    parser.add_argument(
        "--log-output",
        type=str,
        default=None,
        help=(
            "Per-item log JSONL filename in logs/. "
            "Default: quality_gate_generator-<prompt_variant>_<run_id>.jsonl."
        ),
    )
    parser.add_argument(
        "--artifact-variant",
        type=str,
        default=None,
        help=(
            "Semantic variant used in generated artifact filenames. "
            "Default: generator-<prompt_variant>."
        ),
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run identifier used in artifact filenames. Default: timestamp YYYYMMDD_HHMMSS.",
    )
    parser.add_argument(
        "--min-category-share",
        type=float,
        default=DEFAULT_MIN_CATEGORY_SHARE,
        help=(
            "Minimum category share for distribution check. "
            f"Default: {DEFAULT_MIN_CATEGORY_SHARE}."
        ),
    )
    parser.add_argument(
        "--duplicate-similarity-threshold",
        type=float,
        default=DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD,
        help=(
            "Jaccard similarity threshold for near-duplicate question detection. "
            f"Default: {DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD}."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run the Step 2 quality gate."""
    ensure_dirs()
    args = parse_args()

    input_path = RAW_DIR / args.input

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    raw_rows = read_jsonl(input_path)
    schema_valid_records: list[GeneratedRecord] = []
    for row in raw_rows:
        try:
            schema_valid_records.append(GeneratedRecord.model_validate(row))
        except ValidationError:
            continue

    run_id = args.run_id or default_run_id()
    artifact_variant = args.artifact_variant or (
        f"generator-{infer_generator_variant(schema_valid_records)}"
    )
    validated_filename = args.validated_output or artifact_filename(
        artifact_name="validated",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="jsonl",
    )
    report_filename = args.report_output or artifact_filename(
        artifact_name="quality_gate",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="json",
    )
    log_filename = args.log_output or artifact_filename(
        artifact_name="quality_gate",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="jsonl",
    )
    validated_path = VALIDATED_DIR / validated_filename
    report_path = REPORTS_DIR / report_filename
    log_path = LOGS_DIR / log_filename

    print("Step 2: Data quality gate")
    print("-------------------------")
    print(f"Artifact variant: {artifact_variant}")
    print(f"Run ID: {run_id}")
    print(f"Input: {input_path}")
    print(f"Validated output: {validated_path}")
    print(f"Report output: {report_path}")
    print(f"Log output: {log_path}")
    print()

    per_item_accepted, per_item_logs = validate_raw_rows(raw_rows)

    deduped_records, duplicate_logs = deduplicate_records(
        records=per_item_accepted,
        similarity_threshold=args.duplicate_similarity_threshold,
    )

    report = summarize_gate(
        raw_count=len(raw_rows),
        per_item_logs=per_item_logs,
        duplicate_logs=duplicate_logs,
        validated_records=deduped_records,
        min_category_share=args.min_category_share,
    )
    report["artifact_variant"] = artifact_variant
    report["run_id"] = run_id
    report["artifact_stem"] = f"{artifact_variant}_{run_id}"
    report["outputs"] = {
        "validated": str(validated_path),
        "report": str(report_path),
        "log": str(log_path),
    }

    write_jsonl(
        validated_path,
        [record.model_dump(mode="json") for record in deduped_records],
    )
    write_json(report_path, report)
    write_jsonl(log_path, per_item_logs + duplicate_logs)

    print("Quality gate complete.")
    print(f"Input records: {report['input_count']}")
    print(f"Schema failures: {report['schema_failure_count']}")
    print(
        "Per-item gate pass count before dedup: "
        f"{report['per_item_gate_pass_count_before_dedup']}"
    )
    print(f"Duplicates removed: {report['duplicate_count']}")
    print(f"Final validated records: {report['final_validated_count']}")
    print(f"Batch distribution passed: {report['batch_gate_passed']}")
    print()
    print(f"Wrote validated data to: {validated_path}")
    print(f"Wrote report to: {report_path}")
    print(f"Wrote logs to: {log_path}")


if __name__ == "__main__":
    main()
