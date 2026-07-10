import mimetypes

import boto3
from botocore.exceptions import ClientError

from src.config.settings import load_settings


class S3ImageService:
    def __init__(self):
        self.settings = load_settings()

    def get_image(self, s3_key: str) -> tuple[bytes, str]:
        if not self.settings.aws_s3_bucket:
            raise Exception("AWS_S3_BUCKET not found in .env")

        if not s3_key.strip():
            raise ValueError("s3_key is required")

        s3_client = self._get_client()

        try:
            response = s3_client.get_object(
                Bucket=self.settings.aws_s3_bucket,
                Key=s3_key
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            if error_code in {"404", "NoSuchKey"}:
                raise FileNotFoundError(f"S3 object not found: {s3_key}")

            raise

        content_type = self._resolve_image_content_type(
            s3_key,
            response.get("ContentType")
        )

        return response["Body"].read(), content_type

    def _get_client(self):
        client_kwargs = {}

        if self.settings.aws_region:
            client_kwargs["region_name"] = self.settings.aws_region

        return boto3.client(
            "s3",
            **client_kwargs
        )

    def _resolve_image_content_type(
        self,
        s3_key: str,
        s3_content_type: str | None
    ) -> str:
        guessed_content_type = mimetypes.guess_type(s3_key)[0]

        if guessed_content_type and guessed_content_type.startswith("image/"):
            return guessed_content_type

        if s3_content_type and s3_content_type.startswith("image/"):
            return s3_content_type

        if not guessed_content_type and s3_content_type in {None, "binary/octet-stream"}:
            return "image/jpeg"

        raise ValueError(f"S3 object is not an image: {s3_key}")
