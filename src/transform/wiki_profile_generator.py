from typing import Any


class WikiProfileGenerator:
    def generate(self, context: dict[str, Any], source_hash: str | None = None) -> dict[str, Any]:
        subtitle_parts = [
            value
            for value in (context.get("secondary_name"), context.get("identifier_text"))
            if value
        ]
        profile = {
            "id": f"WIKI:{context['entity_id']}",
            "title": context["display_name"],
            "subtitle": " · ".join(subtitle_parts),
            "summary": context["summary"],
            "entity_type": context["entity_type"],
            "language": "vi",
            "audience": "consumer",
            "status": "draft",
            "reviewed_at": context.get("evidence", {}).get("reviewed_at"),
        }
        if source_hash:
            profile["source_hash"] = source_hash
        return profile
