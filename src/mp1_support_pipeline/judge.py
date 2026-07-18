"""Step 4: LLM-as-judge labeling.

This script scores validated synthetic support case artifacts using an LLM judge
and writes labels using the same QualityLabel model used by human labeling.

Input:
    data/validated/validated_baseline.jsonl

Output:
    data/labels/llm_judge_labels_generator-<prompt_variant>_judge-<prompt_version>_<run_id>.jsonl
    logs/llm_judge_generator-<prompt_variant>_judge-<prompt_version>_<run_id>.jsonl

Example:
    uv run python -m mp1_support_pipeline.judge --limit 48
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import instructor
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from mp1_support_pipeline.artifacts import artifact_filename, artifact_slug, default_run_id
from mp1_support_pipeline.config import LABELS_DIR, LOGS_DIR, VALIDATED_DIR
from mp1_support_pipeline.models import GeneratedRecord, QualityLabel
from mp1_support_pipeline.prompts import JUDGE_PROMPTS


DEFAULT_INPUT_FILENAME = "validated_baseline.jsonl"
DEFAULT_PROMPT_VERSION = "v1"
DEFAULT_LIMIT: int | None = None


class JudgeScores(BaseModel):
    """Structured score payload returned by the LLM judge."""

    answer_completeness: int = Field(ge=0, le=1)
    safety_specificity: int = Field(ge=0, le=1)
    tool_realism: int = Field(ge=0, le=1)
    scope_appropriateness: int = Field(ge=0, le=1)
    context_clarity: int = Field(ge=0, le=1)
    tip_usefulness: int = Field(ge=0, le=1)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file. Missing label/log files are treated as empty."""
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


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one row to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def serialize_raw_completion(completion: Any) -> str:
    """Serialize an LLM completion object for audit logging."""
    if hasattr(completion, "model_dump_json"):
        return str(completion.model_dump_json())

    return json.dumps(completion, ensure_ascii=False, default=str)


def load_records(path: Path) -> list[GeneratedRecord]:
    """Load validated generated records."""
    rows = read_jsonl(path)
    return [GeneratedRecord.model_validate(row) for row in rows]


def load_existing_judge_labels(path: Path) -> dict[str, QualityLabel]:
    """Load existing LLM judge labels keyed by trace_id."""
    rows = read_jsonl(path)
    labels: dict[str, QualityLabel] = {}

    for row in rows:
        label = QualityLabel.model_validate(row)
        if label.labeler == "llm_judge":
            labels[label.trace_id] = label

    return labels


def save_labels(path: Path, labels_by_trace_id: dict[str, QualityLabel]) -> None:
    """Save labels sorted by trace_id for stable output."""
    rows = [
        label.model_dump(mode="json")
        for _, label in sorted(labels_by_trace_id.items(), key=lambda item: item[0])
    ]
    write_jsonl(path, rows)


def infer_generator_variant(records: list[GeneratedRecord]) -> str:
    """Infer generator variant from validated records."""
    variants = {
        artifact_slug(record.prompt_variant)
        for record in records
        if record.prompt_variant
    }

    return next(iter(variants)) if len(variants) == 1 else "mixed"


def make_client() -> Any:
    """Create an Instructor-wrapped OpenAI client."""
    return instructor.from_openai(OpenAI())


def format_record_for_judge(record: GeneratedRecord) -> str:
    """Serialize the support case artifact for judge review."""
    item = record.item
    payload = {
        "trace_id": record.trace_id,
        "category": record.category,
        "prompt_variant": record.prompt_variant,
        "item": {
            "question": item.question,
            "answer": item.answer,
            "equipment_problem": item.equipment_problem,
            "tools_required": item.tools_required,
            "steps": item.steps,
            "safety_info": item.safety_info,
            "tips": item.tips,
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def judge_one_record(
    *,
    client: Any,
    record: GeneratedRecord,
    model_name: str,
    prompt_version: str,
    temperature: float,
    max_retries: int,
) -> tuple[QualityLabel, str]:
    """Score one validated record and return the label plus raw completion."""
    scores, completion = client.chat.completions.create_with_completion(
        model=model_name,
        response_model=JudgeScores,
        max_retries=max_retries,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": JUDGE_PROMPTS[prompt_version],
            },
            {
                "role": "user",
                "content": (
                    "Score this support case artifact. Return only the six "
                    "binary dimension fields defined in the response schema.\n\n"
                    f"{format_record_for_judge(record)}"
                ),
            },
        ],
    )

    score_values = scores.model_dump()
    overall_pass = all(value == 1 for value in score_values.values())

    label = QualityLabel(
        trace_id=record.trace_id,
        labeler="llm_judge",
        answer_completeness=scores.answer_completeness,
        safety_specificity=scores.safety_specificity,
        tool_realism=scores.tool_realism,
        scope_appropriateness=scores.scope_appropriateness,
        context_clarity=scores.context_clarity,
        tip_usefulness=scores.tip_usefulness,
        overall_pass=overall_pass,
        timestamp=datetime.now(),
        judge_prompt_version=prompt_version,
    )

    return label, serialize_raw_completion(completion)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Run LLM-as-judge labeling.")

    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT_FILENAME,
        help=f"Input JSONL filename in data/validated/. Default: {DEFAULT_INPUT_FILENAME}.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "Optional output JSONL filename in data/labels/. Default: "
            "llm_judge_labels_generator-<prompt_variant>_judge-<prompt_version>_<run_id>.jsonl."
        ),
    )
    parser.add_argument(
        "--log-output",
        type=str,
        default=None,
        help=(
            "Optional judge audit log JSONL filename in logs/. Default: "
            "llm_judge_generator-<prompt_variant>_judge-<prompt_version>_<run_id>.jsonl."
        ),
    )
    parser.add_argument(
        "--prompt-version",
        type=str,
        default=DEFAULT_PROMPT_VERSION,
        help=f"Judge prompt version from prompts.py. Default: {DEFAULT_PROMPT_VERSION}.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="OpenAI model name. Defaults to JUDGE_MODEL from .env or gpt-5.4-mini.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of new records to judge. Default: all remaining records.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start index within the validated records. Zero-based. Default: 0.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Judge temperature. Default: 0.0.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Instructor validation retry count. Default: 3.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Delay between judge calls. Default: 0.0.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow relabeling records that already have LLM judge labels.",
    )
    parser.add_argument(
        "--artifact-variant",
        type=str,
        default=None,
        help=(
            "Semantic variant used in generated artifact filenames. "
            "Default: generator-<prompt_variant>_judge-<prompt_version>."
        ),
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run identifier used in artifact filenames. Default: timestamp YYYYMMDD_HHMMSS.",
    )

    return parser.parse_args()


def main() -> None:
    """Run LLM-as-judge labeling."""
    load_dotenv(override=True)

    args = parse_args()

    if args.prompt_version not in JUDGE_PROMPTS:
        valid_versions = ", ".join(JUDGE_PROMPTS)
        raise ValueError(
            f"Unknown judge prompt version: {args.prompt_version}. "
            f"Valid versions: {valid_versions}"
        )

    if args.start_index < 0:
        raise ValueError("--start-index must be >= 0")

    if args.limit is not None and args.limit < 0:
        raise ValueError("--limit must be >= 0")

    input_path = VALIDATED_DIR / args.input

    if not input_path.exists():
        raise FileNotFoundError(f"Validated input file does not exist: {input_path}")

    records = load_records(input_path)
    run_id = args.run_id or default_run_id()
    generator_variant = infer_generator_variant(records)
    judge_variant = artifact_slug(args.prompt_version)
    artifact_variant = (
        args.artifact_variant
        or f"generator-{generator_variant}_judge-{judge_variant}"
    )
    output_filename = args.output or artifact_filename(
        artifact_name="llm_judge_labels",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="jsonl",
    )
    log_filename = args.log_output or artifact_filename(
        artifact_name="llm_judge",
        artifact_variant=artifact_variant,
        run_id=run_id,
        extension="jsonl",
    )
    output_path = LABELS_DIR / output_filename
    log_path = LOGS_DIR / log_filename
    existing_labels = load_existing_judge_labels(output_path)
    records_to_judge = [
        record
        for record in records[args.start_index :]
        if args.overwrite or record.trace_id not in existing_labels
    ]

    if args.limit is not None:
        records_to_judge = records_to_judge[: args.limit]

    model_name = args.model or os.getenv("JUDGE_MODEL") or "gpt-5.4-mini"

    print("Step 4: LLM-as-judge labeling")
    print("-----------------------------")
    print(f"Model: {model_name}")
    print(f"Prompt version: {args.prompt_version}")
    print(f"Artifact variant: {artifact_variant}")
    print(f"Run ID: {run_id}")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Audit log: {log_path}")
    print(f"Validated records available: {len(records)}")
    print(f"Existing LLM judge labels: {len(existing_labels)}")
    print(f"Records to judge this run: {len(records_to_judge)}")
    print()

    if not records_to_judge:
        save_labels(output_path, existing_labels)
        print("No records to judge.")
        return

    client = make_client()
    completed_count = 0
    error_count = 0

    for record in records_to_judge:
        print(f"Judging {record.trace_id}...")

        try:
            label, raw_response = judge_one_record(
                client=client,
                record=record,
                model_name=model_name,
                prompt_version=args.prompt_version,
                temperature=args.temperature,
                max_retries=args.max_retries,
            )
            existing_labels[record.trace_id] = label
            save_labels(output_path, existing_labels)
            append_jsonl(
                log_path,
                {
                    "trace_id": record.trace_id,
                    "status": "success",
                    "category": record.category,
                    "prompt_variant": record.prompt_variant,
                    "judge_prompt_version": args.prompt_version,
                    "model_name": model_name,
                    "timestamp": label.timestamp.isoformat(),
                    "scores": {
                        "answer_completeness": label.answer_completeness,
                        "safety_specificity": label.safety_specificity,
                        "tool_realism": label.tool_realism,
                        "scope_appropriateness": label.scope_appropriateness,
                        "context_clarity": label.context_clarity,
                        "tip_usefulness": label.tip_usefulness,
                    },
                    "overall_pass": label.overall_pass,
                    "raw_response": raw_response,
                    "error": None,
                },
            )
            completed_count += 1

        except Exception as exc:
            error_count += 1
            append_jsonl(
                log_path,
                {
                    "trace_id": record.trace_id,
                    "status": "error",
                    "category": record.category,
                    "prompt_variant": record.prompt_variant,
                    "judge_prompt_version": args.prompt_version,
                    "model_name": model_name,
                    "timestamp": datetime.now().isoformat(),
                    "scores": None,
                    "overall_pass": None,
                    "raw_response": None,
                    "error": repr(exc),
                },
            )
            print(f"  ERROR for {record.trace_id}: {exc!r}")

        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    print()
    print("LLM judge run complete.")
    print(f"New labels saved this run: {completed_count}")
    print(f"Errors this run: {error_count}")
    print(f"Total LLM judge labels saved: {len(existing_labels)}")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()
