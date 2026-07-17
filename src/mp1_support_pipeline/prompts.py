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
""".strip()
}
