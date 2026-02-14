"""
Database connection and utilities for TrendVest.
Uses asyncpg for async PostgreSQL access.
"""
import os
import json
import asyncpg
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/trendvest")


async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)


@asynccontextmanager
async def get_connection(pool):
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)


async def init_db(pool):
    """Run schema migration and seed data."""
    schema_path = Path(__file__).parent.parent.parent.parent / "database" / "001_schema.sql"

    async with get_connection(pool) as conn:
        if schema_path.exists():
            schema_sql = schema_path.read_text(encoding="utf-8")
            await conn.execute(schema_sql)
            print("Schema created/updated")

        await seed_topics(conn)

        await conn.execute("SELECT init_momentum_scores()")
        print("Momentum scores initialized")


async def seed_topics(conn):
    topics_path = Path(__file__).parent.parent / "data" / "topics.json"

    if not topics_path.exists():
        print("topics.json not found, skipping seed")
        return

    with open(topics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for topic in data["topics"]:
        topic_id = await conn.fetchval("""
            INSERT INTO topics (slug, name_en, name_he, sector, sector_en, keywords, subreddits)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (slug) DO UPDATE SET
                name_en = EXCLUDED.name_en,
                name_he = EXCLUDED.name_he,
                sector = EXCLUDED.sector,
                sector_en = EXCLUDED.sector_en,
                keywords = EXCLUDED.keywords,
                subreddits = EXCLUDED.subreddits
            RETURNING id
        """, topic["slug"], topic["name_en"], topic["name_he"],
           topic["sector"], topic["sector_en"],
           topic["keywords"], topic.get("subreddits", []))

        for stock in topic["stocks"]:
            await conn.execute("""
                INSERT INTO topic_stocks (topic_id, ticker, company_name, relevance_note, priority)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (topic_id, ticker) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    relevance_note = EXCLUDED.relevance_note,
                    priority = EXCLUDED.priority
            """, topic_id, stock["ticker"], stock["name"], stock.get("note", ""), stock.get("priority", 0))

        count += 1

    print(f"Seeded {count} topics with stocks")
