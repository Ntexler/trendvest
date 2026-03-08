"""
Receipt Scanner Service — Uses Claude Vision API to extract receipt data from images.
Identifies vendor, amount, date, and classifies expense category for Israeli tax purposes.
"""
import os
import base64
import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

import anthropic


# Israeli tax deduction categories
DEDUCTION_CATEGORIES = {
    "office_supplies": "ציוד משרדי",
    "travel": "נסיעות",
    "meals": "ארוחות עסקיות",
    "phone_internet": "טלפון ואינטרנט",
    "software": "תוכנה ומנויים",
    "professional_services": "שירותים מקצועיים",
    "insurance": "ביטוח",
    "rent": "שכירות",
    "utilities": "חשמל/מים/גז",
    "vehicle": "רכב",
    "education": "השתלמות מקצועית",
    "marketing": "שיווק ופרסום",
    "equipment": "ציוד וחומרים",
    "medical": "הוצאות רפואיות",
    "donations": "תרומות",
    "other": "אחר",
}

RECEIPT_ANALYSIS_PROMPT = """You are an Israeli expense receipt analyzer. Analyze this image and extract receipt/invoice data.

Return a JSON object with these fields:
{
  "is_receipt": true/false,        // Is this actually a receipt/invoice/חשבונית?
  "vendor_name": "string",         // Business/vendor name
  "amount": 0.00,                  // Total amount (number only)
  "currency": "ILS",               // ILS, USD, EUR, etc.
  "receipt_date": "YYYY-MM-DD",    // Date on receipt, or null
  "receipt_number": "string",      // Invoice/receipt number, or ""
  "description": "string",         // Brief description of purchase (Hebrew OK)
  "category": "string",            // One of: office_supplies, travel, meals, phone_internet, software, professional_services, insurance, rent, utilities, vehicle, education, marketing, equipment, medical, donations, other
  "tax_deductible": true/false,    // Is this likely tax-deductible for Israeli tax purposes?
  "deduction_category": "string",  // If tax_deductible, which Israeli tax deduction category
  "confidence": 0.0-1.0,           // How confident are you in the extraction
  "vat_amount": 0.00,              // VAT (מע"מ) amount if visible, or null
  "business_number": "string"      // ח.פ./עוסק מורשה number if visible, or ""
}

Important rules:
- If the image is NOT a receipt/invoice, set is_receipt to false and fill minimal data
- For Israeli receipts, look for חשבונית מס, קבלה, חשבונית עסקה
- Identify if it has a valid business number (ח.פ. / עוסק מורשה / עוסק פטור)
- Common deductible expenses: office rent, phone/internet, professional tools, business travel
- Non-deductible: personal groceries, personal clothing, entertainment (unless business)
- Return ONLY the JSON object, no other text"""


EMAIL_RECEIPT_PROMPT = """You are an Israeli expense receipt analyzer. Analyze this email content and determine if it contains receipt/invoice information.

Return a JSON object with these fields:
{
  "is_receipt": true/false,
  "vendor_name": "string",
  "amount": 0.00,
  "currency": "ILS",
  "receipt_date": "YYYY-MM-DD",
  "receipt_number": "string",
  "description": "string",
  "category": "string",
  "tax_deductible": true/false,
  "deduction_category": "string",
  "confidence": 0.0-1.0
}

Categories: office_supplies, travel, meals, phone_internet, software, professional_services, insurance, rent, utilities, vehicle, education, marketing, equipment, medical, donations, other

Look for:
- Digital receipts / חשבונית דיגיטלית
- Payment confirmations / אישור תשלום
- Subscription receipts / קבלה על מנוי
- Order confirmations with amounts / אישור הזמנה

Return ONLY the JSON object."""


class ReceiptScanner:
    """Scans images and text for receipt data using Claude Vision."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.model = "claude-haiku-4-5-20251001"

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from Claude response."""
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting from code block
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding first { ... }
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"is_receipt": False, "confidence": 0, "error": "Failed to parse response"}

    async def scan_image(self, image_data: str, media_type: str = "image/jpeg") -> dict:
        """Scan an image (base64) for receipt data using Claude Vision."""
        if not self.client:
            return {"is_receipt": False, "error": "ANTHROPIC_API_KEY not configured", "confidence": 0}

        try:
            # Ensure we have clean base64
            if "," in image_data:
                image_data = image_data.split(",", 1)[1]

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": RECEIPT_ANALYSIS_PROMPT,
                        },
                    ],
                }],
            )

            result = self._parse_json_response(message.content[0].text)
            return result

        except Exception as e:
            return {"is_receipt": False, "error": str(e), "confidence": 0}

    async def scan_image_file(self, file_path: str) -> dict:
        """Scan an image file from disk."""
        path = Path(file_path)
        if not path.exists():
            return {"is_receipt": False, "error": f"File not found: {file_path}", "confidence": 0}

        suffix = path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/jpeg")

        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return await self.scan_image(image_data, media_type)

    async def scan_email_text(self, subject: str, body: str, sender: str = "") -> dict:
        """Analyze email text to extract receipt data."""
        if not self.client:
            return {"is_receipt": False, "error": "ANTHROPIC_API_KEY not configured", "confidence": 0}

        try:
            email_content = f"From: {sender}\nSubject: {subject}\n\n{body}"

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"{EMAIL_RECEIPT_PROMPT}\n\nEmail content:\n{email_content}",
                }],
            )

            return self._parse_json_response(message.content[0].text)

        except Exception as e:
            return {"is_receipt": False, "error": str(e), "confidence": 0}

    async def scan_folder(self, folder_path: str) -> list[dict]:
        """Scan all images in a folder for receipts."""
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            return []

        results = []
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

        for file in sorted(path.iterdir()):
            if file.suffix.lower() in image_extensions:
                result = await self.scan_image_file(str(file))
                result["source_file"] = str(file)
                result["filename"] = file.name
                results.append(result)

        return results

    def get_categories(self) -> dict:
        """Return available expense categories with Hebrew labels."""
        return DEDUCTION_CATEGORIES.copy()
