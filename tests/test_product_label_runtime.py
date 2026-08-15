import base64
import asyncio

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.api import routes
from src.services.kie_model_client import KieModelClient
from src.services.product_label_service import ProductLabelService


class FakeProductLabelService:
    last_request = None

    async def analyze_from_payload(
        self,
        *,
        request_id: str,
        image_base64: str,
        content_type: str,
    ) -> dict:
        FakeProductLabelService.last_request = {
            "request_id": request_id,
            "image_base64": image_base64,
            "content_type": content_type,
        }
        return {
            "product_name": "Sua ABC",
        }


def test_analyze_endpoint_accepts_image_payload(monkeypatch) -> None:
    fake_service = FakeProductLabelService()
    FakeProductLabelService.last_request = None
    monkeypatch.setattr(
        routes,
        "product_label_service",
        fake_service,
    )

    image_base64 = base64.b64encode(b"image-bytes").decode("ascii")
    response = TestClient(app).post(
        "/labels/analyze",
        json={
            "request_id": "analysis-1",
            "image_base64": image_base64,
            "content_type": "image/png",
            "metadata": {
                "source": "vifood-api",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "product_name": "Sua ABC",
    }
    assert FakeProductLabelService.last_request == {
        "request_id": "analysis-1",
        "image_base64": image_base64,
        "content_type": "image/png",
    }


def test_analyze_endpoint_rejects_storage_key_only_request() -> None:
    response = TestClient(app).post(
        "/labels/analyze",
        json={
            "s3_key": "users/1/scans/label.png",
        },
    )

    assert response.status_code == 422


def test_product_label_service_decodes_payload_and_uses_request_id() -> None:
    class FakeKieModelClient:
        last_request = None

        async def extract_label(
            self,
            *,
            image_bytes: bytes,
            content_type: str,
            request_id: str,
        ) -> dict:
            FakeKieModelClient.last_request = {
                "image_bytes": image_bytes,
                "content_type": content_type,
                "request_id": request_id,
            }
            return {
                "product_name": "Sua ABC",
                "ingredients": ["sua"],
            }

    service = ProductLabelService()
    service.kie_model_client = FakeKieModelClient()
    service.nutrient_sync_service.sync_from_extraction = lambda extraction: []
    service.additive_sync_service.sync_from_extraction = lambda extraction: []
    service.ingredient_sync_service.sync_from_extraction = lambda extraction: []

    result = asyncio.run(async_analyze(service))

    assert result == {
        "product_name": "Sua ABC",
    }
    assert FakeKieModelClient.last_request == {
        "image_bytes": b"image-bytes",
        "content_type": "image/png",
        "request_id": "analysis-1",
    }


async def async_analyze(service: ProductLabelService) -> dict:
    return await service.analyze_from_payload(
        request_id="analysis-1",
        image_base64=base64.b64encode(b"image-bytes").decode("ascii"),
        content_type="image/png",
    )


def test_product_label_service_rejects_invalid_base64() -> None:
    service = ProductLabelService()

    with pytest.raises(ValueError, match="image_base64 is invalid"):
        service._decode_image_base64("not-base64")


def test_kie_model_client_sends_request_id(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "success": True,
                "data": {
                    "product_name": "Sua ABC",
                },
            }

    class FakeAsyncClient:
        last_post = None

        def __init__(self, timeout: int):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict):
            FakeAsyncClient.last_post = {
                "url": url,
                "json": json,
            }
            return FakeResponse()

    monkeypatch.setattr(
        "src.services.kie_model_client.httpx.AsyncClient",
        FakeAsyncClient,
    )

    client = KieModelClient()
    result = asyncio.run(
        client.extract_label(
            image_bytes=b"image-bytes",
            content_type="image/png",
            request_id="analysis-1",
        )
    )

    assert result == {
        "product_name": "Sua ABC",
    }
    assert FakeAsyncClient.last_post["json"] == {
        "request_id": "analysis-1",
        "image_base64": base64.b64encode(b"image-bytes").decode("utf-8"),
        "content_type": "image/png",
    }
