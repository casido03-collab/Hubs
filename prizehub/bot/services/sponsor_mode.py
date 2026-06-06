"""
Sponsor-mode toggle.

White mode (sponsor OFF): users can participate without subscribing to any channel.
Normal mode (sponsor ON): mandatory subscription to sponsor channel is required.

The flag is persisted in `global_settings` table and cached in-memory.
Use `load()` once at startup, then read via `is_required()` everywhere.
"""
from __future__ import annotations

_sponsor_required: bool = True   # default: sponsor required


def is_required() -> bool:
    """Fast in-memory read — no DB call needed."""
    return _sponsor_required


def user_has_access(user) -> bool:
    """True if user can reach protected sections (earn, rating, profile, home)."""
    if not _sponsor_required:
        return True          # white mode: everyone passes
    return user is not None and user.is_subscribed


async def load(session) -> None:
    """Call once on bot startup to restore persisted value."""
    global _sponsor_required
    from bot.database.repositories import GlobalSettingRepository
    repo = GlobalSettingRepository(session)
    val = await repo.get("sponsor_required", default="true")
    _sponsor_required = val.lower() != "false"


async def toggle(session) -> bool:
    """Toggle mode, persist to DB. Returns the NEW value of sponsor_required."""
    global _sponsor_required
    _sponsor_required = not _sponsor_required
    from bot.database.repositories import GlobalSettingRepository
    repo = GlobalSettingRepository(session)
    await repo.set("sponsor_required", "true" if _sponsor_required else "false")
    return _sponsor_required
