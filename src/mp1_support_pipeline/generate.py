"""Step 1: Generate synthetic Q&A items.

This script generates structured synthetic customer support Q&A items for the
medical question bank support domain.

Output:
    data/raw/generated_baseline.jsonl
    logs/generation_baseline.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import instructor
from dotenv import load_dotenv
from openai import OpenAI

from mp1_support_pipeline.config import CATEGORIES, LOGS_DIR, RAW_DIR
from mp1_support_pipeline.models import GeneratedRecord, QAItem
from mp1_support_pipeline.prompts import GENERATOR_PROMPTS


DEFAULT_ITEMS_PER_CATEGORY = 10
DEFAULT_PROMPT_VARIANT = "baseline"
DEFAULT_OUTPUT_FILENAME = "generated_baseline.jsonl"
DEFAULT_LOG_FILENAME = "generation_baseline.jsonl"


def ensure_dirs() -> None:
    """Create output directories if they do not already exist."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write rows to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_user_prompt(category: str, prompt_variant: str) -> str:
    """Fill the generator prompt template for one category."""
    template = GENERATOR_PROMPTS[prompt_variant]
    return template.format(category=category)


def make_client(model_name: str):
    """Create an Instructor client for structured OpenAI outputs."""
    # Instructor wraps the OpenAI client and adds response_model support.
    # This lets us request a QAItem directly instead of manually parsing JSON.
    return instructor.from_openai(OpenAI()), model_name


def generate_one_item(
    *,
    client,
    model_name: str,
    category: str,
    prompt_variant: str,
    trace_id: str,
    temperature: float,
    max_retries: int,
) -> GeneratedRecord:
    """Generate one structured Q&A item."""

    user_prompt = build_user_prompt(category=category, prompt_variant=prompt_variant)

    item: QAItem = client.chat.completions.create(
        model=model_name,
        response_model=QAItem,
        max_retries=max_retries,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate realistic synthetic customer support data. "
                    "Return only data that fits the requested schema. "
                    "Do not include real names, real emails, real institutions, "
                    "or real customer data."
                ),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    return GeneratedRecord(
        trace_id=trace_id,
        category=category,
        prompt_variant=prompt_variant,
        model_name=model_name,
        timestamp=datetime.now(),
        item=item,
        raw_response=None,
    )


def generate_dataset(
    *,
    items_per_category: int,
    prompt_variant: str,
    model_name: str,
    temperature: float,
    max_retries: int,
    sleep_seconds: float,
) -> tuple[list[GeneratedRecord], list[dict]]:
    """Generate a balanced dataset across all configured categories."""

    records: list[GeneratedRecord] = []
    logs: list[dict] = []

    for category in CATEGORIES:
        for index in range(items_per_category):
            trace_id = f"{prompt_variant}_{category}_{index + 1:03d}"

            try:
                print(f"Generating {trace_id}...")

                client, resolved_model_name = make_client(model_name)

                record = generate_one_item(
                    client=client,
                    model_name=resolved_model_name,
                    category=category,
                    prompt_variant=prompt_variant,
                    trace_id=trace_id,
                    temperature=temperature,
                    max_retries=max_retries,
                )

                records.append(record)

                logs.append(
                    {
                        "trace_id": trace_id,
                        "status": "success",
                        "category": category,
                        "prompt_variant": prompt_variant,
                        "model_name": resolved_model_name,
                        "timestamp": datetime.now().isoformat(),
                        "error": None,
                    }
                )

            except Exception as exc:
                logs.append(
                    {
                        "trace_id": trace_id,
                        "status": "error",
                        "category": category,
                        "prompt_variant": prompt_variant,
                        "model_name": model_name,
                        "timestamp": datetime.now().isoformat(),
                        "error": repr(exc),
                    }
                )
                print(f"  ERROR for {trace_id}: {exc!r}")

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return records, logs


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate synthetic support Q&A data.")

    parser.add_argument(
        "--items-per-category",
        type=int,
        default=DEFAULT_ITEMS_PER_CATEGORY,
        help="Number of items to generate per support category. Default: 10.",
    )
    parser.add_argument(
        "--prompt-variant",
        type=str,
        default=DEFAULT_PROMPT_VARIANT,
        help="Generator prompt variant from prompts.py. Default: baseline.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="OpenAI model name. Defaults to GENERATOR_MODEL from .env or gpt-5.4-mini.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.8,
        help="Generation temperature. Default: 0.8.",
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
        default=0.25,
        help="Delay between API calls. Default: 0.25.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_FILENAME,
        help=f"Output JSONL filename in data/raw/. Default: {DEFAULT_OUTPUT_FILENAME}.",
    )
    parser.add_argument(
        "--log-output",
        type=str,
        default=DEFAULT_LOG_FILENAME,
        help=f"Generation log filename in logs/. Default: {DEFAULT_LOG_FILENAME}.",
    )

    return parser.parse_args()


def main() -> None:
    """Generate synthetic Q&A records and save them to disk."""
    load_dotenv(override=True)
    ensure_dirs()

    args = parse_args()

    if args.prompt_variant not in GENERATOR_PROMPTS:
        valid_variants = ", ".join(GENERATOR_PROMPTS)
        raise ValueError(
            f"Unknown prompt variant: {args.prompt_variant}. "
            f"Valid variants: {valid_variants}"
        )

    model_name = args.model or os.getenv("GENERATOR_MODEL") or "gpt-5.4-mini"

    print("Step 1: Generate synthetic Q&A items")
    print("-----------------------------------")
    print(f"Model: {model_name}")
    print(f"Prompt variant: {args.prompt_variant}")
    print(f"Items per category: {args.items_per_category}")
    print(f"Total target items: {args.items_per_category * len(CATEGORIES)}")
    print()

    records, logs = generate_dataset(
        items_per_category=args.items_per_category,
        prompt_variant=args.prompt_variant,
        model_name=model_name,
        temperature=args.temperature,
        max_retries=args.max_retries,
        sleep_seconds=args.sleep_seconds,
    )

    output_path = RAW_DIR / args.output
    log_path = LOGS_DIR / args.log_output

    write_jsonl(
        output_path,
        [record.model_dump(mode="json") for record in records],
    )
    write_jsonl(log_path, logs)

    print()
    print("Generation complete.")
    print(f"Successful records: {len(records)}")
    print(f"Generation errors: {sum(1 for row in logs if row['status'] == 'error')}")
    print(f"Wrote data to: {output_path}")
    print(f"Wrote logs to: {log_path}")


if __name__ == "__main__":
    main()