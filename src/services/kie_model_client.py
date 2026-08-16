import base64

import httpx

from src.config.settings import load_settings


class KieModelClient:
    def __init__(self):
        self.settings = load_settings()

    async def extract_label(
        self,
        image_bytes: bytes,
        content_type: str,
        request_id: str,
    ) -> dict:
        await self._ensure_model_is_healthy()

        image_base64 = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        async with httpx.AsyncClient(
            timeout=self.settings.kie_model_timeout_seconds
        ) as client:
            response = await client.post(
                f"{self.settings.kie_model_url.rstrip('/')}/extract-label",
                json={
                    "request_id": request_id,
                    "image_base64": image_base64,
                    "content_type": content_type
                },
            )
            response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("AIaaS returned invalid response")

        if payload.get("success") is False:
            raise ValueError("AIaaS extraction failed")

        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ValueError("AIaaS returned invalid data")

        return data

    async def _ensure_model_is_healthy(self) -> None:
        async with httpx.AsyncClient(
            timeout=self.settings.kie_model_health_timeout_seconds
        ) as client:
            response = await client.get(
                self.settings.kie_model_health_url
            )
            response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            return

        if not isinstance(payload, dict):
            return

        if payload.get("success") is False:
            raise self._health_status_error(response)

        status = str(payload.get("status", "")).lower()
        if status and status not in {"ok", "healthy", "ready", "up", "pass", "running"}:
            raise self._health_status_error(response)

    @staticmethod
    def _health_status_error(response: httpx.Response) -> httpx.HTTPStatusError:
        return httpx.HTTPStatusError(
            "AIaaS health check returned unhealthy",
            request=response.request,
            response=response,
        )
