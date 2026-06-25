"""Configuration constants for the mini project."""

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
