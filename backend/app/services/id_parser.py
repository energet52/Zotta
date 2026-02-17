"""ID document parsing service using OpenAI Vision API."""

import base64
import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

PARSE_PROMPT = """You are an ID document parser. You will receive images of the front and back of a government-issued identification document. This could be from ANY country. It could be a National ID card, a Driver's License / Driver's Permit, a Passport, or any other official photo ID.

Carefully examine BOTH images. Read ALL visible text, numbers, and details from the document — regardless of the language (Czech, Spanish, French, English, etc.).

Extract the following fields and return ONLY a valid JSON object with these keys:

- first_name (the person's given/first name, string or null)
- last_name (the person's family/last name / surname, string or null)
- date_of_birth (string in YYYY-MM-DD format, or null)
- id_type (one of "national_id", "drivers_license", "passport", "tax_number" — based on the type of document shown)
- national_id (the main ID/permit/license/passport number printed on the document, string or null)
- gender (one of "male", "female", "other", or null)
- address_line1 (street address, string or null)
- address_line2 (apartment/unit, string or null — leave null if not present)
- city (string or null)
- parish (string or null — this is the region/county/state/province)

Rules:
- Return ONLY the JSON object. No markdown fences, no explanation, no extra text.
- If a field cannot be determined from the images, set it to null.
- For date_of_birth, always convert to YYYY-MM-DD regardless of the format on the card.
- Normalise name casing to Title Case (e.g. "SOLDÁTKOVÁ" → "Soldatkova", "NATÁLIE" → "Natalie").
- For gender, map any indicator (M/F, Male/Female, MUŽI/ŽENY, etc.) to lowercase "male" or "female".
- For driver's licenses/permits: use the license/permit number as national_id.
- On EU-style driver's licenses: field 1 = last name, field 2 = first name, field 3 = date of birth, field 5 = license number.
- Look for information on BOTH the front and back of the document.
- Extract the place of birth or issuing authority as city if no address is present.
"""


async def parse_id_images(
    front_bytes: bytes,
    back_bytes: bytes,
    front_mime: str = "image/jpeg",
    back_mime: str = "image/jpeg",
) -> dict:
    """Send front and back ID images to OpenAI Vision and return parsed fields.

    Returns a dict with the extracted fields.  On any failure the dict
    will contain whatever could be parsed (possibly empty).
    """
    if not settings.openai_api_key or settings.openai_api_key in ("", "your-openai-api-key"):
        logger.warning("OpenAI API key not configured — returning empty parse result")
        return {}

    front_b64 = base64.b64encode(front_bytes).decode("utf-8")
    back_b64 = base64.b64encode(back_bytes).decode("utf-8")

    raw = ""
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4o",  # need full gpt-4o for vision; mini may not support images
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PARSE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{front_mime};base64,{front_b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{back_mime};base64,{back_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=600,
            temperature=0.0,
        )

        raw = response.choices[0].message.content or ""
        logger.debug("OpenAI Vision response received (%d chars)", len(raw))

        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (possibly ```json)
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)
        logger.debug("ID parsing completed successfully — %d fields extracted", len(parsed))
        return parsed

    except json.JSONDecodeError as exc:
        logger.warning("ID parser JSON decode error: %s", exc)
        return {"raw_text": raw or str(exc)}
    except Exception as exc:
        logger.error("OpenAI Vision call failed: %s: %s", type(exc).__name__, exc)
        return {}
