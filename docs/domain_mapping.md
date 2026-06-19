# Domain Mapping: Mini Project 1

## Original domain

DIY home repair customer support

## Adapted domain

Medical question bank customer support emails for a pathology/psychiatry exam-prep platform.

## Unit of data

One synthetic customer support request plus one ideal support response.

## Goal

Generate, validate, label, judge, analyze, and improve synthetic medical question bank customer support Q&A data while preserving the original project’s technical structure, quality dimensions, and success criteria.

## Required field mapping

| Required field      | Medical question bank support meaning                                        |
| ------------------- | ---------------------------------------------------------------------------- |
| `question`          | Customer email or support request                                            |
| `answer`            | Ideal support response draft                                                 |
| `equipment_problem` | Specific customer support issue being addressed                              |
| `tools_required`    | Internal tools, resources, or information needed to resolve the issue        |
| `steps`             | Ordered support workflow steps                                               |
| `safety_info`       | Privacy, billing, account-security, or data-handling safeguard               |
| `tips`              | Useful support-handling tip that improves the response or resolution process |

## Five support categories

Each generated run should target approximately 20% coverage per category.

1. Login/account access
2. Billing/subscription/plan changes
3. Content access/activation
4. Technical bugs/device/browser issues
5. Institutional/invoice/documentation requests

## Adapted quality dimensions

| Dimension                | Adapted meaning                                                                                                                                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1 Answer Completeness   | The support response contains enough information to resolve or appropriately triage the customer’s issue end to end.                                                                                       |
| D2 Safety Specificity    | The response identifies a specific privacy, billing, account-security, or data-handling risk and gives a specific precaution. Generic statements such as “be careful with user data” fail.                 |
| D3 Tool Realism          | The listed tools/resources are realistic for a medical question bank support workflow, such as admin dashboard, Stripe, support inbox, logs, user email, screenshots, or browser/device details.           |
| D4 Scope Appropriateness | The response stays within realistic support authority and clearly escalates issues that require engineering, billing review, admin approval, or content review.                                            |
| D5 Context Clarity       | The customer issue and support response contain enough context to understand the problem, including relevant account, subscription, content-access, device, browser, or institutional details when needed. |
| D6 Tip Usefulness        | The tip provides non-obvious, task-specific support advice that adds value beyond the workflow steps. Generic encouragement or restating a step fails.                                                     |

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
