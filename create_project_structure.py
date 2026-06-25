"""
Create the folder and file structure for Mini Project 1.

Usage:
    python create_project_structure.py

This creates a uv-based Python project for the adapted Medical Question Bank
Customer Support Q&A Synthetic Data Generator.
"""

from pathlib import Path

PROJECT_NAME = "mini_project_1_pathdojo_support"
PACKAGE_NAME = "mp1_support_pipeline"

ROOT = Path(PROJECT_NAME)

FILES = {
    "README.md": """# Mini Project 1: Medical Question Bank Support Q&A Synthetic Data Generator

This project adapts the original DIY home repair customer support synthetic data pipeline
to medical question bank customer support emails.

## Goal

Generate, validate, label, judge, analyze, and improve synthetic customer support Q&A data.

## Setup

```bash
uv sync
```

## Run

Scripts will be added as the pipeline is implemented.

```bash
uv run python -m mp1_support_pipeline.generate
```
""",

    ".gitignore": """# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/
env/

# uv
uv.lock

# Environment variables / secrets
.env
.env.*

# Data outputs
data/raw/*.jsonl
data/raw/*.json
data/validated/*.jsonl
data/validated/*.json
data/labels/*.jsonl
data/labels/*.json
data/reports/*.json
logs/*.jsonl
logs/*.json
visualizations/*.png

# Keep directory placeholders
!data/raw/.gitkeep
!data/validated/.gitkeep
!data/labels/.gitkeep
!data/reports/.gitkeep
!logs/.gitkeep
!visualizations/.gitkeep

# OS/editor
.DS_Store
.vscode/
.idea/
""",

    ".env.example": """# Copy this file to .env and add your API keys.

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Example defaults
GENERATOR_MODEL=
JUDGE_MODEL=
""",

    "pyproject.toml": f"""[project]
name = "{PROJECT_NAME}"
version = "0.1.0"
description = "Synthetic customer support Q&A data generator and evaluation pipeline for medical question bank support emails."
readme = "README.md"
requires-python = ">=3.10"
authors = [
    {{ name = "Matthew Fox" }}
]
dependencies = [
    "pydantic>=2.0.0",
    "instructor>=1.0.0",
    "openai>=1.0.0",
    "pandas>=2.0.0",
    "matplotlib>=3.8.0",
    "seaborn>=0.13.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
    "black>=24.0.0",
]

[project.scripts]
mp1-generate = "{PACKAGE_NAME}.generate:main"
mp1-quality-gate = "{PACKAGE_NAME}.quality_gate:main"
mp1-human-label = "{PACKAGE_NAME}.human_label:main"
mp1-judge = "{PACKAGE_NAME}.judge:main"
mp1-analyze = "{PACKAGE_NAME}.analyze:main"
mp1-iterate = "{PACKAGE_NAME}.iterate:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
package = true

[tool.hatch.build.targets.wheel]
packages = ["src/{PACKAGE_NAME}"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.mypy]
python_version = "3.10"
strict = true
ignore_missing_imports = true
""",

    "docs/domain_mapping.md": """# Domain Mapping: Mini Project 1

## Original domain

DIY home repair customer support

## Adapted domain

Medical question bank customer support emails for a pathology/psychiatry exam-prep platform.

## Unit of data

One synthetic customer support request plus one ideal support response.

## Goal

Generate, validate, label, judge, analyze, and improve synthetic medical question bank customer support Q&A data while preserving the original project’s technical structure, quality dimensions, and success criteria.

## Required field mapping

| Required field | Medical question bank support meaning |
|---|---|
| `question` | Customer email or support request |
| `answer` | Ideal support response draft |
| `equipment_problem` | Specific customer support issue being addressed |
| `tools_required` | Internal tools, resources, or information needed to resolve the issue |
| `steps` | Ordered support workflow steps |
| `safety_info` | Privacy, billing, account-security, or data-handling safeguard |
| `tips` | Useful support-handling tip that improves the response or resolution process |

## Five support categories

Each generated run should target approximately 20% coverage per category.

1. Login/account access
2. Billing/subscription/plan changes
3. Content access/activation
4. Technical bugs/device/browser issues
5. Institutional/invoice/documentation requests

## Adapted quality dimensions

| Dimension | Adapted meaning |
|---|---|
| D1 Answer Completeness | The support response contains enough information to resolve or appropriately triage the customer’s issue end to end. |
| D2 Safety Specificity | The response identifies a specific privacy, billing, account-security, or data-handling risk and gives a specific precaution. Generic statements fail. |
| D3 Tool Realism | The listed tools/resources are realistic for a medical question bank support workflow, such as admin dashboard, Stripe, support inbox, logs, user email, screenshots, or browser/device details. |
| D4 Scope Appropriateness | The response stays within realistic support authority and clearly escalates issues requiring engineering, billing review, admin approval, or content review. |
| D5 Context Clarity | The customer issue and support response contain enough context to understand the problem. |
| D6 Tip Usefulness | The tip provides non-obvious, task-specific support advice that adds value beyond the workflow steps. |

## Benchmark adaptation

The original project uses the Hugging Face DIY repair benchmark only as a category-distribution reference. The adapted version preserves that method by using a five-category support distribution with approximately 20% of generated items in each support category.

The benchmark is not used for labeling. Human labels and LLM-as-judge labels are applied only to the generated customer support items.

## Constraints preserved

This adaptation keeps the original project's required technical approach:

- Python 3.10+
- Pydantic schema validation
- Instructor structured LLM outputs
- LLM generation and independent LLM-as-judge
- Human CLI labeling
- Step 2 data-quality gate
- Segment-level analysis and visualization
- Judge calibration before generator correction
- Before/after prompt improvement comparison
- Same success criteria and evaluation logic
""",

    f"src/{PACKAGE_NAME}/__init__.py": '"""Mini Project 1 support data pipeline."""\n',

    f"src/{PACKAGE_NAME}/config.py": '''"""Configuration constants for the mini project."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
VALIDATED_DIR = DATA_DIR / "validated"
LABELS_DIR = DATA_DIR / "labels"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
VISUALIZATIONS_DIR = PROJECT_ROOT / "visualizations"

CATEGORIES = [
    "login_account_access",
    "billing_subscription_plan_changes",
    "content_access_activation",
    "technical_bugs_device_browser",
    "institutional_invoice_documentation",
]

BENCHMARK_DISTRIBUTION = {
    category: 0.20 for category in CATEGORIES
}

QUALITY_DIMENSIONS = [
    "answer_completeness",
    "safety_specificity",
    "tool_realism",
    "scope_appropriateness",
    "context_clarity",
    "tip_usefulness",
]
''',

    f"src/{PACKAGE_NAME}/models.py": '''"""Pydantic models for generated items, labels, gates, and traces."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class QAItem(BaseModel):
    """Generated Q&A item using the required 7-field schema."""

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    equipment_problem: str = Field(min_length=1)
    tools_required: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=3)
    safety_info: str = Field(min_length=1)
    tips: list[str] = Field(min_length=1)


class GeneratedRecord(BaseModel):
    """Generated item plus metadata needed for traceability."""

    trace_id: str
    category: str
    prompt_variant: str
    model_name: str
    timestamp: datetime
    item: QAItem
    raw_response: str | None = None


class QualityLabel(BaseModel):
    """Human or LLM judge quality label using the required 6 dimensions."""

    trace_id: str
    labeler: Literal["human", "llm_judge"]
    answer_completeness: int = Field(ge=0, le=1)
    safety_specificity: int = Field(ge=0, le=1)
    tool_realism: int = Field(ge=0, le=1)
    scope_appropriateness: int = Field(ge=0, le=1)
    context_clarity: int = Field(ge=0, le=1)
    tip_usefulness: int = Field(ge=0, le=1)
    overall_pass: bool
    timestamp: datetime
    judge_prompt_version: str | None = None


class GateResult(BaseModel):
    """Step 2 quality gate result for one item."""

    trace_id: str
    passed: bool
    failed_checks: list[str] = Field(default_factory=list)
    timestamp: datetime


class TraceRecord(BaseModel):
    """Assembled trace record across generation, gate, human labels, and judge labels."""

    trace_id: str
    generated: GeneratedRecord | None = None
    gate_result: GateResult | None = None
    human_label: QualityLabel | None = None
    judge_label: QualityLabel | None = None
''',

    f"src/{PACKAGE_NAME}/prompts.py": '''"""Prompt templates for generator and LLM-as-judge."""

GENERATOR_PROMPTS = {
    "baseline": """
You are generating synthetic customer support Q&A data for a medical question bank platform.

Category: {category}

Generate one realistic customer support request and one ideal support response.

Return structured output with exactly these fields:
- question
- answer
- equipment_problem
- tools_required
- steps
- safety_info
- tips

The response should be realistic, helpful, privacy-conscious, and appropriate for a support workflow.
""".strip()
}

JUDGE_PROMPTS = {
    "v1": """
You are an independent evaluator of medical question bank customer support responses.

Score the item on six binary quality dimensions:
D1 Answer Completeness
D2 Safety Specificity
D3 Tool Realism
D4 Scope Appropriateness
D5 Context Clarity
D6 Tip Usefulness

Return structured output only.
""".strip()
}
''',

    f"src/{PACKAGE_NAME}/io_utils.py": '''"""Small JSON/JSONL helpers."""

import json
from pathlib import Path
from typing import Any, Iterable


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
''',

    f"src/{PACKAGE_NAME}/generate.py": '''"""Step 1: Generate synthetic Q&A items."""

def main() -> None:
    print("Step 1 placeholder: generation will be implemented here.")


if __name__ == "__main__":
    main()
''',

    f"src/{PACKAGE_NAME}/quality_gate.py": '''"""Step 2: Run schema, heuristic, deduplication, and distribution checks."""

def main() -> None:
    print("Step 2 placeholder: quality gate will be implemented here.")


if __name__ == "__main__":
    main()
''',

    f"src/{PACKAGE_NAME}/human_label.py": '''"""Step 3: Human CLI labeler."""

def main() -> None:
    print("Step 3 placeholder: human labeling CLI will be implemented here.")


if __name__ == "__main__":
    main()
''',

    f"src/{PACKAGE_NAME}/judge.py": '''"""Step 4: LLM-as-judge labeling."""

def main() -> None:
    print("Step 4 placeholder: LLM-as-judge will be implemented here.")


if __name__ == "__main__":
    main()
''',

    f"src/{PACKAGE_NAME}/analyze.py": '''"""Step 5: Analysis and visualization."""

def main() -> None:
    print("Step 5 placeholder: analysis and visualizations will be implemented here.")


if __name__ == "__main__":
    main()
''',

    f"src/{PACKAGE_NAME}/iterate.py": '''"""Step 6: Judge calibration and generator correction logs."""

def main() -> None:
    print("Step 6 placeholder: iteration logging will be implemented here.")


if __name__ == "__main__":
    main()
''',

    "data/raw/.gitkeep": "",
    "data/validated/.gitkeep": "",
    "data/labels/.gitkeep": "",
    "data/reports/.gitkeep": "",
    "logs/.gitkeep": "",
    "visualizations/.gitkeep": "",
}


def create_project() -> None:
    """Create the project directory and all starter files."""
    if ROOT.exists():
        raise FileExistsError(
            f"{ROOT} already exists. Rename it, delete it, or change PROJECT_NAME."
        )

    for relative_path, content in FILES.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    print(f"Created project structure at: {ROOT.resolve()}")
    print()
    print("Next steps:")
    print(f"  cd {PROJECT_NAME}")
    print("  uv sync")
    print("  cp .env.example .env")
    print("  uv run python -m mp1_support_pipeline.generate")
    print()
    print("Optional script entry points after uv sync:")
    print("  uv run mp1-generate")
    print("  uv run mp1-quality-gate")
    print("  uv run mp1-human-label")
    print("  uv run mp1-judge")
    print("  uv run mp1-analyze")
    print("  uv run mp1-iterate")


if __name__ == "__main__":
    create_project()
