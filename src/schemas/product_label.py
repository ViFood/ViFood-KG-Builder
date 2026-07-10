from pydantic import BaseModel


class ProductLabelAnalyzeRequest(BaseModel):
    s3_key: str
