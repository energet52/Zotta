"""AI-powered rule generator with safety guardrails.

Uses OpenAI GPT-4o to transform natural-language prompts into structured
underwriting rules.  Enforces a strict field whitelist and blocks any
rules based on protected characteristics (gender, race, religion, etc.).
"""

import json
import logging
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# ── Field whitelist ──────────────────────────────────────────────────────
# Only these fields may appear in generated rules.

ALLOWED_FIELDS: dict[str, dict[str, Any]] = {
    "applicant_age": {
        "label": "Applicant Age",
        "type": "number",
        "unit": "years",
        "description": "Age of the applicant in years",
    },
    "monthly_income": {
        "label": "Monthly Income",
        "type": "number",
        "unit": "TTD",
        "description": "Gross monthly income of the applicant in TTD",
    },
    "monthly_expenses": {
        "label": "Monthly Expenses",
        "type": "number",
        "unit": "TTD",
        "description": "Monthly living expenses of the applicant in TTD",
    },
    "existing_debt": {
        "label": "Existing Debt",
        "type": "number",
        "unit": "TTD",
        "description": "Total existing monthly debt obligations",
    },
    "years_employed": {
        "label": "Years Employed",
        "type": "number",
        "unit": "years",
        "description": "Number of years at current employer",
    },
    "employment_months": {
        "label": "Employment Months",
        "type": "number",
        "unit": "months",
        "description": "Employment tenure in months (years_employed * 12)",
    },
    "employment_type": {
        "label": "Employment Type",
        "type": "string",
        "values": ["employed", "self_employed", "contract", "unemployed", "retired"],
        "description": "Type of employment",
    },
    "credit_score": {
        "label": "Credit Score",
        "type": "number",
        "unit": "points",
        "description": "Internal credit score (300-850)",
    },
    "risk_band": {
        "label": "Risk Band",
        "type": "string",
        "values": ["A", "B", "C", "D", "E"],
        "description": "Risk band derived from credit score (A=best, E=worst)",
    },
    "debt_to_income_ratio": {
        "label": "Debt-to-Income Ratio",
        "type": "number",
        "unit": "ratio (0.0-1.0+)",
        "description": "Ratio of monthly debt to monthly income",
    },
    "loan_to_income_ratio": {
        "label": "Loan-to-Income Ratio",
        "type": "number",
        "unit": "ratio",
        "description": "Ratio of requested loan amount to annual income",
    },
    "loan_amount_requested": {
        "label": "Loan Amount Requested",
        "type": "number",
        "unit": "TTD",
        "description": "The loan amount the applicant is requesting",
    },
    "term_months": {
        "label": "Term (Months)",
        "type": "number",
        "unit": "months",
        "description": "Requested loan term in months",
    },
    "job_title": {
        "label": "Job Title",
        "type": "string",
        "description": "Applicant's job title / occupation",
    },
    "is_id_verified": {
        "label": "ID Verified",
        "type": "boolean",
        "description": "Whether the applicant's ID has been verified",
    },
}

ALLOWED_OPERATORS = ["gte", "lte", "gt", "lt", "eq", "neq", "in", "not_in", "between"]
ALLOWED_OUTCOMES = ["decline", "refer", "pass"]

# ── Blocked concepts ─────────────────────────────────────────────────────
BLOCKED_CONCEPTS = [
    "gender", "sex", "male", "female", "non-binary",
    "race", "ethnicity", "ethnic", "skin color", "colour",
    "religion", "religious", "christian", "muslim", "hindu", "jewish",
    "marital status", "married", "single", "divorced", "widowed",
    "nationality", "country of origin", "immigrant", "citizen",
    "disability", "disabled", "handicap",
    "sexual orientation", "gay", "lesbian", "bisexual", "transgender",
    "pregnancy", "pregnant",
    "political", "party affiliation",
]


# ── System prompt ────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    fields_desc = "\n".join(
        f"  - `{k}` ({v['type']}{', unit: ' + v.get('unit', '') if v.get('unit') else ''}): {v['description']}"
        for k, v in ALLOWED_FIELDS.items()
    )

    return f"""You are a lending underwriting rules assistant.  Your job is to
transform a human-language description of a business rule into a structured
JSON rule definition.

## Available data fields (ONLY these may be used):
{fields_desc}

## Allowed comparison operators:
gte (>=), lte (<=), gt (>), lt (<), eq (==), neq (!=), in, not_in, between

## Allowed outcomes:
decline — application is automatically declined
refer   — application is sent for manual review
pass    — rule produces a warning only (soft check)

## CRITICAL SAFETY RULES (you MUST refuse):
You MUST NEVER create rules based on gender, sex, race, ethnicity, religion,
marital status, nationality, country of origin, disability, sexual orientation,
pregnancy, or political affiliation.  If the user asks for such a rule, respond
with status "refused" and explain why.

## Response format:
Always respond with valid JSON matching this schema:

{{
  "status": "complete" | "needs_clarification" | "refused",
  "questions": ["question1", ...],    // only if status is "needs_clarification"
  "refusal_reason": "...",            // only if status is "refused"
  "rule": {{                           // only if status is "complete"
    "rule_id": "R_CUSTOM_XXX",
    "name": "Short descriptive name",
    "description": "Human-readable description with {{threshold}} placeholder",
    "field": "one of the allowed fields",
    "operator": "one of the allowed operators",
    "threshold": <number or string or list>,
    "outcome": "decline | refer | pass",
    "severity": "hard | refer | soft"
  }},
  "explanation": "Brief explanation of what this rule does"
}}

## When to ask clarifying questions:
- If the user doesn't specify a threshold value (e.g., "decline people with low income" — ask what TTD amount)
- If the user doesn't specify an outcome (decline vs refer vs pass)
- If the field is ambiguous (e.g., "debt" could mean existing_debt or debt_to_income_ratio)
- If the rule cannot be implemented with the available fields

Set severity to "hard" for decline, "refer" for refer, "soft" for pass outcomes.
Generate a rule_id starting with "R_CUSTOM_" followed by a short uppercase label.
"""


# ── Generator function ───────────────────────────────────────────────────

def generate_rule(
    prompt: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Generate a rule from a natural-language prompt.

    Parameters
    ----------
    prompt : str
        The user's natural-language rule description.
    conversation_history : list[dict] | None
        Previous messages (for follow-up after clarifying questions).

    Returns
    -------
    dict with keys: status, questions?, refusal_reason?, rule?, explanation?
    """

    # ── Pre-flight: check for blocked concepts in the prompt ─────────
    prompt_lower = prompt.lower()
    for concept in BLOCKED_CONCEPTS:
        if concept in prompt_lower:
            return {
                "status": "refused",
                "refusal_reason": (
                    f"Rules based on '{concept}' are not permitted. "
                    "Underwriting rules must not discriminate based on protected "
                    "characteristics such as gender, race, religion, marital status, "
                    "nationality, disability, or sexual orientation."
                ),
            }

    # ── Build messages ───────────────────────────────────────────────
    messages = [{"role": "system", "content": _build_system_prompt()}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": prompt})

    # ── Call OpenAI ──────────────────────────────────────────────────
    api_key = settings.openai_api_key
    if not api_key:
        return {
            "status": "refused",
            "refusal_reason": "OpenAI API key is not configured. Please set OPENAI_API_KEY.",
        }

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-5.2",  # strongest OpenAI model — best for structured output & reasoning
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_completion_tokens=1000,
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "status": "refused",
            "refusal_reason": "Failed to parse AI response. Please try rephrasing your rule.",
        }
    except Exception as e:
        logger.error("OpenAI rule generation failed: %s", e)
        return {
            "status": "refused",
            "refusal_reason": f"AI service error: {str(e)}",
        }

    # ── Post-generation validation ───────────────────────────────────
    if result.get("status") == "complete" and result.get("rule"):
        rule = result["rule"]
        validation_error = _validate_generated_rule(rule)
        if validation_error:
            return {
                "status": "refused",
                "refusal_reason": validation_error,
            }

    return result


def _validate_generated_rule(rule: dict) -> str | None:
    """Validate a generated rule against safety and schema constraints.
    Returns an error message string, or None if valid."""

    field = rule.get("field", "")
    if field not in ALLOWED_FIELDS:
        return f"Field '{field}' is not in the allowed fields list."

    operator = rule.get("operator", "")
    if operator not in ALLOWED_OPERATORS:
        return f"Operator '{operator}' is not allowed."

    outcome = rule.get("outcome", "")
    if outcome not in ALLOWED_OUTCOMES:
        return f"Outcome '{outcome}' is not allowed. Must be one of: {ALLOWED_OUTCOMES}"

    # Check description and name for blocked concepts
    text = f"{rule.get('name', '')} {rule.get('description', '')}".lower()
    for concept in BLOCKED_CONCEPTS:
        if concept in text:
            return f"Rule references blocked concept '{concept}'. Rules must not discriminate on protected characteristics."

    return None
