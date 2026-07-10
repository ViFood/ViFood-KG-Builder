import httpx
from fastapi import APIRouter, HTTPException

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
        result = await product_label_service.analyze_from_s3(
            request.s3_key
        )

        return {
            "success": True,
            "image_key": request.s3_key,
            "data": result
        }

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except (ValueError, httpx.HTTPStatusError) as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
