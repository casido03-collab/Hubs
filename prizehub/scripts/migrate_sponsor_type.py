#!/usr/bin/env python3
"""
Migration: add sponsor_type and sponsor_bot columns to the seasons table.
Run once after deploying the bot-sponsor feature:
  docker compose exec bot python scripts/migrate_sponsor_type.py
"""
import asyncio
import os

import asyncpg

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_USER = os.getenv("POSTGRES_USER", "prizehub")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "prizehub")
DB_NAME = os.getenv("POSTGRES_DB", "prizehub")


async def main() -> None:
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME,
    )

    # sponsor_type column
    exists = await conn.fetchval(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='seasons' AND column_name='sponsor_type'"
    )
    if not exists:
        await conn.execute(
            "ALTER TABLE seasons ADD COLUMN sponsor_type VARCHAR(16) NOT NULL DEFAULT 'channel'"
        )
        print("✅ Added column: seasons.sponsor_type (default 'channel')")
    else:
        print("⏭  Column seasons.sponsor_type already exists, skipping.")

    # sponsor_bot column
    exists = await conn.fetchval(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='seasons' AND column_name='sponsor_bot'"
    )
    if not exists:
        await conn.execute(
            "ALTER TABLE seasons ADD COLUMN sponsor_bot VARCHAR(256) NULL"
        )
        print("✅ Added column: seasons.sponsor_bot")
    else:
        print("⏭  Column seasons.sponsor_bot already exists, skipping.")

    # Make sponsor_channel nullable (bot-type seasons don't need it)
    await conn.execute(
        "ALTER TABLE seasons ALTER COLUMN sponsor_channel DROP NOT NULL"
    )
    print("✅ sponsor_channel is now nullable.")

    await conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(main())
