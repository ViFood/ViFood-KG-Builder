# ViFood-KG-Builder

`ViFood-KG-Builder` là service xây dựng và đồng bộ knowledge graph cho dữ liệu thực phẩm. Project đóng vai trò orchestration layer: nhận ảnh từ S3, gọi `KIE Model API` để trích xuất nhãn, sau đó match/sync `Nutrient` và `Additive` vào Neo4j để trả về kết quả đã được chuẩn hóa.

## Vai Trò

- Nhận `s3_key` của ảnh nhãn sản phẩm.
- Tải ảnh từ AWS S3 và gửi ảnh sang `KIE Model API`.
- Nhận JSON extraction thô từ AI model.
- Match/sync `Nutrient` và `Additive` vào Target Neo4j bằng logic chuẩn của hệ thống.
- Hỗ trợ batch pipeline để replicate dữ liệu `Additive` và `Nutrient` từ Source Neo4j sang Target Neo4j.

## Kiến Trúc Runtime

```text
API/App
-> ViFood-KG-Builder
-> AWS S3
-> KIE Model API
-> Target Neo4j
-> Final JSON response
```

Endpoint chính:

```http
POST /labels/analyze
Content-Type: application/json
```

```json
{
  "s3_key": "users/123/scans/label.jpg"
}
```

## Cài Đặt

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.env` cần cấu hình:

```env
KIE_MODEL_URL=http://localhost:8001

AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=ap-southeast-1
AWS_S3_BUCKET=your_bucket_name

OPENAI_API_KEY=your_openai_api_key
MODEL=gpt-4o-mini

SOURCE_NEO4J_URI=bolt://localhost:7687
SOURCE_NEO4J_USER=neo4j
SOURCE_NEO4J_PASSWORD=change_me
SOURCE_NEO4J_DATABASE=neo4j

TARGET_NEO4J_URI=bolt://localhost:7688
TARGET_NEO4J_USER=neo4j
TARGET_NEO4J_PASSWORD=change_me
TARGET_NEO4J_DATABASE=neo4j
```

## Chạy Local

Chạy `KIE Model API` trước:

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Chạy `ViFood-KG-Builder`:

```bash
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI:

```text
http://localhost:8000/docs
```

## Batch Pipeline

Extract dữ liệu từ Source Neo4j:

```bash
python -m src.main extract --type all
```

Build JSON import:

```bash
python -m src.main build --type all --input data/output/raw_all.json
```

Validate và import vào Target Neo4j:

```bash
python -m src.main batch --entity-type all --input data/output/raw_all.json
```

## Kiểm Tra

```bash
python -m compileall src
pytest
```
