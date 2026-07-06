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
-> Template sinh WikiSection từ dữ liệu đã extract
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

INGREDIENT_LABEL=Ingredient
ADDITIVE_LABEL=Additive
NUTRIENT_LABEL=Nutrient
```

`INGREDIENT_LABEL`, `ADDITIVE_LABEL` và `NUTRIENT_LABEL` được dùng cho node entity chính khi extract dữ liệu từ Source Neo4j. Các label quan hệ phụ như `Source`, `Regulation`, `FunctionalClass`, `FoodCategory` hiện vẫn theo schema ViFood-KC mặc định.

## CLI

Extract dữ liệu thô:

```bash
python -m src.main extract --type additive --limit 10
```

Build JSON review từ Source Neo4j, chưa import:

```bash
python -m src.main build --type additive --limit 10
```

Build JSON review từ file raw đã extract, không query Source Neo4j lại:

```bash
python -m src.main build --type additive --input data/output/raw_additive.json --limit 10
```

Batch generate, validate, import và cập nhật state:

```bash
python -m src.main batch --entity-type additive --limit 10
```

Batch từ file raw đã extract, không query Source Neo4j lại:

```bash
python -m src.main batch --entity-type additive --input data/output/raw_additive.json --limit 10
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

## Chạy Nhanh Hơn Với Raw Cache

Nếu Source Neo4j có nhiều node, nên extract một lần rồi build/batch từ file raw local:

```bash
python -m src.main extract --type additive
python -m src.main batch --entity-type additive --input data/output/raw_additive.json --limit 20
python -m src.main batch --entity-type additive --input data/output/raw_additive.json --limit 20
```

Các lần `batch --input` không query Source Neo4j nữa. Pipeline vẫn đọc `data/state/imported_entities.json` để bỏ qua entity đã import cùng `source_hash`, nên bạn có thể chạy lặp lại theo lô nhỏ.

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
  "generation_status": "template"
}
```

## Lưu Ý

- Pipeline dùng template generator, không cần dịch vụ sinh nội dung bên ngoài.
- Nội dung wiki sinh ra có `status: draft`; cần review nghiệp vụ trước khi xem là nội dung cuối.
- Nội dung wiki phải trung lập, không kết luận an toàn/nguy hiểm tuyệt đối.
- Nếu xoá sạch Target Neo4j, cần xoá state file hoặc chạy với `--reprocess-imported`.

## Kiểm Tra

```bash
python -m compileall src
pytest
```
