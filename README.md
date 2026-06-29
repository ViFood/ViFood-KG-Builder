# ViFood-KG-Builder

`ViFood-KG-Builder` là batch pipeline Python dùng để tạo dữ liệu wiki tri thức cho `ViFood-KG` từ Neo4j nguồn `ViFood-KC`.

Project này không phải FastAPI server và không chứa logic runtime của `ViFood-API`. `ViFood-API` chỉ query dữ liệu đã build trong Target Neo4j; việc đọc nguồn, gọi AI, validate và import thuộc CLI project này.

## Luồng Xử Lý

1. Đọc `Ingredient`, `Additive`, `Nutrient` và các quan hệ liên quan từ Source Neo4j.
2. Tạo semantic context từ dữ liệu đã extract.
3. Gửi context cho AI để diễn giải thành `WikiSection` tự nhiên, dễ hiểu cho người dùng app.
4. Validate JSON review.
5. Import `Ingredient`, `Additive`, `Nutrient`, `WikiProfile`, `WikiSection` vào Target Neo4j bằng `MERGE`.

AI chỉ được dùng dữ liệu lấy từ Source Neo4j trong payload truyền vào. Prompt yêu cầu không tự thêm kiến thức ngoài, không kết luận an toàn/nguy hiểm tuyệt đối, và không dùng các cụm mang tính hệ thống như `graph`, `node`, `relationship`, `hồ sơ`, `dữ liệu hiện liên kết`, `được ghi nhận trong ViFood-KC`.

## Cấu Hình

Tạo môi trường và cài dependency:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`ViFood-KC` và `ViFood-KG` phải là hai database hoặc instance Neo4j riêng:

```env
# Source Neo4j: chỉ đọc dữ liệu gốc.
SOURCE_NEO4J_URI=bolt://localhost:7687
SOURCE_NEO4J_USER=neo4j
SOURCE_NEO4J_PASSWORD=change_me
SOURCE_NEO4J_DATABASE=vifood

# Target Neo4j: chỉ ghi dữ liệu wiki đã build.
TARGET_NEO4J_URI=bolt://localhost:7688
TARGET_NEO4J_USER=neo4j
TARGET_NEO4J_PASSWORD=change_me
TARGET_NEO4J_DATABASE=neo4j

# AI section generation.
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

CLI sẽ dừng nếu Source và Target trỏ cùng URI/user/database để tránh ghi ngược vào Source.

## CLI

Extract dữ liệu thô từ Source Neo4j:

```bash
python -m src.main extract --type additive --limit 10
python -m src.main extract --type ingredient
python -m src.main extract --type nutrient
```

Build JSON review bằng AI, chưa import:

```bash
python -m src.main build --type additive --limit 10
python -m src.main build --type ingredient
python -m src.main build --type nutrient
python -m src.main build --type all
```

Batch có cache theo `source_hash`, validate và import sang Target nếu không dùng `--dry-run`:

```bash
python -m src.main batch --entity-type additive --limit 10 --dry-run
python -m src.main batch --entity-type all --limit 100
python -m src.main batch --entity-type nutrient --force
```

`--dry-run` chỉ ghi JSON review và validate, không import. `--force` bỏ qua cache và gọi AI lại dù `source_hash` đang trùng.

Validate JSON:

```bash
python -m src.main validate --file data/output/wiki_additive.json
```

Import JSON đã review vào Target Neo4j:

```bash
python -m src.main import --file data/output/wiki_additive.json
```

## Output JSON

Output mặc định nằm trong `data/output/`:

- `wiki_additive.json`
- `wiki_ingredient.json`
- `wiki_nutrient.json`
- `wiki_all.json`

Mỗi item có dạng:

```json
{
  "entity_id": "additive:e330",
  "entity_type": "additive",
  "source_hash": "...",
  "source_entity": {},
  "wiki_profile": {},
  "wiki_sections": [],
  "facts": [],
  "related": {},
  "evidence": {},
  "ai_status": "generated"
}
```

AI output chỉ nhận các `section_type` sau:

- `overview`
- `role_and_usage`
- `common_foods`
- `regulation`
- `consumer_note`

Nếu dữ liệu nguồn không đủ cho một section, section đó được bỏ qua. Nếu một entity không sinh được section nào thì item đó không được đưa vào JSON import.

## Neo4j Target Schema

Import chỉ thêm hoặc cập nhật các node/wiki phục vụ app:

```cypher
(:Ingredient|Additive|Nutrient)-[:HAS_WIKI_PROFILE]->(:WikiProfile)
(:WikiProfile)-[:HAS_SECTION {order}]->(:WikiSection)
```

Loader dùng `MERGE`, không xóa dữ liệu cũ và không tạo thêm các node quan hệ ngoài luồng như `Source`, `Regulation`, `FoodCategory`. `WikiProfile` và `WikiSection` có `source_hash`; khi dữ liệu nguồn không đổi, batch có thể dùng lại section đã có trên Target thay vì gọi AI lại.

## Kiểm Tra

```bash
python -m compileall src
pytest
```

Không cần kết nối Neo4j thật để chạy compile/test cơ bản. Các lệnh extract/build/batch/import cần `.env` hợp lệ.
