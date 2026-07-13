import base64

import httpx

from src.config.settings import load_settings


class KieModelClient:
    def __init__(self):
        self.settings = load_settings()

    async def extract_label(
        self,
        image_bytes: bytes,
        content_type: str
    ) -> dict:
        image_base64 = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        async with httpx.AsyncClient(
            timeout=self.settings.kie_model_timeout_seconds
        ) as client:
            response = await client.post(
                f"{self.settings.kie_model_url.rstrip('/')}/extract-label",
                json={
                    "image_base64": image_base64,
                    "content_type": content_type
                },
            )
            response.raise_for_status()

        payload = response.json()
        return payload.get("data", payload)
