"""
Expense Scheduler Service — Manages automatic receipt scanning schedules.
Runs background tasks to scan screenshots and emails at configured intervals.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional


class ExpenseScheduler:
    """Manages scheduled expense scanning tasks."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start_schedule(
        self,
        session_id: str,
        pool,
        scan_callback,
        interval_hours: int = 24,
    ):
        """Start a recurring scan schedule for a session."""
        if session_id in self._tasks:
            self._tasks[session_id].cancel()

        async def _run_scheduled():
            while True:
                try:
                    await asyncio.sleep(interval_hours * 3600)
                    await scan_callback(session_id, pool)

                    # Update last scan time
                    async with pool.acquire() as conn:
                        now = datetime.now(timezone.utc)
                        next_scan = now + timedelta(hours=interval_hours)
                        await conn.execute("""
                            UPDATE expense_scan_schedules
                            SET last_auto_scan_at = $1, next_scan_at = $2
                            WHERE session_id = $3
                        """, now, next_scan, session_id)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Scheduled scan error for {session_id}: {e}")
                    await asyncio.sleep(300)  # Retry after 5 min on error

        task = asyncio.create_task(_run_scheduled())
        self._tasks[session_id] = task

    async def stop_schedule(self, session_id: str):
        """Stop a recurring scan schedule."""
        if session_id in self._tasks:
            self._tasks[session_id].cancel()
            del self._tasks[session_id]

    def is_scheduled(self, session_id: str) -> bool:
        """Check if a session has an active schedule."""
        return session_id in self._tasks and not self._tasks[session_id].done()

    async def stop_all(self):
        """Stop all scheduled tasks."""
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()


# Global scheduler instance
expense_scheduler = ExpenseScheduler()
