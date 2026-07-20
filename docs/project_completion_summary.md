# Project Completion Summary

## Status

The mini-project pipeline is complete through Step 6.

The final accepted judge prompt is `JUDGE_PROMPTS["v6"]`.
The final corrected generator prompt is
`GENERATOR_PROMPTS["corrected_content_access_v1"]`.

## Architecture Implemented

The repository now supports the required six-step workflow:

1. Step 1 generation with Instructor/Pydantic structured output.
2. Step 2 lightweight quality gate with schema checks, D1-D6 pre-checks,
   deduplication, category distribution checks, validated JSONL output, reports,
   and per-item logs.
3. Step 3 human labeling CLI with sequential and stratified review modes.
4. Step 4 LLM-as-judge labeling with structured six-dimension output.
5. Step 5 analysis and visualization across quality gate results, human labels,
   judge labels, categories, prompt variants, and judge prompt versions.
6. Step 6 two-phase iteration:
   - Phase A: judge prompt calibration.
   - Phase B: targeted generator prompt correction.

All pipeline artifacts use semantic variant plus timestamp filenames. Generator
dependent artifacts include `generator-<variant>`. Judge-dependent artifacts
include `generator-<variant>_judge-<version>`.

## Step 6 Phase A: Judge Calibration

The baseline judge `v1` was too permissive. It passed most items that human
labels failed, especially for tool realism, scope appropriateness, and tip
usefulness.

Judge prompts were iterated through `v2`, `v3`, `v4`, `v5`, and `v6`. The final
accepted judge was `v6`.

Final `v6` agreement on the 20 human-labeled baseline records:

| Dimension | Agreement |
| --- | ---: |
| `answer_completeness` | 0.85 |
| `safety_specificity` | 0.95 |
| `tool_realism` | 0.90 |
| `scope_appropriateness` | 0.90 |
| `context_clarity` | 0.90 |
| `tip_usefulness` | 0.80 |
| `overall_pass` | 0.95 |

Phase A evidence:

```text
data/labels/llm_judge_labels_generator-baseline_judge-v6_20260718_194819.jsonl
logs/llm_judge_generator-baseline_judge-v6_20260718_194819.jsonl
data/reports/analysis_generator-baseline_judge-v6_20260718_194909.json
data/reports/trace_records_generator-baseline_judge-v6_20260718_194909.jsonl
logs/analysis_generator-baseline_judge-v6_20260718_194909.jsonl
visualizations/generator-baseline_judge-v6_20260718_194909_*.png
```

## Step 6 Phase B: Generator Correction

Using calibrated `judge-v6`, the weakest actionable baseline segment was
`content_access_activation`.

Baseline `content_access_activation` metrics:

| Metric | Value |
| --- | ---: |
| Count | 9 |
| Overall pass rate | 0.0 |
| `answer_completeness` | 0.1111 |
| `safety_specificity` | 1.0 |
| `tool_realism` | 0.0 |
| `scope_appropriateness` | 0.0 |
| `context_clarity` | 0.1111 |
| `tip_usefulness` | 0.2222 |

The correction hypothesis was that the baseline generator produced
content-access cases using unsupported activation-link and verification-email
workflows, customer-only tool lists, and vague access-sync assumptions. The
generator prompt was updated narrowly in `corrected_content_access_v1` to treat
content access issues as support-verifiable entitlement, purchase, account-email,
organization assignment, or access-record problems.

Corrected run commands:

```bash
uv run python -m mp1_support_pipeline.generate --prompt-variant corrected_content_access_v1
uv run python -m mp1_support_pipeline.quality_gate --input generated_generator-corrected-content-access-v1_20260720_190156.jsonl
uv run python -m mp1_support_pipeline.judge --input validated_generator-corrected-content-access-v1_20260720_190626.jsonl --prompt-version v6
uv run python -m mp1_support_pipeline.analyze --raw generated_generator-corrected-content-access-v1_20260720_190156.jsonl --validated validated_generator-corrected-content-access-v1_20260720_190626.jsonl --gate-log quality_gate_generator-corrected-content-access-v1_20260720_190626.jsonl --gate-report quality_gate_generator-corrected-content-access-v1_20260720_190626.json --judge-labels llm_judge_labels_generator-corrected-content-access-v1_judge-v6_20260720_190632.jsonl
```

Corrected `content_access_activation` metrics:

| Metric | Before | After |
| --- | ---: | ---: |
| Count | 9 | 10 |
| Overall pass rate | 0.0 | 1.0 |
| `answer_completeness` | 0.1111 | 1.0 |
| `safety_specificity` | 1.0 | 1.0 |
| `tool_realism` | 0.0 | 1.0 |
| `scope_appropriateness` | 0.0 | 1.0 |
| `context_clarity` | 0.1111 | 1.0 |
| `tip_usefulness` | 0.2222 | 1.0 |

Overall judge pass rate:

```text
baseline: 0.0833
corrected_content_access_v1: 1.0
```

The target category started at zero, so its improvement ratio is undefined.
The target category absolute gain is `+1.0`. The overall pass-rate improvement
ratio is approximately `12.0x`.

Phase B evidence:

```text
data/raw/generated_generator-corrected-content-access-v1_20260720_190156.jsonl
logs/generation_generator-corrected-content-access-v1_20260720_190156.jsonl
data/validated/validated_generator-corrected-content-access-v1_20260720_190626.jsonl
data/reports/quality_gate_generator-corrected-content-access-v1_20260720_190626.json
logs/quality_gate_generator-corrected-content-access-v1_20260720_190626.jsonl
data/labels/llm_judge_labels_generator-corrected-content-access-v1_judge-v6_20260720_190632.jsonl
logs/llm_judge_generator-corrected-content-access-v1_judge-v6_20260720_190632.jsonl
data/reports/analysis_generator-corrected-content-access-v1_judge-v6_20260720_190910.json
data/reports/trace_records_generator-corrected-content-access-v1_judge-v6_20260720_190910.jsonl
logs/analysis_generator-corrected-content-access-v1_judge-v6_20260720_190910.jsonl
visualizations/generator-corrected-content-access-v1_judge-v6_20260720_190910_*.png
```

The Step 6 iteration entry is recorded in:

```text
logs/iteration_log.jsonl
```

## Important Interpretation Note

The corrected generator run has different trace IDs from the baseline run, so
there is no human/LLM overlap for the corrected dataset. Step 5 therefore marks
human/LLM agreement as not evaluable for that corrected run. That is expected in
Phase B: the previously calibrated `judge-v6` is used as the trusted evaluator
for before/after generator comparison.
