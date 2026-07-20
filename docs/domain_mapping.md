# Domain Mapping: Mini Project 1

## Original domain

DIY home repair customer support

## Adapted domain

Medical question bank customer support emails for a pathology/psychiatry exam-prep platform.

## Unit of data

One synthetic support case artifact: a customer support request, a customer-facing
support reply, and internal support metadata used to resolve or triage the case.

## Goal

Generate, validate, label, judge, analyze, and improve synthetic medical question bank customer support Q&A data while preserving the original project’s technical structure, quality dimensions, and success criteria.

## Required field mapping

| Required field      | Primary audience      | Medical question bank support meaning                                                                                     |
| ------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `question`          | Customer              | Customer email or support request                                                                                         |
| `answer`            | Customer              | Ideal support response draft that could be sent to the customer                                                           |
| `equipment_problem` | Internal/support      | Concise summary of the customer support issue being addressed; summarize the problem, not the answer                      |
| `tools_required`    | Internal/support      | Internal tools, resources, or information needed to resolve the issue                                                     |
| `steps`             | Internal/support      | Ordered support workflow steps; these may include customer actions that support should ask the customer to try            |
| `safety_info`       | Mostly support-facing | Privacy, billing, account-security, screenshot, or data-handling safeguard; may include customer-facing wording           |
| `tips`              | Support-facing        | Useful support-handling tips; customer-facing suggestions can pass when they are specific things support should recommend |

The generated record should be labeled as a whole support case artifact, not
only as an email. Minor audience mixing is acceptable when the field remains
useful and safe for support handling.

## Workflow realism rule

Evaluate support items against the intended real medical question bank workflow,
not generic SaaS plausibility.

Items should fail relevant dimensions when they invent unsupported product
workflows such as activation links, account recovery forms, fixed lockout periods,
automatic renewals, app-store subscriptions, prorated billing cycles, patient
charts, or clinical-care workflows.

Fluent and plausible text can still fail if it would mislead support staff or
customers about how the actual platform works.

## Five support categories

Each generated run should target approximately 20% coverage per category.

1. Login/account access
2. Billing/subscription/plan changes
3. Content access/activation
4. Technical bugs/device/browser issues
5. Institutional/invoice/documentation requests

## Adapted quality dimensions

| Dimension                | Adapted meaning                                                                                                                                                                                                                     |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1 Answer Completeness   | The support case contains enough information to resolve or appropriately triage the customer’s issue end to end, especially in the answer, workflow steps, requested information, and escalation path. Unsupported workflow assumptions can fail this dimension. |
| D2 Safety Specificity    | The case identifies a specific privacy, billing, account-security, screenshot, medical/private-information, or data-handling risk and gives a specific precaution. Generic statements such as “be careful with user data” fail.     |
| D3 Tool Realism          | The listed tools/resources are realistic for the intended medical question bank support workflow, such as admin dashboard, Stripe, support inbox, logs, user email, screenshots, receipts, or browser/device details. Unsupported product tools fail.           |
| D4 Scope Appropriateness | The answer and workflow stay within realistic support authority and clearly escalate issues that require engineering, billing review, admin approval, content review, or account verification. Unsupported authority or product workflows fail.                |
| D5 Context Clarity       | The customer issue, internal issue summary, and answer contain enough context to understand the problem, including relevant account, subscription, content-access, device, browser, billing, or institutional details when needed. Unsupported platform context can fail. |
| D6 Tip Usefulness        | The tips provide non-obvious, task-specific support advice that adds value beyond the workflow steps. Customer-facing troubleshooting suggestions can pass if they are useful things support should recommend.                     |

## Benchmark adaptation

The original project uses the Hugging Face DIY repair benchmark only as a category-distribution reference. The adapted version preserves that method by using a five-category support distribution with approximately 20% of generated items in each support category.

The benchmark is not used for labeling. Human labels and LLM-as-judge labels are applied only to the generated customer support items.

## Constraints preserved

This adaptation keeps the original project’s required technical approach:

* Python 3.10+
* Pydantic schema validation
* Instructor structured LLM outputs
* LLM generation and independent LLM-as-judge
* Human CLI labeling
* Step 2 data-quality gate
* Segment-level analysis and visualization
* Judge calibration before generator correction
* Before/after prompt improvement comparison
* Same success criteria and evaluation logic

## Final Prompt Variants

The completed project uses:

- Baseline generator: `GENERATOR_PROMPTS["baseline"]`
- Corrected generator: `GENERATOR_PROMPTS["corrected_content_access_v1"]`
- Calibrated judge: `JUDGE_PROMPTS["v6"]`

The corrected generator variant was targeted at the weakest baseline segment,
`content_access_activation`, after the judge reached at least 80% agreement with
human labels on all six dimensions.

See `docs/project_completion_summary.md` for final metrics and evidence files.
