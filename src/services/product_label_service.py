from src.load.additive_sync_service import AdditiveSyncService
from src.load.nutrient_sync_service import NutrientSyncService
from src.services.kie_model_client import KieModelClient
from src.services.s3_image_service import S3ImageService


class ProductLabelService:
    def __init__(self):
        self.s3_service = S3ImageService()
        self.kie_model_client = KieModelClient()
        self.nutrient_sync_service = NutrientSyncService()
        self.additive_sync_service = AdditiveSyncService()

    async def analyze_from_s3(self, s3_key: str) -> dict:
        image_bytes, content_type = self.s3_service.get_image(
            s3_key
        )

        result = await self.kie_model_client.extract_label(
            image_bytes,
            content_type
        )

        nutrient_sync = self.nutrient_sync_service.sync_from_extraction(
            result
        )
        result["nutrition"] = nutrient_sync

        additive_sync = self.additive_sync_service.sync_from_extraction(
            result
        )
        result["additive"] = additive_sync

        return result
