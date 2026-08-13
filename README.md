# ViFood-KG-Builder

`ViFood-KG-Builder` là service runtime cho hệ thống phân tích nhãn thực phẩm. Project nhận ảnh nhãn từ `ViFood-API` qua payload ảnh, gọi KIE Model API để đọc nhãn, chuẩn hóa dữ liệu trích xuất, liên kết dữ liệu với knowledge graph, rồi trả JSON phân tích public về cho Backend API.

Builder không phải project tạo tri thức chuẩn. Tri thức chuẩn nằm ở `ViFood-KC`. Builder đọc KG Builder Contract do `ViFood-KC` publish để biết schema, release IDs và match keys cần dùng khi xử lý runtime.

## Vai Trò Của Project

Builder chịu trách nhiệm:

- Nhận input phân tích nhãn qua API nội bộ từ `ViFood-API`.
- Gọi KIE Model API để lấy extraction result từ ảnh.
- Tách extraction thành ba nhóm: `nutritions`, `additives`, `ingredients`.
- Match hoặc tạo dữ liệu graph theo flow riêng của từng nhóm.
- Build payload graph nội bộ để validate/import Neo4j.
- Trả `FinalLabelResponse` cho Backend API, chỉ gồm thông tin public cần cho app.

Builder không chịu trách nhiệm:

- Tạo canonical release cho `Nutrient` hoặc `Additive`.
- Chạy quality gate canonical của `ViFood-KG`.
- Publish KG Builder Contract.
- Đưa metadata kỹ thuật, provenance hoặc source detail vào response cuối cùng cho app.
- Đọc ảnh từ S3/storage trong flow runtime chuẩn.
- Quản lý user/session/history hoặc lưu ảnh sau phân tích.

## Quan Hệ Với ViFood-KC

`ViFood-KC` là Knowledge Core. Project đó tạo curated releases, source registry, quality gate, Neo4j import và contract cho Builder.

Builder đọc contract JSON từ `ViFood-KG` qua biến môi trường:

```env
KG_CONTRACT_PATH=/opt/vifood/contracts/kg_schema_contract.json
KG_CONTRACT_VERSION=2026-07-13.1
```

Contract cho Builder biết:

- Release canonical nào dùng để match `Nutrient`.
- Release canonical nào dùng để match `Additive`.
- Match keys cho từng entity.
- Provenance rules nội bộ.
- `Ingredient` nằm ngoài canonical catalog của `ViFood-KG` và do Builder xử lý runtime.

## Flow Tổng

```text
Ảnh nhãn từ ViFood-API
  -> validate request
  -> KIE extraction qua LLM-KIE 2
  -> normalize thành nutritions / additives / ingredients
  -> Nutrient flow
  -> Additive flow
  -> Ingredient flow
  -> Neo4j/KG contract
  -> build FinalLabelResponse public
  -> trả về ViFood-API
```

## Flow Nutrient

`Nutrient` là catalog-first.

```text
nutritions từ nhãn
  -> normalize NutrientInput
  -> match canonical Nutrient trong KG trước
  -> ưu tiên external_code / INFOODS tagname
  -> fallback name / alias
  -> nếu match: dùng node có sẵn
  -> nếu không match: runtime fallback create có kiểm soát
```

## Flow Additive

`Additive` là catalog-first.

```text
additives từ nhãn
  -> parse/normalize INS hoặc E-code
  -> match canonical Additive trong KG trước
  -> ưu tiên INS / E-code
  -> fallback name / alias
  -> nếu match: dùng node có sẵn
  -> nếu không match: runtime fallback create có kiểm soát
```

## Flow Ingredient

`Ingredient` không có catalog nền từ `ViFood-KG`. Builder xử lý theo hướng graph-first.

```text
ingredients từ nhãn
  -> match graph trước
  -> nếu đã có: dùng node có sẵn
  -> nếu chưa có: resolve Wikidata QID trong ngữ cảnh thành phần thực phẩm
  -> lấy candidate bằng Wikidata mwapi search
  -> annotate candidate bằng food signal
  -> chọn theo food signal / exact label / rank
  -> lấy detail bằng QID
  -> tạo Ingredient / Alias / Usage / Source / relationships
```

Ingredient mới dùng ID dạng:

```text
INGREDIENT:{WIKIDATA_QID}
```

## Output Cuối Cùng Cho Backend API

Response public cuối cùng chỉ chứa thông tin có trên nhãn và danh sách entity đã được liên kết graph. Backend API sẽ bổ sung `analysis_id`, `image_ref`, lưu S3 và lưu history sau khi Builder trả success. Builder không trả metadata kỹ thuật, contract version, release IDs, provenance, source nodes, Wikidata detail, status hoặc errors nội bộ.

Ví dụ:

```json
{
  "product_name": "Sữa đậu nành ABC",
  "brand": "ABC",
  "serving_size": "180 ml",
  "nutritions": {
    "energy": 120,
    "protein": {
      "id": "NUTRIENT:INFOODS_PROCNT",
      "name": "Protein",
      "value": 1,
      "unit": "g"
    }
  },
  "ingredients": [
    {
      "id": "INGREDIENT:Q10943",
      "name": "Victoria pineapple",
      "percentage": 96
    }
  ],
  "additives": [
    {
      "id": "ADDITIVE:INS_330",
      "name": "Citric acid",
      "ins": "330"
    }
  ]
}
```

Các field public chính:

```text
product_name
age_range
ingredients
additives
nutritions
manufacturer
mfg_date
expiry_date
net_weight
warning
origin
```

Không trả field không tìm thấy, field rỗng, `null`, metadata kỹ thuật hoặc debug data. Với entity đã liên kết graph, item public giữ `id` và `name`.

## API Chính

```http
POST /labels/analyze
Content-Type: application/json
```

```json
{
  "request_id": "analysis_20260813_0001",
  "image_base64": "...",
  "content_type": "image/jpeg",
  "metadata": {
    "source": "vifood-api"
  }
}
```

Builder không chấp nhận request chỉ có `s3_key`, `image_ref` hoặc storage key.

## Cài Đặt

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Cấu Hình Chính

Các giá trị runtime nằm trong `.env`. `.env.example` liệt kê đầy đủ các nhóm chính:

- Neo4j source/target: `SOURCE_NEO4J_*`, `TARGET_NEO4J_*`
- KG contract: `KG_CONTRACT_PATH`, `KG_CONTRACT_VERSION`
- Graph labels: `INGREDIENT_LABEL`, `ADDITIVE_LABEL`, `NUTRIENT_LABEL`, `SOURCE_LABEL`, `REGULATION_LABEL`
- KIE model: `KIE_MODEL_URL`, `KIE_MODEL_TIMEOUT_SECONDS`
- Wikidata Ingredient flow: `WIKIDATA_*`
- OpenAI nutrient fallback: `OPENAI_API_KEY`, `MODEL`

Wikidata search dùng `WIKIDATA_SEARCH_LANGUAGE`, `WIKIDATA_SEARCH_LIMIT`, `WIKIDATA_FOOD_SIGNAL_QIDS` để chọn đúng candidate trong ngữ cảnh thực phẩm, ví dụ tránh chọn `đường` theo nghĩa `road`.

## Chạy Local

Chạy Builder:

```bash
uvicorn src.app:app --host 0.0.0.0 --port 8002 --reload
```

Swagger UI:

```text
http://localhost:8002/docs
```

## CLI Hiện Có

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
