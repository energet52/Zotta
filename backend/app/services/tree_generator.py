"""AI-powered decision tree generator using OpenAI.

Takes a natural language description of a lending strategy and generates
a complete decision tree structure with conditions and assessment nodes.
"""

import json
import logging
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a lending decision tree architect. Your job is to transform a
natural-language description of a lending strategy into a structured decision tree definition.

## Available routing attributes for conditions:

### Binary (true/false):
- is_existing_customer: Whether the applicant is an existing customer
- is_pre_approved: Whether the applicant was pre-approved
- has_adverse_records: Whether the applicant has adverse credit bureau records
- is_income_verified: Whether income has been verified
- is_approved_merchant: Whether the merchant is approved
- has_cross_default: Whether the applicant has cross-defaults
- is_topup_refinance: Whether this is a top-up or refinance

### Categorical (pick from specific values):
- employment_type: employed, self_employed, contract, part_time, not_employed, government_employee, retired
- bureau_file_status: thick, standard, thin, none
- income_band: below_5000, 5000_15000, 15000_30000, above_30000
- channel: branch, online, mobile, agent, api, pos
- relationship_status: new, existing_active, existing_dormant, previous, staff
- risk_band: A, B, C, D, E
- merchant_name: (free text — merchant names)
- geographic_region: (free text — region names)

### Numeric (comparisons with thresholds):
- monthly_income: Monthly income in TTD
- loan_amount: Loan amount requested in TTD
- age: Applicant age in years
- dti_ratio: Debt-to-income ratio (0.0-1.0+)
- ltv_ratio: Loan-to-value ratio
- application_score: Application scorecard score (points)
- loan_tenure_months: Loan term in months
- employment_tenure_months: Time at current employer in months
- net_disposable_income: Net disposable income in TTD
- total_exposure: Total credit exposure in TTD
- prior_loan_count: Number of previous loans

## Condition types:
- "binary": for true/false attributes. Branches have {"value": true} or {"value": false}
- "categorical": for category attributes. Branches have {"values": ["val1", "val2"]}
- "numeric_range": for numeric attributes. Branches have {"operator": ">=", "threshold": 5000}

## Tree node types:
- "annotation": Entry point node (always the root, label "Application Received")
- "condition": Branching node with an attribute and branches
- "assessment": Terminal node where business rules are evaluated

## Rules:
1. The root is ALWAYS an annotation node with label "Application Received"
2. Each condition branches into 2+ paths
3. Each path eventually leads to an assessment node
4. Assessment nodes should have descriptive names based on the path
5. Every branch of every condition MUST have a corresponding child node
6. Position nodes logically: root at top, children below, spread horizontally

## Response format:
Return valid JSON:
{
  "status": "complete" | "needs_clarification",
  "questions": ["..."],  // only if needs_clarification
  "tree": {              // only if complete
    "description": "Brief description of the strategy",
    "nodes": [
      {
        "node_key": "unique_key",
        "node_type": "annotation" | "condition" | "assessment",
        "label": "Display label",
        "condition_type": "binary" | "categorical" | "numeric_range" | null,
        "attribute": "field_name" | null,
        "branches": {"Branch Name": {"value": true}, ...} | null,
        "parent_node_key": "parent_key" | null,
        "branch_label": "which branch from parent" | null,
        "is_root": true | false,
        "position_x": 0,
        "position_y": 0,
        "assessment_name": "Name for this assessment" | null
      }
    ]
  },
  "explanation": "What this tree does"
}
"""


def generate_tree(
    prompt: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Generate a decision tree from a natural-language description."""

    api_key = settings.openai_api_key
    if not api_key:
        return {
            "status": "refused",
            "refusal_reason": "OpenAI API key is not configured.",
        }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        if result.get("status") == "complete" and result.get("tree"):
            _assign_positions(result["tree"]["nodes"])

        return result

    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response: %s", e)
        return {"status": "refused", "refusal_reason": f"AI returned invalid JSON: {e}"}
    except Exception as e:
        logger.error("Tree generation failed: %s", e)
        return {"status": "refused", "refusal_reason": f"AI generation failed: {e}"}


def _assign_positions(nodes: list[dict]):
    """Assign sensible x,y positions based on tree depth."""
    key_to_node = {n["node_key"]: n for n in nodes}
    root = next((n for n in nodes if n.get("is_root")), None)
    if not root:
        return

    def get_children(parent_key):
        return [n for n in nodes if n.get("parent_node_key") == parent_key]

    def layout(node_key, depth, x_offset, x_span):
        node = key_to_node.get(node_key)
        if not node:
            return
        node["position_y"] = depth * 160
        node["position_x"] = x_offset + x_span // 2

        children = get_children(node_key)
        if not children:
            return
        child_span = x_span // max(len(children), 1)
        for i, child in enumerate(children):
            layout(child["node_key"], depth + 1, x_offset + i * child_span, child_span)

    total_width = max(len(nodes) * 200, 800)
    layout(root["node_key"], 0, 0, total_width)
