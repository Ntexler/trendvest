#!/usr/bin/env python3
"""
TrendVest Data Collection Pipeline
"""
import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

from backend.app.services.reddit import RedditCollector
from backend.app.services.news import NewsCollector
from backend.app.services.momentum import MomentumCalculator

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/trendvest")
TOPICS_FILE = Path(__file__).parent.parent / "backend" / "app" / "data" / "topics.json"


def load_topics() -> list[dict]:
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["topics"]


async def save_mentions(pool, mentions: list[dict]):
    async with pool.acquire() as conn:
        for m in mentions:
            topic_id = await conn.fetchval(
                "SELECT id FROM topics WHERE slug = $1", m["topic_slug"]
            )
            if not topic_id:
                continue
            await conn.execute("""
                INSERT INTO topic_mentions (topic_id, source, mention_count, collected_at, period_start, period_end)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, topic_id, m["source"], m["mention_count"],
               m["collected_at"], m["period_start"], m["period_end"])
    print(f"Saved {len(mentions)} mention records to DB")


async def run_pipeline(args):
    start = datetime.now(timezone.utc)
    print(f"\nTrendVest Pipeline - {start.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    try:
        topics = load_topics()
        print(f"Loaded {len(topics)} topics")

        if args.seed_only:
            from backend.app.models.database import init_db
            await init_db(pool)
            return

        all_mentions = []

        if not args.momentum_only:
            if args.source in (None, "reddit"):
                reddit = RedditCollector()
                try:
                    reddit_mentions = reddit.collect_all(topics)
                    all_mentions.extend(reddit_mentions)
                except Exception as e:
                    print(f"Reddit collection failed: {e}")

            if args.source in (None, "news"):
                news = NewsCollector()
                try:
                    news_mentions = news.collect_all(topics)
                    all_mentions.extend(news_mentions)
                except Exception as e:
                    print(f"News collection failed: {e}")

            if all_mentions:
                await save_mentions(pool, all_mentions)

        momentum = MomentumCalculator()
        await momentum.calculate_all(pool)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        print(f"\nPipeline complete in {elapsed:.1f}s")
        print(f"Mentions collected: {len(all_mentions)}")

    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(description="TrendVest Data Pipeline")
    parser.add_argument("--source", choices=["reddit", "news"], default=None)
    parser.add_argument("--momentum-only", action="store_true")
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
