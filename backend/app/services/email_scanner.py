"""
Email Scanner Service — Connects to email via IMAP and scans for receipts.
Identifies invoices, payment confirmations, and digital receipts.
"""
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from typing import Optional

from .receipt_scanner import ReceiptScanner


class EmailScanner:
    """Scans email inbox for receipts and invoices via IMAP."""

    # Common Israeli receipt sender patterns
    RECEIPT_SENDER_PATTERNS = [
        "invoice", "receipt", "חשבונית", "קבלה",
        "payment", "billing", "תשלום",
        "order", "הזמנה", "confirm",
        "noreply", "no-reply",
    ]

    RECEIPT_SUBJECT_PATTERNS = [
        "חשבונית", "קבלה", "אישור תשלום", "אישור הזמנה",
        "invoice", "receipt", "payment", "confirmation",
        "order confirm", "your order", "תשלום התקבל",
        "חשבונית מס", "חשבונית עסקה", "הקבלה שלך",
    ]

    def __init__(self):
        self.receipt_scanner = ReceiptScanner()

    def _decode_str(self, s: str) -> str:
        """Decode email header string."""
        if not s:
            return ""
        decoded_parts = decode_header(s)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(str(part))
        return " ".join(result)

    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
                    except Exception:
                        continue
                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                    except Exception:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
            except Exception:
                body = str(msg.get_payload())

        return body[:5000]  # Limit body length

    def _is_likely_receipt(self, subject: str, sender: str) -> bool:
        """Quick heuristic check if email might contain a receipt."""
        combined = f"{subject} {sender}".lower()
        return any(pattern in combined for pattern in self.RECEIPT_SUBJECT_PATTERNS + self.RECEIPT_SENDER_PATTERNS)

    async def scan_inbox(
        self,
        imap_server: str,
        email_address: str,
        password: str,
        imap_port: int = 993,
        days_back: int = 30,
        max_emails: int = 50,
    ) -> list[dict]:
        """Connect to IMAP and scan recent emails for receipts."""
        results = []

        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_address, password)
            mail.select("INBOX", readonly=True)

            # Search for recent emails
            since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%d-%b-%Y")
            _, message_ids = mail.search(None, f'(SINCE "{since_date}")')

            if not message_ids[0]:
                mail.logout()
                return []

            ids = message_ids[0].split()
            # Process most recent first, limit count
            ids = ids[-max_emails:]

            for msg_id in reversed(ids):
                try:
                    _, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if not msg_data or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = self._decode_str(msg.get("Subject", ""))
                    sender = self._decode_str(msg.get("From", ""))
                    date_str = msg.get("Date", "")

                    # Quick filter — only process likely receipts
                    if not self._is_likely_receipt(subject, sender):
                        continue

                    body = self._get_email_body(msg)
                    msg_date = None
                    try:
                        msg_date = parsedate_to_datetime(date_str)
                    except Exception:
                        pass

                    # Analyze with AI
                    scan_result = await self.receipt_scanner.scan_email_text(
                        subject=subject,
                        body=body,
                        sender=sender,
                    )

                    scan_result["email_subject"] = subject
                    scan_result["email_sender"] = sender
                    scan_result["email_date"] = msg_date.isoformat() if msg_date else None
                    scan_result["source_type"] = "email"
                    scan_result["source_ref"] = f"email:{msg_id.decode()}"

                    results.append(scan_result)

                except Exception as e:
                    results.append({
                        "is_receipt": False,
                        "error": f"Failed to process email: {str(e)}",
                        "email_id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                    })

            mail.logout()

        except imaplib.IMAP4.error as e:
            return [{"is_receipt": False, "error": f"IMAP login failed: {str(e)}"}]
        except Exception as e:
            return [{"is_receipt": False, "error": f"Email scan failed: {str(e)}"}]

        return results

    async def test_connection(
        self,
        imap_server: str,
        email_address: str,
        password: str,
        imap_port: int = 993,
    ) -> dict:
        """Test IMAP connection without scanning."""
        try:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_address, password)
            _, data = mail.select("INBOX", readonly=True)
            count = int(data[0]) if data[0] else 0
            mail.logout()
            return {"success": True, "message_count": count}
        except imaplib.IMAP4.error as e:
            return {"success": False, "error": f"IMAP error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
