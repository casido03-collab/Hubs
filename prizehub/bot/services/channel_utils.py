def build_sponsor_link(channel: str) -> str:
    """Correctly build a Telegram channel link regardless of input format."""
    channel = channel.strip()
    if channel.startswith("http://") or channel.startswith("https://"):
        return channel
    if channel.startswith("@"):
        return f"https://t.me/{channel.lstrip('@')}"
    return f"https://t.me/{channel}"
