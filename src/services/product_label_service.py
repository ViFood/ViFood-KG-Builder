import base64
import binascii

from src.load.additive_sync_service import AdditiveSyncService
from src.load.ingredient_sync_service import IngredientSyncService
from src.load.nutrient_sync_service import NutrientSyncService
from src.services.final_label_response_mapper import FinalLabelResponseMapper
from src.services.kie_model_client import KieModelClient


class ProductLabelService:
    def __init__(self):
        self.kie_model_client = KieModelClient()
        self.nutrient_sync_service = NutrientSyncService()
        self.additive_sync_service = AdditiveSyncService()
        self.ingredient_sync_service = IngredientSyncService()
        self.final_label_response_mapper = FinalLabelResponseMapper()

    async def analyze_from_payload(
        self,
        *,
        request_id: str,
        image_base64: str,
        content_type: str,
    ) -> dict:
        image_bytes = self._decode_image_base64(
            image_base64
        )

        raw_extraction = await self.kie_model_client.extract_label(
            image_bytes=image_bytes,
            content_type=content_type,
            request_id=request_id,
        )

        nutrient_sync = self.nutrient_sync_service.sync_from_extraction(
            raw_extraction
        )

        additive_sync = self.additive_sync_service.sync_from_extraction(
            raw_extraction
        )

        ingredient_sync = self.ingredient_sync_service.sync_from_extraction(
            raw_extraction
        )

        return self.final_label_response_mapper.build(
            raw_extraction=raw_extraction,
            nutrient_results=nutrient_sync,
            additive_results=additive_sync,
            ingredient_results=ingredient_sync,
        )

    def _decode_image_base64(self, image_base64: str) -> bytes:
        try:
            image_bytes = base64.b64decode(
                image_base64,
                validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise ValueError("image_base64 is invalid") from exc

        if not image_bytes:
            raise ValueError("image payload is empty")

        return image_bytes
