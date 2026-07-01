# ViFood-KG-Builder

`ViFood-KG-Builder` là batch pipeline Python dùng để tạo dữ liệu wiki tri thức cho `ViFood-KG` từ Neo4j nguồn `ViFood-KC`.

Project này không phải API server. Nó chỉ làm nhiệm vụ đọc dữ liệu nguồn, sinh nội dung wiki, validate, xuất JSON review và import vào Target Neo4j.

## Pipeline

```text
Source Neo4j ViFood-KC
-> Extract Ingredient/Additive/Nutrient + relationships
-> Compute source_hash
-> Skip entity đã import bằng state file
-> Build semantic context
-> Gemini sinh WikiSection
-> Build WikiProfile
-> Validate JSON
-> Import vào Target Neo4j ViFood-KG
-> Mark imported entity vào state file
```

Source và Target là hai Neo4j riêng. Pipeline chỉ đọc Source và chỉ ghi Target.

## Dữ Liệu Sinh Ra

Target Neo4j chỉ thêm lớp wiki:

```cypher
(:Ingredient|Additive|Nutrient)-[:HAS_WIKI_PROFILE]->(:WikiProfile)
(:WikiProfile)-[:HAS_SECTION {order}]->(:WikiSection)
```

`WikiProfile` là trang wiki tổng thể của entity. `WikiSection` là các mục nội dung bên trong trang.

Các `section_type` hiện dùng:

- `overview`
- `classification_and_role`
- `common_foods`
- `health_note`
- `source_and_regulation`

## Cấu Hình

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` cần có:

```env
SOURCE_NEO4J_URI=bolt://localhost:7687
SOURCE_NEO4J_USER=neo4j
SOURCE_NEO4J_PASSWORD=change_me
SOURCE_NEO4J_DATABASE=vifood

TARGET_NEO4J_URI=bolt://localhost:7688
TARGET_NEO4J_USER=neo4j
TARGET_NEO4J_PASSWORD=change_me
TARGET_NEO4J_DATABASE=neo4j

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_RETRIES=6
GEMINI_RETRY_BASE_SECONDS=5
GEMINI_REQUEST_DELAY_SECONDS=1
```

## CLI

Extract dữ liệu thô:

```bash
python -m src.main extract --type additive --limit 10
```

Build JSON review, chưa import:

```bash
python -m src.main build --type additive --limit 10
```

Batch generate, validate, import và cập nhật state:

```bash
python -m src.main batch --entity-type additive --limit 10
```

Dry-run:

```bash
python -m src.main batch --entity-type additive --limit 10 --dry-run
```

Import JSON có sẵn:

```bash
python -m src.main import --file data/output/wiki_additive.json
```

Validate JSON:

```bash
python -m src.main validate --file data/output/wiki_additive.json
```

## State File

Pipeline dùng state file để tránh import lại dữ liệu đã xử lý:

```text
data/state/imported_entities.json
```

Sau khi import thành công, entity được ghi lại cùng `source_hash`. Lần sau, nếu dữ liệu nguồn không đổi, batch sẽ bỏ qua entity đó. Nếu muốn xử lý lại toàn bộ:

```bash
python -m src.main batch --entity-type additive --reprocess-imported --force
```

`--limit` được áp dụng sau khi skip entity đã import. Ví dụ `--limit 10` nghĩa là xử lý tối đa 10 entity chưa import.

## Output

JSON review nằm trong:

```text
data/output/
```

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

## Lưu Ý

- Gemini chỉ được dùng dữ liệu extract từ Source Neo4j, không tự thêm kiến thức ngoài.
- Nội dung wiki phải trung lập, không kết luận an toàn/nguy hiểm tuyệt đối.
- Nếu Gemini quota/high demand (`429`, `503`), batch sẽ dừng sớm nhưng vẫn import phần đã generate được.
- Nếu xoá sạch Target Neo4j, cần xoá state file hoặc chạy với `--reprocess-imported`.

## Kiểm Tra

```bash
python -m compileall src
pytest
```
