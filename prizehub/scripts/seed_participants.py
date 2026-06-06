#!/usr/bin/env python3
"""
Seed script: adds 20 fake participants with small ticket counts (1–100).
Run inside the bot container:
  docker compose exec bot python scripts/seed_participants.py
"""
import asyncio
import os
import random
import uuid

import asyncpg

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_USER = os.getenv("POSTGRES_USER", "prizehub")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "prizehub")
DB_NAME = os.getenv("POSTGRES_DB", "prizehub")

# Realistic Russian names pool
NAMES = [
    "Михаил Т.", "Ксения В.", "Владимир К.", "Анна С.", "Олег Р.",
    "Дарья Н.", "Илья Ж.", "Полина Г.", "Константин М.", "Вера Л.",
    "Тимур Б.", "Алина Ф.", "Руслан Д.", "Юлия З.", "Антон Ш.",
    "Карина О.", "Станислав Е.", "Надежда П.", "Виктор Х.", "Маргарита И.",
]

# Reserved TG ID range for fake participants (won't clash with winners or real users)
FAKE_TG_ID_BASE = 9_300_001


async def main() -> None:
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME,
    )

    # Get the active (or first) season
    season = await conn.fetchrow(
        "SELECT id FROM seasons WHERE status = 'active' ORDER BY id LIMIT 1"
    )
    if not season:
        season = await conn.fetchrow("SELECT id FROM seasons ORDER BY id LIMIT 1")
    if not season:
        print("❌  No season found — create and activate a season first.")
        await conn.close()
        return

    season_id = season["id"]
    print(f"Using season_id={season_id}")
    created = 0

    for i, name in enumerate(NAMES):
        tg_id = FAKE_TG_ID_BASE + i
        tickets = random.randint(10, 100)

        # Upsert user
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", tg_id
        )
        if existing:
            user_id = existing["id"]
            print(f"  User '{name}' exists (id={user_id}), reusing.")
        else:
            user_id = await conn.fetchval(
                """
                INSERT INTO users
                    (telegram_id, first_name, referral_code,
                     is_subscribed, onboarding_done, login_streak, total_wins)
                VALUES ($1, $2, $3, false, true, 0, 0)
                RETURNING id
                """,
                tg_id, name, f"fp_{uuid.uuid4().hex[:8]}",
            )
            print(f"  Created user '{name}' (id={user_id})")

        # Upsert season_participant
        existing_sp = await conn.fetchrow(
            "SELECT id FROM season_participants WHERE user_id = $1 AND season_id = $2",
            user_id, season_id,
        )
        if existing_sp:
            print(f"  Participant for '{name}' already exists, skipping.")
            continue

        await conn.execute(
            """
            INSERT INTO season_participants (user_id, season_id, tickets)
            VALUES ($1, $2, $3)
            """,
            user_id, season_id, tickets,
        )
        print(f"  ✅  Added participant: {name} — {tickets} билетов")
        created += 1

    await conn.close()
    print(f"\nDone! Added {created} fake participants. Check 🏆 Рейтинг.")


if __name__ == "__main__":
    asyncio.run(main())
