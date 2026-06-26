"""Step 3: Human labeling CLI.

This script walks a human reviewer through validated synthetic Q&A records
and collects binary pass/fail labels across the six required quality dimensions.

Input:
    data/validated/validated_baseline.jsonl

Output:
    data/labels/human_labels_baseline.jsonl

Example:
    uv run python -m mp1_support_pipeline.human_label --limit 20
"""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mp1_support_pipeline.config import LABELS_DIR, QUALITY_DIMENSIONS, VALIDATED_DIR
from mp1_support_pipeline.models import GeneratedRecord, QualityLabel


DEFAULT_INPUT_FILENAME = "validated_baseline.jsonl"
DEFAULT_OUTPUT_FILENAME = "human_labels_baseline.jsonl"
DEFAULT_LIMIT = 20

DIMENSION_RUBRICS = {
    "answer_completeness": {
        "label": "D1 Answer Completeness",
        "question": "Does the support response contain enough information to resolve or appropriately triage the issue end to end?",
        "pass": "The response includes concrete next steps, relevant resources, safety/privacy handling, and a useful resolution or escalation path.",
        "fail": "The response is vague, incomplete, missing key steps, or leaves the customer/support agent unsure what to do next.",
    },
    "safety_specificity": {
        "label": "D2 Safety Specificity",
        "question": "Does the response identify a specific privacy, billing, account-security, or data-handling risk and give a specific precaution?",
        "pass": "The safety note names a relevant risk, such as account access, password reset, billing data, screenshots, subscription records, or institutional user data.",
        "fail": "The safety note is generic, such as 'be careful' or 'protect user data,' without a specific risk or precaution.",
    },
    "tool_realism": {
        "label": "D3 Tool Realism",
        "question": "Are the listed tools/resources realistic for a medical question bank support workflow?",
        "pass": "Resources are plausible, such as admin dashboard, support inbox, Stripe/billing portal, logs, screenshots, user email, browser/device details, or invoice records.",
        "fail": "Resources are vague, irrelevant, unavailable to support, or not actually useful for resolving the issue.",
    },
    "scope_appropriateness": {
        "label": "D4 Scope Appropriateness",
        "question": "Does the response stay within realistic support authority and escalate when needed?",
        "pass": "The response avoids overpromising and clearly escalates engineering, billing review, admin approval, or content review when appropriate.",
        "fail": "The response promises actions support cannot safely take, bypasses account/security processes, or gives inappropriate authority to frontline support.",
    },
    "context_clarity": {
        "label": "D5 Context Clarity",
        "question": "Is there enough context to understand the customer issue and why the response addresses it?",
        "pass": "The question, issue, and response include enough relevant account, subscription, content-access, browser/device, billing, or institutional context.",
        "fail": "The issue is too vague, the response does not clearly match the problem, or important context is missing.",
    },
    "tip_usefulness": {
        "label": "D6 Tip Usefulness",
        "question": "Does the tip add non-obvious, task-specific support value beyond the workflow steps?",
        "pass": "The tip would genuinely help a support agent handle the case better, faster, or more safely.",
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

    reviewed_count = 0
    skipped_count = 0

    print("Step 3: Human labeling CLI")
    print("--------------------------")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Validated records available: {len(records)}")
    print(f"Existing human labels: {len(existing_labels)}")
    print(f"New label limit: {args.limit}")
    print()
    print("Input options:")
    print("  p / pass / 1 / y   = pass")
    print("  f / fail / 0 / n   = fail")
    print("  s / skip           = skip current item")
    print("  q / quit           = quit and save completed labels")
    print("  ? / help           = show rubric again")
    print()

    records_to_review = records[args.start_index :]

    for visible_index, record in enumerate(records_to_review, start=args.start_index + 1):
        if reviewed_count >= args.limit:
            print(f"Reached label limit: {args.limit}")
            break

        if not args.overwrite and record.trace_id in existing_labels:
            continue

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
