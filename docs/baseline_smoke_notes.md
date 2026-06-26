# Baseline Smoke Test Notes

Command:

`uv run python -m mp1_support_pipeline.generate --items-per-category 1 --output generated_smoke.jsonl --log-output generation_smoke.jsonl`

## Observations

- All 5 categories generated successfully.
- All items had the required 7 fields.
- `question` was understandable.
- `equipment_problem` was understandable and matched the issue or issues raised by the question.
- `tools_required` mostly contained realistic support resources, but sometimes included unnecessary or overly generic items such as `web browser`.
- `steps` were realistic for a general website support workflow, but the LLM does not know the actual medical question bank website processes or customer support flows, so the steps were not fully true-to-life for the real product.
- `safety_info` was often generic, such as warnings not to share private information or payment card details, although some items included more specific safeguards.
- `tips` were generally useful, but similar to `steps`, they lacked some true-to-life details about the actual support workflow.

## Preliminary failure pattern

The baseline prompt appears structurally adequate but under-specified for real product workflow details. The likely weak dimensions are:

- D2 Safety Specificity
- D3 Tool Realism
- D5 Context Clarity
- D6 Tip Usefulness

## Decision

Proceed to full baseline generation before implementing Step 2 quality gate. Do not improve the generator prompt yet, because these weaknesses should be measured first and used as evidence for a later prompt correction.