from typing import Any


class RequiredFieldValidator:
    profile_fields = ("id", "title", "summary", "entity_type", "language", "status")
    section_fields = ("id", "title", "content", "section_type", "status")

    def validate(self, item: dict[str, Any]) -> list[str]:
        entity_id = item.get("entity_id", "<missing entity_id>")
        errors: list[str] = []
        profile = item.get("wiki_profile")
        if not isinstance(profile, dict):
            return [f"{entity_id}: wiki_profile is required."]
        for field in self.profile_fields:
            if profile.get(field) in (None, ""):
                errors.append(f"{entity_id}: wiki_profile.{field} is required.")

        sections = item.get("wiki_sections")
        if not isinstance(sections, list) or not sections:
            errors.append(f"{entity_id}: wiki_sections must be a non-empty list.")
            return errors
        for index, section in enumerate(sections):
            prefix = f"{entity_id}: wiki_sections[{index}]"
            if not isinstance(section, dict):
                errors.append(f"{prefix} must be an object.")
                continue
            for field in self.section_fields:
                if section.get(field) in (None, ""):
                    errors.append(f"{prefix}.{field} is required.")
            if isinstance(section.get("content"), str) and not section["content"].strip():
                errors.append(f"{prefix}.content must not be empty.")
        return errors
