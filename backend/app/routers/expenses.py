"""
Expense Receipt Bot router — scan, catalog, and export receipts for Israeli tax filing.
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from ..models.schemas import (
    ReceiptScanRequest, ReceiptManualEntry, ReceiptResponse,
    ReceiptExportResponse, EmailConfigRequest, ScanScheduleRequest,
    ReceiptUpdateRequest,
)
from ..deps import get_db_pool
from ..services.receipt_scanner import ReceiptScanner, DEDUCTION_CATEGORIES
from ..services.email_scanner import EmailScanner
from ..services.expense_scheduler import expense_scheduler

router = APIRouter(prefix="/api/expenses", tags=["expenses"])

scanner = ReceiptScanner()
email_scanner = EmailScanner()


# ── Helper ──

def _row_to_receipt(row) -> dict:
    return {
        "id": row["id"],
        "vendor_name": row["vendor_name"],
        "amount": row["amount"],
        "currency": row["currency"],
        "receipt_date": str(row["receipt_date"]) if row["receipt_date"] else None,
        "receipt_number": row["receipt_number"] or "",
        "description": row["description"] or "",
        "category": row["category"],
        "tax_deductible": row["tax_deductible"],
        "deduction_category": row["deduction_category"],
        "confidence_score": row["confidence_score"],
        "source_type": row["source_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "has_image": bool(row["image_data"]),
    }


# ══════════════════════════════════════
# RECEIPT SCANNING
# ══════════════════════════════════════

@router.post("/scan")
async def scan_receipt(body: ReceiptScanRequest, session_id: str = Query(...), pool=Depends(get_db_pool)):
    """Scan an image for receipt data using AI vision."""
    result = await scanner.scan_image(body.image_data, body.media_type)

    if not result.get("is_receipt"):
        return {"is_receipt": False, "message": "No receipt detected in image", "raw": result}

    # Save to database
    async with pool.acquire() as conn:
        receipt_id = await conn.fetchval("""
            INSERT INTO expense_receipts
                (session_id, vendor_name, amount, currency, receipt_date,
                 receipt_number, description, category, tax_deductible,
                 deduction_category, confidence_score, source_type,
                 original_filename, image_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING id
        """,
            session_id,
            result.get("vendor_name", ""),
            float(result.get("amount", 0)),
            result.get("currency", "ILS"),
            result.get("receipt_date"),
            result.get("receipt_number", ""),
            result.get("description", ""),
            result.get("category", "other"),
            result.get("tax_deductible", False),
            result.get("deduction_category"),
            float(result.get("confidence", 0)),
            body.source_type,
            body.original_filename,
            body.image_data[:100],  # Store thumbnail reference only
        )

    return {
        "is_receipt": True,
        "receipt_id": receipt_id,
        "data": result,
    }


@router.post("/manual")
async def add_manual_receipt(body: ReceiptManualEntry, session_id: str = Query(...), pool=Depends(get_db_pool)):
    """Add a receipt manually."""
    async with pool.acquire() as conn:
        receipt_id = await conn.fetchval("""
            INSERT INTO expense_receipts
                (session_id, vendor_name, amount, currency, receipt_date,
                 receipt_number, description, category, tax_deductible,
                 deduction_category, confidence_score, source_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 1.0, 'manual')
            RETURNING id
        """,
            session_id,
            body.vendor_name,
            body.amount,
            body.currency,
            body.receipt_date,
            body.receipt_number,
            body.description,
            body.category,
            body.tax_deductible,
            body.deduction_category,
        )

    return {"receipt_id": receipt_id, "status": "created"}


# ══════════════════════════════════════
# RECEIPT MANAGEMENT
# ══════════════════════════════════════

@router.get("/list")
async def list_receipts(
    session_id: str = Query(...),
    status: str | None = None,
    category: str | None = None,
    tax_deductible: bool | None = None,
    sort_by: str = "date_desc",
    pool=Depends(get_db_pool),
):
    """List all receipts for a session with optional filters."""
    query = "SELECT * FROM expense_receipts WHERE session_id = $1"
    params = [session_id]
    idx = 2

    if status:
        query += f" AND status = ${idx}"
        params.append(status)
        idx += 1
    if category:
        query += f" AND category = ${idx}"
        params.append(category)
        idx += 1
    if tax_deductible is not None:
        query += f" AND tax_deductible = ${idx}"
        params.append(tax_deductible)
        idx += 1

    order = {
        "date_desc": "created_at DESC",
        "date_asc": "created_at ASC",
        "amount_desc": "amount DESC",
        "amount_asc": "amount ASC",
        "vendor": "vendor_name ASC",
    }.get(sort_by, "created_at DESC")

    query += f" ORDER BY {order}"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [_row_to_receipt(r) for r in rows]


@router.get("/receipt/{receipt_id}")
async def get_receipt(receipt_id: int, session_id: str = Query(...), pool=Depends(get_db_pool)):
    """Get a single receipt by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM expense_receipts WHERE id = $1 AND session_id = $2",
            receipt_id, session_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return _row_to_receipt(row)


@router.put("/receipt/{receipt_id}")
async def update_receipt(
    receipt_id: int,
    body: ReceiptUpdateRequest,
    session_id: str = Query(...),
    pool=Depends(get_db_pool),
):
    """Update receipt fields (for manual corrections)."""
    updates = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            updates[field] = value

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params = []
    idx = 1
    for key, val in updates.items():
        set_clauses.append(f"{key} = ${idx}")
        params.append(val)
        idx += 1

    params.extend([receipt_id, session_id])
    query = f"""
        UPDATE expense_receipts
        SET {', '.join(set_clauses)}, updated_at = NOW()
        WHERE id = ${idx} AND session_id = ${idx + 1}
        RETURNING id
    """

    async with pool.acquire() as conn:
        result = await conn.fetchval(query, *params)

    if not result:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"status": "updated", "receipt_id": result}


@router.delete("/receipt/{receipt_id}")
async def delete_receipt(receipt_id: int, session_id: str = Query(...), pool=Depends(get_db_pool)):
    """Delete a receipt."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "DELETE FROM expense_receipts WHERE id = $1 AND session_id = $2 RETURNING id",
            receipt_id, session_id,
        )
    if not result:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"status": "deleted"}


# ══════════════════════════════════════
# EXPORT & SUMMARY
# ══════════════════════════════════════

@router.get("/summary")
async def get_summary(session_id: str = Query(...), pool=Depends(get_db_pool)):
    """Get expense summary with totals by category."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM expense_receipts WHERE session_id = $1 ORDER BY created_at DESC",
            session_id,
        )

    total_amount = 0.0
    tax_deductible_amount = 0.0
    by_category: dict[str, float] = {}

    receipts = []
    for r in rows:
        receipt = _row_to_receipt(r)
        receipts.append(receipt)
        total_amount += r["amount"]
        if r["tax_deductible"]:
            tax_deductible_amount += r["amount"]
        cat = r["category"]
        by_category[cat] = by_category.get(cat, 0) + r["amount"]

    return {
        "total_receipts": len(receipts),
        "total_amount": round(total_amount, 2),
        "tax_deductible_amount": round(tax_deductible_amount, 2),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "receipts": receipts,
    }


@router.get("/export")
async def export_receipts(
    session_id: str = Query(...),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    tax_deductible_only: bool = False,
    pool=Depends(get_db_pool),
):
    """Export receipts for tax filing / חשבונית ירוקה upload."""
    query = "SELECT * FROM expense_receipts WHERE session_id = $1"
    params = [session_id]

    if tax_deductible_only:
        query += " AND tax_deductible = true"

    query += " ORDER BY receipt_date ASC, created_at ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    receipts = [_row_to_receipt(r) for r in rows]

    if format == "csv":
        lines = ["תאריך,ספק,סכום,מטבע,קטגוריה,מספר קבלה,ניכוי מס,תיאור"]
        for r in receipts:
            cat_he = DEDUCTION_CATEGORIES.get(r["category"], r["category"])
            lines.append(
                f'{r["receipt_date"] or ""},"{r["vendor_name"]}",{r["amount"]},'
                f'{r["currency"]},"{cat_he}",{r["receipt_number"]},'
                f'{"כן" if r["tax_deductible"] else "לא"},"{r["description"]}"'
            )
        return {"format": "csv", "data": "\n".join(lines), "count": len(receipts)}

    total = sum(r["amount"] for r in receipts)
    deductible = sum(r["amount"] for r in receipts if r["tax_deductible"])

    return {
        "format": "json",
        "count": len(receipts),
        "total_amount": round(total, 2),
        "tax_deductible_amount": round(deductible, 2),
        "receipts": receipts,
    }


# ══════════════════════════════════════
# EMAIL SCANNING
# ══════════════════════════════════════

@router.post("/email/test")
async def test_email_connection(body: EmailConfigRequest):
    """Test IMAP email connection."""
    result = await email_scanner.test_connection(
        imap_server=body.imap_server,
        email_address=body.email_address,
        password=body.password,
        imap_port=body.imap_port,
    )
    return result


@router.post("/email/scan")
async def scan_emails(
    body: EmailConfigRequest,
    session_id: str = Query(...),
    days_back: int = Query(default=30, ge=1, le=365),
    pool=Depends(get_db_pool),
):
    """Scan email inbox for receipts."""
    results = await email_scanner.scan_inbox(
        imap_server=body.imap_server,
        email_address=body.email_address,
        password=body.password,
        imap_port=body.imap_port,
        days_back=days_back,
    )

    saved_count = 0
    receipts_found = []

    for result in results:
        if result.get("is_receipt"):
            async with pool.acquire() as conn:
                receipt_id = await conn.fetchval("""
                    INSERT INTO expense_receipts
                        (session_id, vendor_name, amount, currency, receipt_date,
                         receipt_number, description, category, tax_deductible,
                         deduction_category, confidence_score, source_type, source_ref)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'email', $12)
                    RETURNING id
                """,
                    session_id,
                    result.get("vendor_name", ""),
                    float(result.get("amount", 0)),
                    result.get("currency", "ILS"),
                    result.get("receipt_date"),
                    result.get("receipt_number", ""),
                    result.get("description", ""),
                    result.get("category", "other"),
                    result.get("tax_deductible", False),
                    result.get("deduction_category"),
                    float(result.get("confidence", 0)),
                    result.get("source_ref", ""),
                )
                result["receipt_id"] = receipt_id
                saved_count += 1
                receipts_found.append(result)

    return {
        "emails_scanned": len(results),
        "receipts_found": saved_count,
        "receipts": receipts_found,
    }


# ══════════════════════════════════════
# SCAN SCHEDULING
# ══════════════════════════════════════

@router.post("/schedule")
async def set_scan_schedule(
    body: ScanScheduleRequest,
    session_id: str = Query(...),
    pool=Depends(get_db_pool),
):
    """Configure automatic scanning schedule."""
    now = datetime.now(timezone.utc)
    next_scan = now + timedelta(hours=body.scan_interval_hours) if body.is_active else None

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO expense_scan_schedules
                (session_id, scan_interval_hours, scan_screenshots, scan_emails,
                 screenshot_folder, is_active, next_scan_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (session_id) DO UPDATE SET
                scan_interval_hours = EXCLUDED.scan_interval_hours,
                scan_screenshots = EXCLUDED.scan_screenshots,
                scan_emails = EXCLUDED.scan_emails,
                screenshot_folder = EXCLUDED.screenshot_folder,
                is_active = EXCLUDED.is_active,
                next_scan_at = EXCLUDED.next_scan_at
        """,
            session_id,
            body.scan_interval_hours,
            body.scan_screenshots,
            body.scan_emails,
            body.screenshot_folder,
            body.is_active,
            next_scan,
        )

    if body.is_active:
        # Note: actual background scheduling would require the email config
        return {"status": "scheduled", "next_scan_at": next_scan.isoformat() if next_scan else None}
    else:
        await expense_scheduler.stop_schedule(session_id)
        return {"status": "stopped"}


@router.get("/schedule")
async def get_scan_schedule(session_id: str = Query(...), pool=Depends(get_db_pool)):
    """Get current scan schedule."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM expense_scan_schedules WHERE session_id = $1", session_id,
        )
    if not row:
        return {
            "is_active": False,
            "scan_interval_hours": 24,
            "scan_screenshots": True,
            "scan_emails": True,
        }
    return {
        "is_active": row["is_active"],
        "scan_interval_hours": row["scan_interval_hours"],
        "scan_screenshots": row["scan_screenshots"],
        "scan_emails": row["scan_emails"],
        "screenshot_folder": row["screenshot_folder"] or "",
        "last_auto_scan_at": row["last_auto_scan_at"].isoformat() if row["last_auto_scan_at"] else None,
        "next_scan_at": row["next_scan_at"].isoformat() if row["next_scan_at"] else None,
    }


@router.post("/scan-now")
async def trigger_manual_scan(
    session_id: str = Query(...),
    scan_type: str = Query(default="all", pattern="^(all|screenshots|emails)$"),
    pool=Depends(get_db_pool),
):
    """Trigger an immediate manual scan."""
    results = {"scan_type": scan_type, "screenshots": [], "emails": []}

    if scan_type in ("all", "screenshots"):
        # Check if user has a configured screenshot folder
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT screenshot_folder FROM expense_scan_schedules WHERE session_id = $1",
                session_id,
            )
        folder = row["screenshot_folder"] if row and row["screenshot_folder"] else None
        if folder:
            scan_results = await scanner.scan_folder(folder)
            for sr in scan_results:
                if sr.get("is_receipt"):
                    async with pool.acquire() as conn:
                        receipt_id = await conn.fetchval("""
                            INSERT INTO expense_receipts
                                (session_id, vendor_name, amount, currency, receipt_date,
                                 receipt_number, description, category, tax_deductible,
                                 deduction_category, confidence_score, source_type,
                                 original_filename, source_ref)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                                    'screenshot', $12, $13)
                            RETURNING id
                        """,
                            session_id,
                            sr.get("vendor_name", ""),
                            float(sr.get("amount", 0)),
                            sr.get("currency", "ILS"),
                            sr.get("receipt_date"),
                            sr.get("receipt_number", ""),
                            sr.get("description", ""),
                            sr.get("category", "other"),
                            sr.get("tax_deductible", False),
                            sr.get("deduction_category"),
                            float(sr.get("confidence", 0)),
                            sr.get("filename", ""),
                            sr.get("source_file", ""),
                        )
                        sr["receipt_id"] = receipt_id
                    results["screenshots"].append(sr)

    return results


# ══════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════

@router.get("/categories")
async def get_categories():
    """Get available expense categories with Hebrew labels."""
    return DEDUCTION_CATEGORIES
