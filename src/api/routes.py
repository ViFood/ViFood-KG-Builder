import httpx
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from src.schemas.product_label import ProductLabelAnalyzeRequest
from src.services.product_label_service import ProductLabelService

router = APIRouter()

product_label_service = ProductLabelService()


@router.get("/")
async def root():
    return {
        "message": "ViFood KG Builder Service"
    }


@router.post("/labels/analyze")
async def analyze_product_label(request: ProductLabelAnalyzeRequest):
    try:
        result = await product_label_service.analyze_from_payload(
            request_id=request.request_id,
            image_base64=request.image_base64,
            content_type=request.content_type,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail="AIaaS extract-label request failed",
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Cannot connect to AIaaS extract-label service",
        ) from exc

    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Builder produced invalid analysis response",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Builder analyze request failed",
        ) from exc
