"""AV Knowles credit bureau web scraper for Trinidad & Tobago.

Since AV Knowles does not expose a REST API, this adapter uses Playwright
to automate the web portal: login, fill the search form, submit, and
scrape the results page.
"""

import asyncio
import base64
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.credit_bureau.adapter import CreditBureauAdapter

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://cdmsv2.avknowles.com/login"
_SEARCH_URL = "https://cdmsv2.avknowles.com/search-individual"

PURPOSE_MAP: Dict[str, str] = {
    "personal": "10",
    "personal_expenses": "10",
    "debt_consolidation": "1",
    "education": "2",
    "furniture": "3",
    "home_improvement": "4",
    "vehicle_insurance": "5",
    "investment": "6",
    "medical": "7",
    "mortgage": "8",
    "new_vehicle": "9",
    "savings": "11",
    "travel": "12",
    "used_vehicle": "13",
    "wedding": "14",
    "storage": "15",
    "other": "16",
    "hire_purchase": "3",
}

GENDER_MAP = {"male": "M", "female": "F", "m": "M", "f": "F"}
MARITAL_MAP = {"single": "S", "married": "M", "divorced": "D", "widowed": "W"}
TITLE_MAP = {"male": "mr", "female": "ms", "m": "mr", "f": "ms"}


class AVKnowlesWebAdapter(CreditBureauAdapter):
    """Headless-browser adapter that scrapes the AV Knowles CDMS portal."""

    def __init__(self):
        self.web_url = settings.av_knowles_web_url or _LOGIN_URL
        self.username = settings.av_knowles_username
        self.password = settings.av_knowles_password

    @property
    def provider_name(self) -> str:
        return "av_knowles_web"

    # ── public interface ───────────────────────────────

    async def pull_credit_report(self, national_id: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "Use run_web_inquiry() instead — it requires full applicant details."
        )

    async def check_health(self) -> bool:
        return bool(self.username and self.password)

    async def run_web_inquiry(
        self,
        *,
        first_name: str,
        last_name: str,
        middle_name: str = "",
        date_of_birth: str = "",
        gender: str = "",
        marital_status: str = "",
        national_id: str = "",
        drivers_permit: str = "",
        passport: str = "",
        address1: str = "",
        address2: str = "",
        city: str = "",
        country: str = "223",
        phone: str = "",
        cell: str = "",
        employer: str = "",
        occupation: str = "",
        amount: float = 0,
        purpose: str = "personal",
        on_step: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run a full credit bureau inquiry through the AV Knowles web portal.

        ``on_step`` is an optional async callback ``(step_number, message)``
        used to push progress updates to the frontend.
        """
        from playwright.async_api import async_playwright

        if not self.username or not self.password:
            raise RuntimeError(
                "AV Knowles web credentials not configured. "
                "Set AV_KNOWLES_USERNAME and AV_KNOWLES_PASSWORD in .env"
            )

        async def step(n: int, msg: str):
            logger.info("AVK step %d: %s", n, msg)
            if on_step:
                await on_step(n, msg)

        screenshot_b64 = ""
        results_url = ""
        page_text = ""
        search_summary: Dict[str, str] = {}
        result_entries: List[Dict[str, str]] = []
        entries_found = 0
        error_message = ""

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                # Step 1 – Navigate to login
                await step(1, "Connecting to AV Knowles CDMS portal…")
                await page.goto(self.web_url, wait_until="networkidle", timeout=30_000)

                # Step 2 – Fill credentials
                await step(2, "Entering login credentials…")
                await page.locator("#Username").fill(self.username)
                await page.locator("#Password").fill(self.password)
                cb = page.locator("#flexCheckDefault")
                if await cb.is_visible():
                    await cb.check()
                await page.locator("#LoginBtn").click()
                await page.wait_for_load_state("networkidle", timeout=30_000)
                await page.wait_for_timeout(1500)

                if "login" in page.url.lower():
                    error_message = "Login failed — check AV Knowles credentials."
                    raise RuntimeError(error_message)

                # Step 3 – Navigate to Credit Bureau search
                await step(3, "Opening Credit Bureau search form…")
                await page.goto(_SEARCH_URL, wait_until="networkidle", timeout=30_000)
                await page.wait_for_timeout(1000)

                # Step 4 – Fill form
                await step(4, "Populating applicant details…")
                title = TITLE_MAP.get(gender.lower(), "mr")
                await page.locator(f"#{title}").check()
                await page.locator("#FirstName").fill(first_name)
                if middle_name:
                    await page.locator("#MiddleName").fill(middle_name)
                await page.locator("#LastName").fill(last_name)
                if date_of_birth:
                    await page.locator("#DOB").fill(date_of_birth)
                g = GENDER_MAP.get(gender.lower(), "")
                if g:
                    await page.locator("#gender").select_option(g)
                ms = MARITAL_MAP.get(marital_status.lower(), "")
                if ms:
                    await page.locator("#maritial_status").select_option(ms)
                if drivers_permit:
                    await page.locator("#DriversPermit").fill(drivers_permit)
                if passport:
                    await page.locator("#Passport").fill(passport)
                if national_id:
                    await page.locator("#NationalId").fill(national_id)
                await page.locator("#Address1").fill(address1 or "N/A")
                if address2:
                    await page.locator("#Address2").fill(address2)
                if city:
                    await page.locator("#CityTown").fill(city)
                await page.locator("#Country").select_option(country)
                if phone:
                    await page.locator("#Phone").fill(phone.lstrip("+"))
                if cell:
                    await page.locator("#Cell").fill(cell.lstrip("+"))
                if employer:
                    await page.locator("#EmployerName").fill(employer)
                if occupation:
                    await page.locator("#Occupation").fill(occupation)
                await page.locator("#Amount").fill(str(int(amount)) if amount else "0")
                purpose_code = PURPOSE_MAP.get(purpose.lower(), "16")
                await page.locator("#Purpose").select_option(purpose_code)

                # Step 5 – Submit search
                await step(5, "Submitting inquiry to AV Knowles bureau…")
                await page.locator('input[type="submit"]').click()
                await page.wait_for_load_state("networkidle", timeout=60_000)
                await page.wait_for_timeout(3000)

                results_url = page.url

                # Step 6 – Scrape results
                await step(6, "Retrieving and parsing bureau results…")

                # Take screenshot
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                await page.screenshot(path=tmp_path, full_page=True)
                with open(tmp_path, "rb") as f:
                    screenshot_b64 = base64.b64encode(f.read()).decode()
                os.unlink(tmp_path)

                # Scrape text
                page_text = await page.evaluate("() => document.body?.innerText || ''")

                # Parse search criteria summary
                search_summary = await page.evaluate("""() => {
                    const summary = {};
                    const text = document.body?.innerText || '';
                    const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
                    let inSummary = false;
                    const knownKeys = ['Date', 'Name', 'DOB', 'Address', 'Amount', 'ID Card #', 'Drivers Permit #', 'Passport #'];
                    let pendingKey = null;
                    for (const line of lines) {
                        if (line.includes('Search Criteria Summary')) { inSummary = true; continue; }
                        if (line.includes('Individual Search Entries') || line.includes('Individual Search Results')) { inSummary = false; continue; }
                        if (inSummary) {
                            // Check if this line is a known key (with trailing colon)
                            const matchedKey = knownKeys.find(k => line === k + ':' || line.startsWith(k + ':'));
                            if (matchedKey) {
                                const afterColon = line.substring(matchedKey.length + 1).trim();
                                if (afterColon) {
                                    summary[matchedKey] = afterColon;
                                    pendingKey = null;
                                } else {
                                    pendingKey = matchedKey;
                                }
                            } else if (pendingKey) {
                                summary[pendingKey] = line;
                                pendingKey = null;
                            }
                        }
                    }
                    return summary;
                }""")

                # Parse entries count
                entries_found = await page.evaluate("""() => {
                    const text = document.body?.innerText || '';
                    const match = text.match(/(\\d+)\\s*Individual Search Entries Found/);
                    return match ? parseInt(match[1]) : 0;
                }""")

                # Parse result table rows
                result_entries = await page.evaluate("""() => {
                    const table = document.querySelector('table');
                    if (!table) return [];
                    const rows = Array.from(table.querySelectorAll('tr'));
                    const headers = Array.from(rows[0]?.querySelectorAll('th') || []).map(th => th.textContent?.trim() || '');
                    return rows.slice(1).map(row => {
                        const cells = Array.from(row.querySelectorAll('td'));
                        const obj = {};
                        cells.forEach((cell, i) => {
                            const key = headers[i] || ('col_' + i);
                            obj[key] = cell.textContent?.trim() || '';
                        });
                        return obj;
                    }).filter(r => {
                        const vals = Object.values(r);
                        return vals.length > 0 && !vals.every(v => v === '' || v === 'No Results Found');
                    });
                }""")

                # If there are results, try clicking first row for detail
                detail_data: Dict[str, Any] = {}
                if entries_found > 0 and len(result_entries) > 0:
                    await step(7, "Opening detailed credit report…")
                    first_row = page.locator("table tbody tr").first
                    if await first_row.is_visible():
                        await first_row.click()
                        await page.wait_for_load_state("networkidle", timeout=30_000)
                        await page.wait_for_timeout(3000)

                        # Screenshot of detail page
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp2:
                            tmp2_path = tmp2.name
                        await page.screenshot(path=tmp2_path, full_page=True)
                        with open(tmp2_path, "rb") as f2:
                            detail_screenshot = base64.b64encode(f2.read()).decode()
                        os.unlink(tmp2_path)
                        detail_data["screenshot_base64"] = detail_screenshot
                        detail_data["url"] = page.url
                        detail_data["text"] = await page.evaluate(
                            "() => document.body?.innerText || ''"
                        )

                await step(8 if entries_found > 0 else 7, "Inquiry complete.")

            except Exception as exc:
                if not error_message:
                    error_message = str(exc)
                logger.exception("AV Knowles web inquiry failed: %s", exc)
                # Still take screenshot on error if possible
                if not screenshot_b64:
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            tmp_path = tmp.name
                        await page.screenshot(path=tmp_path, full_page=True)
                        with open(tmp_path, "rb") as f:
                            screenshot_b64 = base64.b64encode(f.read()).decode()
                        os.unlink(tmp_path)
                    except Exception:
                        pass
            finally:
                await browser.close()

        return {
            "provider": "av_knowles_web",
            "inquiry_timestamp": datetime.now(timezone.utc).isoformat(),
            "results_url": results_url,
            "entries_found": entries_found,
            "search_summary": search_summary,
            "result_entries": result_entries,
            "detail": detail_data if entries_found > 0 else {},
            "screenshot_base64": screenshot_b64,
            "page_text": page_text,
            "error": error_message,
        }
