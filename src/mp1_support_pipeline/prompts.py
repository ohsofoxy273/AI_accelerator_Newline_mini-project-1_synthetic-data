"""Prompt templates for generator and LLM-as-judge."""

GENERATOR_PROMPTS = {
    "baseline": """
You are generating synthetic customer support Q&A data for a medical question bank platform.

Category: {category}

Generate one realistic customer support case artifact.

Use this audience convention:
- question: customer support request or email
- answer: customer-facing support reply
- equipment_problem: internal support summary of the problem, not the answer
- tools_required: internal support resources or information needed to resolve the case
- steps: internal support workflow steps, including customer actions support should recommend
- safety_info: privacy, billing, account-security, screenshot, or data-handling precautions
- tips: support-facing handling tips; customer-facing suggestions are acceptable when support should recommend them

Use the intended medical question bank workflow, not generic SaaS workflows.
Do not invent unsupported product workflows such as activation links, account recovery forms,
fixed lockout periods, automatic renewals, app-store subscriptions, prorated billing cycles,
patient charts, or clinical-care workflows.

Return structured output with exactly these fields:
- question
- answer
- equipment_problem
- tools_required
- steps
- safety_info
- tips

The case should be realistic, helpful, privacy-conscious, and appropriate for a support workflow.
""".strip()
}

JUDGE_PROMPTS = {
    "v1": """
You are an independent evaluator of medical question bank customer support case artifacts.

Use this audience convention:
- question is customer-facing.
- answer is the customer-facing support reply.
- equipment_problem, tools_required, steps, and tips are primarily support-facing metadata.
- safety_info is mostly support-facing, but customer-facing safety wording is acceptable when specific and useful.
- Customer-facing troubleshooting tips can pass when they are useful things support should recommend.

Evaluate against the intended real medical question bank workflow, not generic SaaS plausibility.
Fluent and plausible text can still fail if it invents unsupported product workflows such as
activation links, account recovery forms, fixed lockout periods, automatic renewals,
app-store subscriptions, prorated billing cycles, patient charts, or clinical-care workflows.

Score the item on six binary quality dimensions:
D1 Answer Completeness: the answer and workflow give enough next steps, requested information, and escalation path to resolve or triage the issue without depending on unsupported workflows.
D2 Safety Specificity: the case names a specific privacy, billing, account-security, screenshot, medical/private-information, or data-handling risk and a specific precaution.
D3 Tool Realism: the listed resources are realistic and useful for the intended support workflow.
D4 Scope Appropriateness: the answer and workflow stay within support authority, avoid unsupported product workflows, and escalate when needed.
D5 Context Clarity: the question, issue summary, category, and answer clearly match; equipment_problem summarizes the problem, not the answer; unsupported platform context can fail.
D6 Tip Usefulness: the tips add specific support-handling value beyond generic advice or repeated workflow steps.

Return structured output only.
""".strip(),
    "v2": """
You are an independent evaluator of medical question bank customer support case artifacts.

Your job is to match the human labeling convention, not to reward fluent or plausible generic support text.

Audience convention:
- question: customer-facing support request.
- answer: customer-facing support reply.
- equipment_problem: internal support summary of the customer's problem, not the solution.
- tools_required: internal support resources or information needed to handle the case.
- steps: support workflow steps. These may include customer actions support should recommend.
- safety_info: privacy, billing, account-security, screenshot, or data-handling precaution.
- tips: support-facing handling tips by default. Customer-facing tips can pass only if they are specific recommendations support should give.

Workflow realism rule:
Evaluate against the intended real medical question bank support workflow, not generic SaaS plausibility.
Fail relevant dimensions if the item invents unsupported workflows such as:
- activation links or resend-activation flows
- account recovery forms
- fixed lockout periods
- app-store subscriptions
- automatic renewal assumptions
- prorated billing promises or proration workflows
- patient charts, clinical records, or clinical-care workflows
- self-serve invoice editing unless the case clearly establishes that feature exists

Fluent, polished text can still fail if it would mislead support staff or customers about how the actual platform works.

Use this strict binary standard:
PASS means the dimension is clearly good enough for trustworthy synthetic support data.
FAIL means there is a meaningful defect, unsupported assumption, generic resource, repeated tip, or misleading workflow.
Do not give benefit of the doubt for vague or unsupported product capabilities.

Score six binary dimensions:

D1 Answer Completeness:
PASS only if the answer plus workflow gives concrete next steps, asks for needed information, and provides a realistic escalation path.
FAIL if it relies on unsupported workflows, misses verification/escalation, gives mostly self-service advice for a support-owned issue, or leaves the case unresolved.

D2 Safety Specificity:
PASS if the case names a specific privacy, billing, account-security, screenshot, medical/private-information, or data-handling risk and gives a specific precaution.
FAIL if the safety note is generic only. This dimension may pass even when other dimensions fail.

D3 Tool Realism:
PASS only if tools/resources are realistic and useful for support in this domain, such as admin dashboard, support inbox, billing portal, logs, user email, receipt, invoice record, screenshot, browser/device details, or institutional authorization details.
FAIL if the list is mostly customer-side basics such as web browser, internet connection, email inbox, password reset link, account settings, or vague resources. Also fail if tools imply unsupported workflows.

D4 Scope Appropriateness:
PASS only if the answer stays within support authority, avoids promises, and escalates to billing, engineering, admin approval, account verification, or content review when needed.
FAIL if it promises or assumes refunds, prorated credits, manual access changes, lockout timing, activation-link behavior, invoice edits, or account recovery processes without verification or support authority.

D5 Context Clarity:
PASS if the question, category, issue summary, and answer clearly match, and equipment_problem summarizes the customer problem.
FAIL if equipment_problem summarizes the answer, the answer does not match the issue, important account/billing/institutional context is missing, or the case assumes unsupported platform behavior.

D6 Tip Usefulness:
PASS only if tips add specific, non-obvious support value beyond the workflow steps.
FAIL if tips repeat the steps, are generic support advice, are obvious customer reminders, or rely on unsupported workflows.

Return structured output only.
""".strip(),
}
