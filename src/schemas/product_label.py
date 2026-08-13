from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductLabelAnalyzeRequest(BaseModel):
    request_id: str
    image_base64: str
    content_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_id", "image_base64", "content_type")
    @classmethod
    def require_non_empty_string(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @field_validator("content_type")
    @classmethod
    def require_image_content_type(cls, value: str) -> str:
        if not value.startswith("image/"):
            raise ValueError("content_type must be an image MIME type")
        return value


class PublicLabelEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    value: Any | None = None
    unit: str | None = None
    percentage: float | int | str | None = None
    daily_value_percent: float | int | str | None = None
    ins: str | None = None


class FinalLabelResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_name: str | None = None
    age_range: str | None = None
    ingredients: list[PublicLabelEntity] = Field(default_factory=list)
    additives: list[PublicLabelEntity] = Field(default_factory=list)
    nutritions: dict[str, Any] = Field(default_factory=dict)
    manufacturer: str | None = None
    mfg_date: str | None = None
    expiry_date: str | None = None
    net_weight: str | None = None
    warning: str | list[str] | None = None
    origin: str | None = None
