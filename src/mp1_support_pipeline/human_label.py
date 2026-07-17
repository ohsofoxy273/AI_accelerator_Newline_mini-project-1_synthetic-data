"""Step 3: Human labeling CLI.

This script walks a human reviewer through validated synthetic Q&A records
and collects binary pass/fail labels across the six required quality dimensions.

Input:
    data/validated/validated_baseline.jsonl

Output:
    data/labels/human_labels_baseline.jsonl

Examples:
    uv run python -m mp1_support_pipeline.human_label --limit 20
    uv run python -m mp1_support_pipeline.human_label --sample-strategy stratified --limit 20
"""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mp1_support_pipeline.config import CATEGORIES, LABELS_DIR, QUALITY_DIMENSIONS, VALIDATED_DIR
from mp1_support_pipeline.models import GeneratedRecord, QualityLabel


DEFAULT_INPUT_FILENAME = "validated_baseline.jsonl"
DEFAULT_OUTPUT_FILENAME = "human_labels_baseline.jsonl"
DEFAULT_LIMIT = 20
SampleStrategy = Literal["sequential", "stratified"]

DIMENSION_RUBRICS = {
    "answer_completeness": {
        "label": "D1 Answer Completeness",
        "question": "Does the support case contain enough information to resolve or appropriately triage the issue end to end?",
        "pass": "The answer and workflow include concrete next steps, requested information, safety/privacy handling, and a useful resolution or escalation path.",
        "fail": "The answer or workflow is vague, incomplete, missing key steps, depends on an unsupported platform workflow, or leaves the customer/support agent unsure what to do next.",
    },
    "safety_specificity": {
        "label": "D2 Safety Specificity",
        "question": "Does the case identify a specific privacy, billing, account-security, screenshot, medical/private-information, or data-handling risk and give a specific precaution?",
        "pass": "The safety note names a relevant risk, such as account access, password reset, billing data, screenshots, subscription records, institutional user data, or private medical information.",
        "fail": "The safety note is generic, such as 'be careful' or 'protect user data,' without a specific risk or precaution.",
    },
    "tool_realism": {
        "label": "D3 Tool Realism",
        "question": "Are the listed tools/resources realistic for the intended medical question bank support workflow?",
        "pass": "Resources fit the real workflow, such as admin dashboard, support inbox, Stripe/billing portal, logs, screenshots, user email, browser/device details, receipts, or invoice records.",
        "fail": "Resources are vague, irrelevant, unavailable to support, or invent unsupported workflows such as activation links, account recovery forms, app-store subscriptions, patient charts, or clinical-care systems.",
    },
    "scope_appropriateness": {
        "label": "D4 Scope Appropriateness",
        "question": "Do the answer and workflow stay within realistic support authority and escalate when needed?",
        "pass": "The case avoids overpromising and clearly escalates engineering, billing review, admin approval, content review, or account verification when appropriate.",
        "fail": "The response promises actions support cannot safely take, bypasses account/security processes, invents unsupported product workflows, or gives inappropriate authority to frontline support.",
    },
    "context_clarity": {
        "label": "D5 Context Clarity",
        "question": "Is there enough context to understand the customer issue and why the answer addresses it?",
        "pass": "The question, internal issue summary, and answer include enough relevant account, subscription, content-access, browser/device, billing, or institutional context.",
        "fail": "The issue is too vague, the internal issue summary describes the answer instead of the problem, the answer does not match the problem, important context is missing, or the case assumes unsupported platform behavior.",
    },
    "tip_usefulness": {
        "label": "D6 Tip Usefulness",
        "question": "Do the tips add non-obvious, task-specific support value beyond the workflow steps?",
        "pass": "The tips help a support agent handle the case better, faster, or more safely. Customer-facing troubleshooting suggestions can pass when they are useful things support should recommend.",
        "fail": "The tip is generic, merely repeats a step, or says something obvious like 'be polite' or 'follow up.'",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file."""
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
    """Write rows to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_records(path: Path) -> list[GeneratedRecord]:
    """Load validated generated records."""
    rows = read_jsonl(path)
    return [GeneratedRecord.model_validate(row) for row in rows]


def load_existing_labels(path: Path) -> dict[str, QualityLabel]:
    """Load existing human labels keyed by trace_id."""
    rows = read_jsonl(path)
    labels: dict[str, QualityLabel] = {}

    for row in rows:
        label = QualityLabel.model_validate(row)
        if label.labeler == "human":
            labels[label.trace_id] = label

    return labels


def save_labels(path: Path, labels_by_trace_id: dict[str, QualityLabel]) -> None:
    """Save all labels, sorted by trace_id for stable output."""
    rows = [
        label.model_dump(mode="json")
        for _, label in sorted(labels_by_trace_id.items(), key=lambda item: item[0])
    ]
    write_jsonl(path, rows)


def is_reviewable(
    record: GeneratedRecord,
    existing_labels: dict[str, QualityLabel],
    overwrite: bool,
) -> bool:
    """Return whether the record should be shown to the reviewer."""
    return overwrite or record.trace_id not in existing_labels


def select_records_for_review(
    records: list[GeneratedRecord],
    *,
    start_index: int,
    existing_labels: dict[str, QualityLabel],
    overwrite: bool,
    sample_strategy: SampleStrategy,
) -> list[tuple[int, GeneratedRecord]]:
    """Select candidate records while preserving original one-based item numbers."""
    indexed_records = list(enumerate(records[start_index:], start=start_index + 1))
    reviewable_records = [
        (visible_index, record)
        for visible_index, record in indexed_records
        if is_reviewable(record, existing_labels, overwrite)
    ]

    if sample_strategy == "sequential":
        return reviewable_records

    records_by_category: dict[str, list[tuple[int, GeneratedRecord]]] = {
        category: [] for category in CATEGORIES
    }
    unexpected_category_records: list[tuple[int, GeneratedRecord]] = []

    for visible_index, record in reviewable_records:
        if record.category in records_by_category:
            records_by_category[record.category].append((visible_index, record))
        else:
            unexpected_category_records.append((visible_index, record))

    stratified_records: list[tuple[int, GeneratedRecord]] = []
    category_position = 0

    while True:
        added_this_round = False

        for category in CATEGORIES:
            category_records = records_by_category[category]

            if category_position < len(category_records):
                stratified_records.append(category_records[category_position])
                added_this_round = True

        if not added_this_round:
            break

        category_position += 1

    return stratified_records + unexpected_category_records


def wrap(text: str, width: int = 96, indent: str = "") -> str:
    """Format long text for terminal display."""
    paragraphs = text.splitlines() or [""]
    wrapped_paragraphs: list[str] = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            wrapped_paragraphs.append("")
            continue

        wrapped_paragraphs.append(
            textwrap.fill(
                paragraph,
                width=width,
                initial_indent=indent,
                subsequent_indent=indent,
            )
        )

    return "\n".join(wrapped_paragraphs)


def print_section(title: str, content: str | list[str]) -> None:
    """Print a labeled item section."""
    print()
    print(title)
    print("-" * len(title))

    if isinstance(content, list):
        for index, value in enumerate(content, start=1):
            print(wrap(f"{index}. {value}", indent="  "))
    else:
        print(wrap(content, indent="  "))


def display_record(record: GeneratedRecord, item_number: int, total_items: int) -> None:
    """Display one generated record for human review."""
    item = record.item

    print()
    print("=" * 100)
    print(f"Item {item_number} of {total_items}")
    print(f"trace_id: {record.trace_id}")
    print(f"category: {record.category}")
    print(f"prompt_variant: {record.prompt_variant}")
    print("=" * 100)

    print_section("QUESTION", item.question)
    print_section("ANSWER", item.answer)
    print_section("EQUIPMENT_PROBLEM / SUPPORT ISSUE", item.equipment_problem)
    print_section("TOOLS_REQUIRED / SUPPORT RESOURCES", item.tools_required)
    print_section("STEPS", item.steps)
    print_section("SAFETY_INFO", item.safety_info)
    print_section("TIPS", item.tips)
    print()


def print_dimension_rubric(dimension: str) -> None:
    """Print rubric for a single dimension."""
    rubric = DIMENSION_RUBRICS[dimension]

    print()
    print(rubric["label"])
    print("-" * len(rubric["label"]))
    print(wrap(rubric["question"], indent="  "))
    print()
    print(wrap(f"PASS: {rubric['pass']}", indent="  "))
    print(wrap(f"FAIL: {rubric['fail']}", indent="  "))


def parse_label_input(value: str) -> Literal[0, 1, "skip", "quit", "help"] | None:
    """Parse one CLI answer."""
    normalized = value.strip().lower()

    if normalized in {"1", "p", "pass", "y", "yes"}:
        return 1

    if normalized in {"0", "f", "fail", "n", "no"}:
        return 0

    if normalized in {"s", "skip"}:
        return "skip"

    if normalized in {"q", "quit", "exit"}:
        return "quit"

    if normalized in {"?", "h", "help"}:
        return "help"

    return None


def ask_dimension_label(dimension: str) -> Literal[0, 1, "skip", "quit"]:
    """Ask the reviewer for one pass/fail dimension label."""
    print_dimension_rubric(dimension)

    while True:
        raw = input("Label [p/pass/1, f/fail/0, s/skip item, q/quit, ?/help]: ")
        parsed = parse_label_input(raw)

        if parsed == 0 or parsed == 1 or parsed == "skip" or parsed == "quit":
            return parsed

        if parsed == "help":
            print_dimension_rubric(dimension)
            continue

        print("Unrecognized input. Use p, f, s, q, or ?.")


def label_record(record: GeneratedRecord) -> QualityLabel | Literal["skip", "quit"]:
    """Collect all six dimension labels for one record."""
    labels: dict[str, int] = {}

    for dimension in QUALITY_DIMENSIONS:
        response = ask_dimension_label(dimension)

        if response == "skip":
            return "skip"

        if response == "quit":
            return "quit"

        labels[dimension] = response

    overall_pass = all(value == 1 for value in labels.values())

    return QualityLabel(
        trace_id=record.trace_id,
        labeler="human",
        answer_completeness=labels["answer_completeness"],
        safety_specificity=labels["safety_specificity"],
        tool_realism=labels["tool_realism"],
        scope_appropriateness=labels["scope_appropriateness"],
        context_clarity=labels["context_clarity"],
        tip_usefulness=labels["tip_usefulness"],
        overall_pass=overall_pass,
        timestamp=datetime.now(),
        judge_prompt_version=None,
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Human label validated Q&A records.")

    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT_FILENAME,
        help=f"Input JSONL filename in data/validated/. Default: {DEFAULT_INPUT_FILENAME}.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_FILENAME,
        help=f"Output JSONL filename in data/labels/. Default: {DEFAULT_OUTPUT_FILENAME}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of new items to label. Default: {DEFAULT_LIMIT}.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start index within the validated records. Zero-based. Default: 0.",
    )
    parser.add_argument(
        "--sample-strategy",
        choices=["sequential", "stratified"],
        default="sequential",
        help=(
            "Record selection strategy. 'sequential' reviews records in file order. "
            "'stratified' balances review order across configured categories. "
            "Default: sequential."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow relabeling records that already have human labels.",
    )

    return parser.parse_args()


def main() -> None:
    """Run the human labeling CLI."""
    args = parse_args()

    input_path = VALIDATED_DIR / args.input
    output_path = LABELS_DIR / args.output

    if not input_path.exists():
        raise FileNotFoundError(f"Validated input file does not exist: {input_path}")

    records = load_records(input_path)
    existing_labels = load_existing_labels(output_path)

    if args.start_index < 0:
        raise ValueError("--start-index must be >= 0")

    if args.limit < 0:
        raise ValueError("--limit must be >= 0")

    records_to_review = select_records_for_review(
        records,
        start_index=args.start_index,
        existing_labels=existing_labels,
        overwrite=args.overwrite,
        sample_strategy=args.sample_strategy,
    )
    session_records = records_to_review[: args.limit]
    session_category_counts: dict[str, int] = {}

    for _, record in session_records:
        session_category_counts[record.category] = session_category_counts.get(record.category, 0) + 1

    reviewed_count = 0
    skipped_count = 0

    print("Step 3: Human labeling CLI")
    print("--------------------------")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Validated records available: {len(records)}")
    print(f"Existing human labels: {len(existing_labels)}")
    print(f"New label limit: {args.limit}")
    print(f"Sample strategy: {args.sample_strategy}")
    print(f"Reviewable records after start/label filters: {len(records_to_review)}")
    print(f"Planned records this session: {len(session_records)}")
    if args.sample_strategy == "stratified":
        print("Planned category mix:")
        for category in CATEGORIES:
            print(f"  {category}: {session_category_counts.get(category, 0)}")
    print()
    print("Input options:")
    print("  p / pass / 1 / y   = pass")
    print("  f / fail / 0 / n   = fail")
    print("  s / skip           = skip current item")
    print("  q / quit           = quit and save completed labels")
    print("  ? / help           = show rubric again")
    print()

    for visible_index, record in records_to_review:
        if reviewed_count >= args.limit:
            print(f"Reached label limit: {args.limit}")
            break

        display_record(record, item_number=visible_index, total_items=len(records))

        result = label_record(record)

        if result == "quit":
            print("Quitting. Completed labels have been saved.")
            break

        if result == "skip":
            skipped_count += 1
            print(f"Skipped {record.trace_id}.")
            continue

        existing_labels[record.trace_id] = result
        save_labels(output_path, existing_labels)

        reviewed_count += 1

        print()
        print(f"Saved label for {record.trace_id}.")
        print(f"New labels this session: {reviewed_count}")
        print(f"Total saved human labels: {len(existing_labels)}")

    save_labels(output_path, existing_labels)

    print()
    print("Human labeling session complete.")
    print(f"New labels saved this session: {reviewed_count}")
    print(f"Items skipped this session: {skipped_count}")
    print(f"Total human labels saved: {len(existing_labels)}")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()
