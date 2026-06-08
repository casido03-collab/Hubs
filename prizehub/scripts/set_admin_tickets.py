#!/usr/bin/env python3
"""
One-off: set the admin's ticket count in the active season to a fixed value.
Run inside the bot container:
  docker compose exec bot python scripts/set_admin_tickets.py
"""
import asyncio
import os

import asyncpg

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_USER = os.getenv("POSTGRES_USER", "prizehub")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "prizehub")
DB_NAME = os.getenv("POSTGRES_DB", "prizehub")

ADMIN_TG_ID = 1_715_461_306
TICKETS = 211


async def main() -> None:
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME,
    )

    season = await conn.fetchrow(
        "SELECT id FROM seasons WHERE status = 'active' ORDER BY id LIMIT 1"
    )
    if not season:
        print("❌  No active season found.")
        await conn.close()
        return
    season_id = season["id"]

    user = await conn.fetchrow(
        "SELECT id FROM users WHERE telegram_id = $1", ADMIN_TG_ID
    )
    if not user:
        print(f"❌  No user found with telegram_id={ADMIN_TG_ID}. "
              f"Make sure the admin has started the bot at least once.")
        await conn.close()
        return
    user_id = user["id"]

    sp = await conn.fetchrow(
        "SELECT id, tickets FROM season_participants WHERE user_id = $1 AND season_id = $2",
        user_id, season_id,
    )
    if sp:
        await conn.execute(
            "UPDATE season_participants SET tickets = $1 WHERE id = $2",
            TICKETS, sp["id"],
        )
        print(f"✅  Updated admin tickets: {sp['tickets']} → {TICKETS} (season_id={season_id})")
    else:
        await conn.execute(
            "INSERT INTO season_participants (user_id, season_id, tickets) VALUES ($1, $2, $3)",
            user_id, season_id, TICKETS,
        )
        print(f"✅  Created participant record for admin with {TICKETS} tickets (season_id={season_id})")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
