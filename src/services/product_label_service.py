from src.load.additive_sync_service import AdditiveSyncService
from src.load.nutrient_sync_service import NutrientSyncService
from src.services.final_label_response_mapper import FinalLabelResponseMapper
from src.services.kie_model_client import KieModelClient
from src.services.s3_image_service import S3ImageService


class ProductLabelService:
    def __init__(self):
        self.s3_service = S3ImageService()
        self.kie_model_client = KieModelClient()
        self.nutrient_sync_service = NutrientSyncService()
        self.additive_sync_service = AdditiveSyncService()
        self.final_label_response_mapper = FinalLabelResponseMapper()

    async def analyze_from_s3(self, s3_key: str) -> dict:
        image_bytes, content_type = self.s3_service.get_image(
            s3_key
        )

        raw_extraction = await self.kie_model_client.extract_label(
            image_bytes,
            content_type
        )

        nutrient_sync = self.nutrient_sync_service.sync_from_extraction(
            raw_extraction
        )

        additive_sync = self.additive_sync_service.sync_from_extraction(
            raw_extraction
        )

        return self.final_label_response_mapper.build(
            raw_extraction=raw_extraction,
            nutrient_results=nutrient_sync,
            additive_results=additive_sync,
            ingredient_results=[],
        )
