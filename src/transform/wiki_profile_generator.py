from typing import Any


class WikiProfileGenerator:
    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        subtitle_parts = [
            value
            for value in (context.get("secondary_name"), context.get("identifier_text"))
            if value
        ]
        return {
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
