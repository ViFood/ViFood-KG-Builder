from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductLabelAnalyzeRequest(BaseModel):
    s3_key: str


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
    additive: list[PublicLabelEntity] = Field(default_factory=list)
    nutrition: dict[str, Any] = Field(default_factory=dict)
    manufacturer: str | None = None
    mfg_date: str | None = None
    expiry_date: str | None = None
    net_weight: str | None = None
    warning: str | list[str] | None = None
    origin: str | None = None
