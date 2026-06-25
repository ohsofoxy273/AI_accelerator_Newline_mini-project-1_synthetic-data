"""Prompt templates for generator and LLM-as-judge."""

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
