# ViFood-KG-Builder

`ViFood-KG-Builder` là service orchestration và knowledge graph layer cho hệ thống phân tích nhãn thực phẩm. Project nhận ảnh từ S3, gọi `KIE Model API` để trích xuất thông tin nhãn, sau đó match/sync `Nutrient` và `Additive` vào Neo4j để tạo kết quả cuối cùng có ngữ cảnh tri thức.

Project được thiết kế để tách rõ AI inference và graph intelligence: model chỉ đọc ảnh, Builder chịu trách nhiệm chuẩn hóa, đối chiếu dữ liệu và đồng bộ knowledge graph. Kiến trúc này giúp hệ thống dễ mở rộng, dễ kiểm soát dữ liệu chuẩn và phù hợp triển khai dạng microservice.

## Điểm Nổi Bật

- FastAPI runtime API cho luồng xử lý ảnh nhãn theo thời gian thực.
- Tích hợp AWS S3, KIE Model API và Neo4j trong một orchestration layer.
- Match/sync `Nutrient` và `Additive` bằng logic chuẩn của hệ thống.
- Hỗ trợ CLI batch để replicate dữ liệu graph từ Source Neo4j sang Target Neo4j.
- Giữ AI extraction tách biệt với graph persistence để dễ bảo trì và scale độc lập.

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

```bash
python -m src.main extract --type all
python -m src.main build --type all --input data/output/raw_all.json
python -m src.main batch --entity-type all --input data/output/raw_all.json
```

## Kiểm Tra

```bash
python -m compileall src
pytest
```
