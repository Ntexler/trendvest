"""
Momentum calculator for TrendVest.
Calculates momentum scores based on mention counts.

Formula: momentum = (mentions_today / avg_mentions_7d) * 100

Direction:
  score > 150  →  'rising'   (50%+ above average)
  score > 80   →  'stable'   (within normal range)
  score <= 80  →  'falling'  (below average)
"""
from datetime import datetime, timezone, timedelta


class MomentumCalculator:
    """Calculates and stores momentum scores for topics."""

    RISING_THRESHOLD = 150
    FALLING_THRESHOLD = 80

    async def calculate_all(self, pool) -> list[dict]:
        """
        Calculate momentum scores for all active topics.

        Args:
            pool: asyncpg connection pool

        Returns:
            List of momentum score dicts
        """
        print(f"\n{'='*50}")
        print(f"📈 Momentum Calculation")
        print(f"{'='*50}")

        results = []
        async with pool.acquire() as conn:
            topics = await conn.fetch("SELECT id, slug FROM topics WHERE is_active = true")

            for topic in topics:
                score_data = await self._calculate_topic(conn, topic["id"], topic["slug"])
                results.append(score_data)

        rising = sum(1 for r in results if r["direction"] == "rising")
        stable = sum(1 for r in results if r["direction"] == "stable")
        falling = sum(1 for r in results if r["direction"] == "falling")
        print(f"\n📊 Results: {rising} rising, {stable} stable, {falling} falling")

        return results

    async def _calculate_topic(self, conn, topic_id: int, slug: str) -> dict:
        """Calculate momentum for a single topic."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today_start - timedelta(days=7)

        # Get today's total mentions (all sources)
        today_count = await conn.fetchval("""
            SELECT COALESCE(SUM(mention_count), 0)
            FROM topic_mentions
            WHERE topic_id = $1 AND collected_at >= $2
        """, topic_id, today_start) or 0

        # Get 7-day daily average
        daily_totals = await conn.fetch("""
            SELECT DATE(collected_at) as day, SUM(mention_count) as total
            FROM topic_mentions
            WHERE topic_id = $1 AND collected_at >= $2 AND collected_at < $3
            GROUP BY DATE(collected_at)
        """, topic_id, week_ago, today_start)

        if daily_totals:
            avg_7d = sum(row["total"] for row in daily_totals) / max(len(daily_totals), 1)
        else:
            avg_7d = 0

        # Calculate score
        if avg_7d > 0:
            score = (today_count / avg_7d) * 100
        elif today_count > 0:
            score = 200  # New topic with mentions = strong signal
        else:
            score = 0

        # Determine direction
        if score > self.RISING_THRESHOLD:
            direction = "rising"
        elif score > self.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"

        # Upsert momentum score
        await conn.execute("""
            INSERT INTO momentum_scores (topic_id, score, mention_count_today, mention_avg_7d, direction, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (topic_id) DO UPDATE SET
                score = EXCLUDED.score,
                mention_count_today = EXCLUDED.mention_count_today,
                mention_avg_7d = EXCLUDED.mention_avg_7d,
                direction = EXCLUDED.direction,
                updated_at = EXCLUDED.updated_at
        """, topic_id, round(score, 1), int(today_count), round(avg_7d, 1), direction, now)

        emoji = "🟢" if direction == "rising" else ("🔴" if direction == "falling" else "🟡")
        print(f"  {emoji} {slug}: score={score:.0f}, today={today_count}, avg7d={avg_7d:.0f}, dir={direction}")

        return {
            "topic_id": topic_id,
            "slug": slug,
            "score": round(score, 1),
            "mention_count_today": int(today_count),
            "mention_avg_7d": round(avg_7d, 1),
            "direction": direction,
        }
