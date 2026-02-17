"""Price tag photo parser using OpenAI Vision API.

Extracts item description, price, currency, merchant name, and category
from photos of price tags, shelf labels, invoices, and quote documents.
"""

import base64
import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

PARSE_PROMPT = """You are a price tag and receipt reader for a hire-purchase financing app in the Caribbean (Trinidad & Tobago, Jamaica, Barbados, Guyana).

Examine the image and extract product and pricing information. The image may be a:
- Printed retail price tag or shelf label
- Handwritten price label
- Digital screen (photographed)
- Quote document or proforma invoice
- Receipt or invoice

Extract the following and return ONLY a valid JSON object:

- item_description (string or null): What is being sold — include brand, model, size if visible.
  Examples: "Samsung 65-inch Crystal UHD TV", "3-Piece Living Room Set", "Whirlpool 9kg Front Load Washer"
- prices (array of objects): Each with {amount: number, label: string, currency: string}.
  If there are multiple prices (regular vs sale), include both. Label them "regular", "sale", "each", "total", etc.
- currency (string): The primary currency. Map to standard codes:
  TT$ or TTD → "TTD", J$ or JMD → "JMD", BDS$ or BBD → "BBD", GY$ or GYD → "GYD", US$ or USD → "USD".
  If no symbol is visible, default to "TTD".
- merchant_name (string or null): Store or vendor name if visible (from logo, letterhead, header).
- category_hint (string or null): Best guess category from:
  "furniture", "electronics", "appliances", "home_improvement", "automotive", "other"
- confidence (string): "high", "medium", or "low" — how confident you are in the extraction.

Rules:
- Return ONLY the JSON object. No markdown, no explanation.
- If price is partially obscured, give your best reading and set confidence to "low".
- Separate thousands correctly: "12,500" = 12500, not 12.5.
- If the image is too blurry or dark to read, return: {"error": "unreadable", "message": "I couldn't read this clearly. Try again with better lighting."}
"""


async def parse_price_tag(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> dict:
    """Send a price tag photo to OpenAI Vision and return extracted data.

    Returns a dict with extracted fields. On failure returns a dict with
    an 'error' key explaining what went wrong.
    """
    if not settings.openai_api_key or settings.openai_api_key in ("", "your-openai-api-key"):
        logger.warning("OpenAI API key not configured — returning empty parse result")
        return {"error": "no_api_key", "message": "Image parsing is not configured."}

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    raw = ""
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PARSE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{img_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=800,
            temperature=0.0,
        )

        raw = response.choices[0].message.content or ""
        logger.debug("Price tag Vision response received (%d chars)", len(raw))

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)

        # Normalise: pick best price
        if "prices" in parsed and parsed["prices"]:
            best = parsed["prices"][0]
            for p in parsed["prices"]:
                if p.get("label") in ("sale", "total"):
                    best = p
                    break
            parsed["price"] = best.get("amount")
            if not parsed.get("currency"):
                parsed["currency"] = best.get("currency", "TTD")

        logger.debug("Price tag parsing completed — %d fields extracted", len(parsed))
        return parsed

    except json.JSONDecodeError as exc:
        logger.warning("Price tag parser JSON decode error: %s — raw: %s", exc, raw[:200])
        return {"error": "parse_error", "message": "Could not read the price tag. Try a clearer photo.", "raw_text": raw}
    except Exception as exc:
        logger.error("OpenAI Vision call failed for price tag: %s: %s", type(exc).__name__, exc)
        return {"error": "api_error", "message": "Image processing is temporarily unavailable. Please enter details manually."}
