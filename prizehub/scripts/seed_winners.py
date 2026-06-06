#!/usr/bin/env python3
"""
Seed script: inserts display winners so the bot doesn't look empty at launch.
Run inside the bot container:
  docker compose exec bot python scripts/seed_winners.py
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta

import asyncpg
import pytz

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_USER = os.getenv("POSTGRES_USER", "prizehub")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "prizehub")
DB_NAME = os.getenv("POSTGRES_DB", "prizehub")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# Fake winners — names are anonymised, prizes as requested
WINNERS_DATA = [
    {"first_name": "Алексей К.",    "prize": "2 000 ₽", "days_ago": 4},
    {"first_name": "Мария П.",      "prize": "1 500 ₽", "days_ago": 9},
    {"first_name": "Дмитрий В.",    "prize": "1 000 ₽", "days_ago": 16},
    {"first_name": "Екатерина Н.", "prize": "500 ₽",   "days_ago": 23},
]

# Reserved telegram_id range for seeded users (won't clash with real accounts)
SEED_TG_ID_BASE = 9_000_001


async def main() -> None:
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME,
    )

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Use the first existing season (oldest)
    season = await conn.fetchrow("SELECT id FROM seasons ORDER BY id LIMIT 1")
    if not season:
        print("❌  No season found — create a season first, then run this script.")
        await conn.close()
        return
    season_id = season["id"]
    print(f"Using season_id={season_id}")

    for i, w in enumerate(WINNERS_DATA):
        tg_id = SEED_TG_ID_BASE + i

        # Upsert fake user
        existing_user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", tg_id
        )
        if existing_user:
            user_id = existing_user["id"]
            print(f"  User '{w['first_name']}' already exists (id={user_id}), reusing.")
        else:
            user_id = await conn.fetchval(
                """
                INSERT INTO users
                    (telegram_id, first_name, referral_code,
                     is_subscribed, onboarding_done, login_streak, total_wins)
                VALUES ($1, $2, $3, false, true, 0, 1)
                RETURNING id
                """,
                tg_id,
                w["first_name"],
                f"seed_{uuid.uuid4().hex[:8]}",
            )
            print(f"  Created user '{w['first_name']}' (id={user_id})")

        # Skip if winner row already exists for this user
        existing_win = await conn.fetchrow(
            "SELECT id FROM winners WHERE user_id = $1", user_id
        )
        if existing_win:
            print(f"  Winner record for '{w['first_name']}' already exists, skipping.")
            continue

        published_at = now - timedelta(days=w["days_ago"])
        await conn.execute(
            """
            INSERT INTO winners
                (user_id, season_id, raffle_type, prize, status, published_at)
            VALUES ($1, $2, 'mini', $3, 'published', $4)
            """,
            user_id, season_id, w["prize"], published_at,
        )
        print(f"  ✅  Winner created: {w['first_name']} — {w['prize']} ({w['days_ago']} days ago)")

    await conn.close()
    print("\nDone! Open the bot and check 🏅 Победители.")


if __name__ == "__main__":
    asyncio.run(main())
