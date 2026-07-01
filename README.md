# ViFood-KG-Builder

`ViFood-KG-Builder` là batch data pipeline dùng để tạo lớp dữ liệu wiki tri thức cho `ViFood-KG` từ Neo4j nguồn `ViFood-KC`.

Project này không phải API server. Nó không chứa runtime logic của `ViFood-API`. `ViFood-API` chỉ nên đọc dữ liệu wiki đã được build trong Target Neo4j; việc đọc dữ liệu nguồn, sinh nội dung, validate, ghi JSON review và import thuộc project CLI này.

## Mục Tiêu

Pipeline chuyển dữ liệu gốc có cấu trúc từ `ViFood-KC` thành nội dung wiki dễ đọc cho người dùng app:

- Giữ nguyên dữ liệu gốc ở Source Neo4j.
- Chỉ ghi dữ liệu wiki sang Target Neo4j.
- Sinh `WikiProfile` và `WikiSection` cho `Ingredient`, `Additive`, `Nutrient`.
- Nội dung viết tự nhiên, trung lập, không kết luận an toàn/nguy hiểm tuyệt đối.
- Gemini chỉ được dùng dữ liệu đã extract từ Source Neo4j, không tự thêm kiến thức ngoài.
- Có JSON review trước/sau batch để kiểm tra.
- Có state file để lần sau chỉ xử lý dữ liệu chưa import hoặc dữ liệu có `source_hash` thay đổi.

## Kiến Trúc

```text
Source Neo4j ViFood-KC
  -> Extract entity + relationships
  -> Compute source_hash
  -> Skip imported entities by state file
  -> Build semantic context
  -> Generate WikiSection with Gemini
  -> Build WikiProfile
  -> Validate JSON
  -> Write review JSON
  -> Import into Target Neo4j ViFood-KG
  -> Mark imported entities in state file
```

Hai Neo4j phải tách riêng:

- `SourceNeo4jConnection`: chỉ đọc dữ liệu gốc từ `ViFood-KC`.
- `TargetNeo4jConnection`: chỉ ghi dữ liệu wiki sang `ViFood-KG`.

CLI sẽ dừng nếu Source và Target trỏ cùng URI/user/database.

## Cấu Trúc Module

```text
src/config/      Đọc cấu hình .env
src/db/          Neo4j connection wrapper
src/extract/     Extract Ingredient/Additive/Nutrient từ Source Neo4j
src/transform/   Build semantic context, source_hash, WikiProfile, WikiSection bằng Gemini
src/validate/    Validate JSON review trước khi import
src/load/        Import JSON vào Target Neo4j bằng MERGE
src/state/       Theo dõi entity đã import bằng file state
src/main.py      CLI entrypoint
```

## Entity Coverage

### Ingredient

Extractor đọc node `Ingredient` và các quan hệ:

- `IN_GROUP -> IngredientGroup`
- `IS_A -> Ingredient`
- `DERIVED_FROM -> Ingredient`
- `CONTAINS_ALLERGEN -> Allergen`
- `HAS_NUTRIENT -> Nutrient`
- `SUPPORTED_BY -> Source`
- `Alias -[:REFERS_TO]-> Ingredient`

### Additive

Extractor đọc node `Additive` và các quan hệ:

- `HAS_FUNCTION -> FunctionalClass`
- `PERMITTED_IN -> FoodCategory`
- `SUPPORTED_BY -> Source`
- `Alias -[:REFERS_TO]-> Additive`
- `Regulation -[:GOVERNS]-> Additive`

### Nutrient

Extractor đọc node `Nutrient` và các quan hệ:

- `SUPPORTED_BY -> Source`
- `HealthClaim -[:SUBJECT_OF]-> Nutrient`
- `Ingredient -[:HAS_NUTRIENT]-> Nutrient`
- `Alias -[:REFERS_TO]-> Nutrient`

## Target Neo4j Schema

Import chỉ tạo/cập nhật các node phục vụ wiki:

```cypher
(:Ingredient|Additive|Nutrient)-[:HAS_WIKI_PROFILE]->(:WikiProfile)
(:WikiProfile)-[:HAS_SECTION {order}]->(:WikiSection)
```

Loader không tạo thêm `Source`, `Regulation`, `FoodCategory`, `FunctionalClass` trong Target. Các dữ liệu liên quan chỉ nằm trong JSON review để sinh nội dung và truy vết.

Import dùng `MERGE`, không xoá dữ liệu cũ.

## WikiProfile Và WikiSection

`WikiProfile` đại diện cho trang wiki tổng thể của một entity:

```json
{
  "id": "WIKI:ADDITIVE:INS_100_I",
  "title": "Curcumin",
  "subtitle": "INS 100(i)",
  "summary": "...",
  "entity_type": "additive",
  "language": "vi",
  "audience": "consumer",
  "status": "draft",
  "source_hash": "..."
}
```

`WikiSection` là từng mục nội dung bên trong trang wiki:

```json
{
  "id": "WIKI:ADDITIVE:INS_100_I:overview",
  "title": "Tổng quan",
  "section_type": "overview",
  "content": "...",
  "order": 1,
  "status": "draft",
  "source_hash": "...",
  "generated_by": "gemini"
}
```

Các `section_type` hợp lệ:

- `overview`
- `classification_and_role`
- `common_foods`
- `health_note`
- `source_and_regulation`

Nếu dữ liệu nguồn không đủ cho một section, Gemini phải bỏ section đó.

## Source Hash Và State File

Mỗi entity được tính `source_hash` từ:

- properties của node gốc
- relationships đã extract
- entity type

`source_hash` được normalize để không phụ thuộc vào thứ tự relationship list trả về từ Neo4j.

Sau khi import thành công, pipeline ghi entity vào state file:

```text
data/state/imported_entities.json
```

State entry gồm:

- `entity_type`
- `entity_id`
- `source_hash`
- `wiki_profile_id`
- `section_count`
- `section_types`
- `imported_at`
- `output_file`

Lần chạy sau, nếu entity đã có trong state với cùng `source_hash`, batch sẽ bỏ qua entity đó. Nếu dữ liệu nguồn thay đổi làm `source_hash` đổi, entity sẽ được xử lý lại.

Nếu Target bị xoá thủ công nhưng state file vẫn còn, batch sẽ tưởng entity đã import và bỏ qua. Khi reset Target, hãy xoá file state tương ứng hoặc chạy với `--reprocess-imported`.

## Cài Đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Cấu Hình `.env`

```env
# ViFood-KC: Source Neo4j, chỉ đọc.
SOURCE_NEO4J_URI=bolt://localhost:7687
SOURCE_NEO4J_USER=neo4j
SOURCE_NEO4J_PASSWORD=change_me
SOURCE_NEO4J_DATABASE=vifood

# ViFood-KG: Target Neo4j, chỉ ghi wiki.
TARGET_NEO4J_URI=bolt://localhost:7688
TARGET_NEO4J_USER=neo4j
TARGET_NEO4J_PASSWORD=change_me
TARGET_NEO4J_DATABASE=neo4j

# Optional labels.
INGREDIENT_LABEL=Ingredient
ADDITIVE_LABEL=Additive
NUTRIENT_LABEL=Nutrient
SOURCE_LABEL=Source
REGULATION_LABEL=Regulation

# Gemini.
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_RETRIES=6
GEMINI_RETRY_BASE_SECONDS=5
GEMINI_REQUEST_DELAY_SECONDS=1
```

Không hardcode credential trong code.

## CLI

Extract dữ liệu thô từ Source:

```bash
python -m src.main extract --type additive --limit 10
python -m src.main extract --type ingredient --limit 10
python -m src.main extract --type nutrient --limit 10
```

Build JSON review bằng Gemini nhưng chưa import:

```bash
python -m src.main build --type additive --limit 10
python -m src.main build --type ingredient --limit 10
python -m src.main build --type nutrient --limit 10
python -m src.main build --type all --limit 10
```

Batch extract, generate, validate, import, rồi cập nhật state:

```bash
python -m src.main batch --entity-type additive --limit 10
python -m src.main batch --entity-type ingredient --limit 10
python -m src.main batch --entity-type nutrient --limit 10
python -m src.main batch --entity-type all --limit 10
```

Dry-run chỉ ghi JSON review, không import và không mark state:

```bash
python -m src.main batch --entity-type additive --limit 10 --dry-run
```

Chạy lại entity đã import:

```bash
python -m src.main batch --entity-type additive --reprocess-imported
```

Dùng state file khác:

```bash
python -m src.main batch --entity-type additive --state-file data/state/additive_imported.json
```

Validate JSON:

```bash
python -m src.main validate --file data/output/wiki_additive.json
```

Import JSON có sẵn vào Target và cập nhật state:

```bash
python -m src.main import --file data/output/wiki_additive.json
```

## Ý Nghĩa Các Flag Batch

- `--entity-type`: chọn `ingredient`, `additive`, `nutrient`, hoặc `all`.
- `--limit`: số entity chưa import tối đa cần xử lý. Khi dùng state, limit được áp dụng sau bước skip imported.
- `--dry-run`: ghi JSON review và validate nhưng không import.
- `--force`: bỏ qua cache trong Target, gọi Gemini lại nếu cần.
- `--reprocess-imported`: bỏ qua state file và xử lý lại cả entity đã import.
- `--state-file`: đường dẫn file state.

## Output JSON

Output mặc định nằm trong `data/output/`:

- `raw_additive.json`, `raw_ingredient.json`, `raw_nutrient.json` cho lệnh extract
- `wiki_additive.json`, `wiki_ingredient.json`, `wiki_nutrient.json`, `wiki_all.json` cho build/batch

Mỗi item wiki có dạng:

```json
{
  "entity_id": "...",
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

`ai_status` có thể là:

- `generated`: nội dung vừa được Gemini sinh.
- `cached`: nội dung lấy lại từ Target do `source_hash` không đổi.

## Gemini Prompt Rules

Prompt yêu cầu Gemini:

- chỉ dùng JSON nguồn đã cung cấp
- không thêm kiến thức ngoài
- viết tiếng Việt tự nhiên, dễ hiểu, trung lập
- không dùng từ/cụm mang tính hệ thống như `graph`, `node`, `relationship`, `hồ sơ`, `dữ liệu hiện liên kết`, `ViFood-KC`
- không kết luận an toàn tuyệt đối hoặc nguy hiểm tuyệt đối
- không gom nhiều mục đích vào cùng một section
- không lặp cùng một ý ở nhiều section

## Validate Rules

Validator kiểm tra:

- `WikiProfile` có `id`, `title`, `summary`, `entity_type`, `language`, `status`, `source_hash`
- `WikiSection` có `id`, `title`, `content`, `section_type`, `status`, `source_hash`
- `section_type` thuộc danh sách hợp lệ
- `content` không rỗng
- item có dữ liệu nguồn hoặc evidence
- `Additive` có `ins`
- `Nutrient` có `external_code` và `default_unit`
- `Ingredient` có `external_code`

## Xử Lý Lỗi Gemini

Gemini có thể trả lỗi quota hoặc tải cao:

```text
429 RESOURCE_EXHAUSTED
503 UNAVAILABLE
```

Generator có retry/backoff theo `.env`. Nếu vẫn lỗi, batch dừng sớm nhưng vẫn ghi JSON và import những item đã generate được trước đó. Các item import thành công sẽ được mark vào state file.

## Vận Hành Khuyến Nghị

Chạy theo lô nhỏ để tránh quota:

```bash
python -m src.main batch --entity-type additive --limit 10
```

Khi hết quota, dừng lại. Lần sau chạy lại cùng lệnh; state file sẽ bỏ qua entity đã import và tiếp tục phần còn lại.

Khi đổi prompt hoặc muốn rebuild toàn bộ nội dung:

```bash
python -m src.main batch --entity-type additive --reprocess-imported --force
```

Khi xoá sạch Target để build lại từ đầu, xoá state file tương ứng hoặc dùng `--reprocess-imported`.

## Kiểm Tra

```bash
python -m compileall src
pytest
```

Các test cơ bản không cần kết nối Neo4j thật. Các lệnh extract/build/batch/import cần `.env` hợp lệ và Neo4j/Gemini khả dụng.
