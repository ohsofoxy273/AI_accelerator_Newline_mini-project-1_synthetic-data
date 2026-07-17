# Human Labeling Guidelines

Use these conventions when assigning D1-D6 labels in Step 3.

For a faster but still category-balanced review, use stratified sampling:

```bash
uv run python -m mp1_support_pipeline.human_label --sample-strategy stratified --limit 20
```

With the five configured support categories, this selects approximately four
reviewable items per category when enough unlabeled items are available.

## Support Case Artifact Convention

For the adapted medical question bank support domain, each generated record is
a support case artifact, not only a customer email.

| Field | Primary audience | Labeling convention |
| --- | --- | --- |
| `question` | Customer | The customer support request or email. |
| `answer` | Customer | The reply that could be sent to the customer. |
| `equipment_problem` | Internal/support | A concise summary of the customer issue. It should summarize the problem, not the answer. |
| `tools_required` | Internal/support | Resources the support agent or platform would need, such as account dashboard, support inbox, Stripe/billing portal, logs, receipt, screenshot, user email, or device/browser details. |
| `steps` | Internal/support | Support workflow steps. They may include customer actions that support should ask the customer to try. |
| `safety_info` | Mostly support-facing | Privacy, billing, account-security, screenshot, medical/private-information, or data-handling precautions. Customer-facing safety wording is acceptable when specific and useful. |
| `tips` | Support-facing by default | Useful support-handling tips. Customer-facing troubleshooting suggestions can pass when they are specific things support should recommend to the customer. |

When in doubt, ask whether the record would help support handle the customer
issue safely, realistically, and clearly. Do not fail an item for minor awkwardness
if the dimension is still useful and safe.

## Workflow Realism Rule

Evaluate support items against the intended real medical question bank workflow,
not generic SaaS plausibility.

Fail the relevant dimensions when an item invents unsupported product workflows
that would mislead support staff or customers. Examples include activation links,
account recovery forms, fixed lockout periods, automatic renewals, app-store
subscriptions, prorated billing cycles, patient charts, and clinical-care
workflows.

Fluent and plausible text can still fail if it describes a workflow the actual
platform does not support. Apply this rule especially to D1, D3, D4, and D5:

- D1 can fail when the proposed resolution path depends on an unsupported workflow.
- D3 can fail when the listed tools/resources do not exist or are not available to support.
- D4 can fail when the answer gives support authority the real workflow does not allow.
- D5 can fail when the case context implies product behavior outside the intended platform.

## D1 Answer Completeness

Pass when the case gives enough information to resolve or appropriately triage
the issue end to end. Look especially at the answer, workflow steps, requested
information, and escalation path.

Pass examples:

- Gives concrete troubleshooting or resolution steps.
- Requests the right account, receipt, screenshot, browser, or device details.
- Explains what support will do next.
- Provides an escalation route when self-service cannot resolve the issue.

Fail examples:

- The answer is vague or too short.
- The record has no useful next steps.
- The case ends with "contact support" but gives no useful detail.
- Key workflow stages are missing.
- The answer depends on an unsupported workflow such as an account recovery form,
  activation link, or fixed lockout period.

## D2 Safety Specificity

Pass when the case names a specific support risk and gives a specific precaution.
This includes privacy, billing data, account security, screenshots, subscription
records, institutional data, passwords, verification codes, and medical/private
information.

Pass examples:

- Do not ask for or share passwords or one-time codes.
- Redact full card numbers or private medical details from screenshots.
- Verify account ownership before changing access or billing details.

Fail examples:

- "Be careful with user data."
- "Protect privacy."
- "Follow security guidelines."

Generic statements only pass if paired with a specific risk and action.

## D3 Tool Realism

Pass when the listed resources are realistic and useful for the support workflow.

Good resources include admin dashboard, account dashboard, support inbox,
Stripe or billing portal, payment history, purchase receipt, invoice record,
user email, browser/device details, screenshots, and logs.

Fail when the list is mostly vague, irrelevant, or unavailable for the case.

Examples that should usually fail:

- Patience
- Professionalism
- Common sense
- Good communication
- A generic web browser as the only meaningful resource
- Unsupported product resources such as activation links, account recovery forms,
  app-store subscription settings, patient charts, or clinical-care systems

A generic resource such as "web browser" does not automatically fail D3 when
the rest of the list contains useful support resources.

## D4 Scope Appropriateness

Pass when the answer and workflow stay within realistic support authority and
escalate appropriately.

Pass examples:

- Verify account ownership before refreshing access.
- Escalate technical bugs to engineering.
- Escalate refund exceptions to billing or admin review.
- Avoid promising account, billing, or access changes before verification.

Fail examples:

- "Send us your password."
- "We will immediately refund you" without review.
- "We can manually change any account."
- "Ignore the institutional admin and we will add you directly."
- "We guarantee access will be restored today."
- "Use the clinical chart" or "follow the patient-care escalation workflow" for
  a platform that is only an exam-prep question bank.

## D5 Context Clarity

Pass when the customer issue, internal issue summary, category, and answer all
match and provide enough context to understand the case.

`equipment_problem` should summarize the problem, not the proposed answer.

Good example:

> Paid course content is not appearing after login; access or activation may not
> have synced to the correct account.

Bad example:

> Tell the customer to clear cache and send a screenshot.

Fail when the issue is too vague, the answer does not match the problem, or key
context is missing.

## D6 Tip Usefulness

Pass when the tips add specific, useful support value beyond generic behavior.
Tips are support-facing by default, but customer-facing troubleshooting suggestions
can pass when they are useful things support should recommend.

Pass examples:

- Suggest an incognito window to rule out cached session state.
- Check spam or promotions folders for activation or receipt emails.
- Ask for screenshots with full card numbers and private medical information redacted.
- Check whether the receipt email differs from the login email before escalating.

Fail examples:

- Be polite.
- Respond quickly.
- Follow up with the customer.
- Keep the customer happy.
- Check the issue carefully.

## Overall Pass

`overall_pass` is true only when all six dimensions pass. Use fail for a dimension
when the issue is substantial enough that the item should not be trusted as
high-quality synthetic data for that dimension.
