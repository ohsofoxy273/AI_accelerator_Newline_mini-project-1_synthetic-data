# Mini Project 1: Medical Question Bank Support Synthetic Data

This project adapts the original DIY repair synthetic-data pipeline to medical
question bank customer support cases.

The pipeline generates structured 7-field support case artifacts, validates
them with a lightweight quality gate, collects human labels, calibrates an
LLM-as-judge, analyzes segment-level results, and applies a targeted generator
prompt correction.

## Setup

```bash
uv sync
```

Create a local `.env` with the model settings and OpenAI API key used by the
generation and judge steps. Do not commit `.env`.

## Pipeline

The six independently runnable steps are:

1. Generate structured support cases:

   ```bash
   uv run python -m mp1_support_pipeline.generate --prompt-variant baseline
   ```

2. Run the first-pass quality gate:

   ```bash
   uv run python -m mp1_support_pipeline.quality_gate --input generated_baseline.jsonl
   ```

3. Collect human labels:

   ```bash
   uv run python -m mp1_support_pipeline.human_label --sample-strategy stratified --limit 20
   ```

4. Run the LLM judge:

   ```bash
   uv run python -m mp1_support_pipeline.judge --input validated_baseline.jsonl --prompt-version v6
   ```

5. Analyze and visualize results:

   ```bash
   uv run python -m mp1_support_pipeline.analyze --judge-labels llm_judge_labels_generator-baseline_judge-v6_20260718_194819.jsonl
   ```

6. Iterate:

   Phase A calibrates the judge prompt until all six dimensions reach at least
   80% human/LLM agreement. Phase B uses the calibrated judge to identify the
   weakest generator segment and apply a targeted generator prompt correction.

## Final Result

Final calibrated judge prompt:

```text
JUDGE_PROMPTS["v6"]
```

Final corrected generator prompt:

```text
GENERATOR_PROMPTS["corrected_content_access_v1"]
```

Phase A calibration result on the human-labeled baseline subset:

```text
answer_completeness: 0.85
safety_specificity: 0.95
tool_realism: 0.90
scope_appropriateness: 0.90
context_clarity: 0.90
tip_usefulness: 0.80
overall_pass: 0.95
```

Phase B targeted correction:

```text
content_access_activation overall pass rate: 0.0 -> 1.0
overall judge pass rate: 0.0833 -> 1.0
```

Primary final evidence files:

```text
data/reports/analysis_generator-baseline_judge-v6_20260718_194909.json
data/reports/analysis_generator-corrected-content-access-v1_judge-v6_20260720_190910.json
logs/iteration_log.jsonl
visualizations/generator-corrected-content-access-v1_judge-v6_20260720_190910_*.png
```

See [docs/project_completion_summary.md](docs/project_completion_summary.md)
for the full summary of artifacts, commands, and results.
