from datetime import datetime
from zoneinfo import ZoneInfo

SEVERITY_LEVELS = {
    1: "High",
    2: "Medium",
    3: "Low"
}

SEVERITY_CONFIG = {
    1: {"label": "High",   "color": 0xE74C3C, "icon": "🔴"},
    2: {"label": "Medium", "color": 0xE67E22, "icon": "🟠"},
    3: {"label": "Low",    "color": 0xF1C40F, "icon": "🟡"},
}

def send_discord_message(
    discord_cls,
    severity: int,
    title: str,
    description: str,
    multiple_fields: bool = False,
    fields: list = None,
    should_tag: bool = False,
    tag_id: int = None
) -> None:
    """
    Send a formatted embed message to a Discord channel via a discord_cls instance.

    Args:
        discord_cls: A Discord instances (ensure you include the webhook when creating the class).

        severity (int): Severity level of the alert. Must be one of: 1 (High), 2 (Medium), 3 (Low).
            Defaults to Low if an unrecognised value is provided.

        title (str):  Short headline for the embed, prefixed with the severity badge.

        description (str): Body text of the embed, prefixed with the severity icon.

        multiple_fields (bool): When True, appends `fields` to the embed. Defaults to False.

        fields (list[dict] | None): Optional list of extra embed field dicts. Each dict may
            contain:
                - "name"   (str)  – field label.         Default: "Field"
                - "value"  (str)  – field content.       Default: "—"
                - "inline" (bool) – render side-by-side. Default: False
            Only used when `multiple_fields` is True.

    Returns:
        None

    Example:
        send_discord_message(
            discord_cls=discord_instance,
            severity=1,
            title="Database Unreachable",
            description="Primary DB connection failed after 3 retries.",
            multiple_fields=True,
            fields=[
                {"name": "Host", "value": "db-prod-01", "inline": True},
                {"name": "Port", "value": "5432",       "inline": True},
            ],
        )
    """
    if should_tag and not tag_id:
        raise ValueError("tag_id must be provided if should_tag is True")


    config = SEVERITY_CONFIG.get(severity, SEVERITY_CONFIG[3])
    now = datetime.now(tz=ZoneInfo("America/Denver"))

    embed_fields = []

    if multiple_fields and fields:
        for field in fields:
            embed_fields.append(
                {
                    "name": field.get("name", "Field"),
                    "value": field.get("value", "—"),
                    "inline": field.get("inline", False),
                }
            )

    embed_fields.append(
        {
            "name": "Severity",
            "value": f"{config['icon']} {config['label']}",
            "inline": True,
        },
    )

    embed = {
        "title": f"{title}",
        "description": f"{description}",
        "color": config["color"],
        "fields": embed_fields,
        "footer": {"text": "DifferentOdds Logs"},
        "timestamp": now.isoformat(),
    }

    content = f"<@{tag_id}>" if should_tag else None
    discord_cls.post(content=content, embeds=[embed])