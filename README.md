# ViFood-KG-Builder

`ViFood-KG-Builder` là batch pipeline Python dùng để chuyển dữ liệu từ Neo4j nguồn `ViFood-KC` sang Neo4j đích `ViFood-KG`.

Đây không phải FastAPI server và không chứa runtime logic của `ViFood-API`. `ViFood-API` chỉ nên query dữ liệu wiki đã build trong `ViFood-KG`; việc extract, transform, validate và import thuộc project CLI này.

## Kiến trúc

Pipeline chạy theo các bước:

1. `extract`: đọc `Ingredient`, `Additive`, `Nutrient` và relationship liên quan từ Neo4j nguồn `ViFood-KC`.
2. `transform`: tạo semantic context, `WikiProfile`, `WikiSection` bằng văn bản tiếng Việt gần với người dùng.
3. `validate`: kiểm tra field bắt buộc, nguồn dữ liệu và rule riêng từng entity type.
4. `build`: xuất JSON review để con người rà soát trước khi import.
5. `import`: ghi sang Neo4j đích `ViFood-KG` bằng `MERGE`.

Trong code, hai kết nối được tách theo vai trò:

- `Neo4jConnection`: class nền cung cấp `read`, `write`, `close`.
- `SourceNeo4jConnection`: chỉ dùng cho extractor và chỉ đọc từ `ViFood-KC`.
- `TargetNeo4jConnection`: chỉ dùng cho loader và chỉ ghi sang `ViFood-KG`.

CLI sẽ dừng nếu `SOURCE_NEO4J_*` và `TARGET_NEO4J_*` đang trỏ cùng một URI/user/database, vì đó là cấu hình sai với kiến trúc của project.

Import không xóa dữ liệu cũ, không sửa node/relationship gốc ngoài việc thêm:

```cypher
(:Entity)-[:HAS_WIKI_PROFILE]->(:WikiProfile)
(:WikiProfile)-[:HAS_SECTION {order}]->(:WikiSection)
(:WikiSection)-[:SUPPORTED_BY]->(:Source|Regulation)
```

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Cấu hình `.env`

`ViFood-KC` và `ViFood-KG` là hai Neo4j khác nhau:

```env
SOURCE_NEO4J_URI=bolt://localhost:7687
SOURCE_NEO4J_USER=neo4j
SOURCE_NEO4J_PASSWORD=change_me
SOURCE_NEO4J_DATABASE=vifood-kc

TARGET_NEO4J_URI=bolt://localhost:7688
TARGET_NEO4J_USER=neo4j
TARGET_NEO4J_PASSWORD=change_me
TARGET_NEO4J_DATABASE=vifood-kg
```

Không hardcode credential trong code. Nếu thiếu password, CLI sẽ báo lỗi cấu hình rõ ràng.

Các biến cũ dạng `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` không được dùng cho pipeline này, vì chúng không phân biệt được Neo4j nguồn `ViFood-KC` và Neo4j đích `ViFood-KG`.

## CLI

Extract raw data từ `ViFood-KC`:

```bash
python -m src.main extract --type additive
python -m src.main extract --type ingredient --limit 100
python -m src.main extract --type nutrient
```

Build JSON review:

```bash
python -m src.main build --type additive
python -m src.main build --type ingredient
python -m src.main build --type nutrient
python -m src.main build --type all
```

Output mặc định:

- `data/output/wiki_additive.json`
- `data/output/wiki_ingredient.json`
- `data/output/wiki_nutrient.json`
- `data/output/wiki_all.json`

Validate trước khi import:

```bash
python -m src.main validate --file data/output/wiki_additive.json
```

Import sang `ViFood-KG`:

```bash
python -m src.main import --file data/output/wiki_additive.json
```

## JSON Output

Mỗi item trong JSON build có dạng:

```json
{
  "entity_id": "...",
  "entity_type": "additive",
  "wiki_profile": {},
  "wiki_sections": [],
  "facts": [],
  "related": {},
  "evidence": {}
}
```

`wiki_sections[].content` là văn bản tri thức tiếng Việt, không chỉ liệt kê field thô. Nội dung giữ giọng trung lập, có nguồn, và tránh kết luận kiểu “an toàn tuyệt đối” hoặc “nguy hiểm tuyệt đối”.

## Extractor Coverage

Ingredient:

- `IN_GROUP`
- `IS_A`
- `DERIVED_FROM`
- `CONTAINS_ALLERGEN`
- `HAS_NUTRIENT`
- `SUPPORTED_BY`
- `Alias -[:REFERS_TO]-> Ingredient`

Additive:

- `HAS_FUNCTION`
- `PERMITTED_IN`
- `SUPPORTED_BY`
- `Alias -[:REFERS_TO]-> Additive`
- `Regulation -[:GOVERNS]-> Additive`

Nutrient:

- `SUPPORTED_BY`
- `HealthClaim -[:SUBJECT_OF]-> Nutrient`
- `Ingredient -[:HAS_NUTRIENT]-> Nutrient`
- `Alias -[:REFERS_TO]-> Nutrient`

## Validate Rules

- `WikiProfile` phải có `id`, `title`, `summary`, `entity_type`, `language`, `status`.
- `WikiSection` phải có `id`, `title`, `content`, `section_type`, `status`.
- `content` không rỗng.
- Entity phải có nguồn hoặc `SUPPORTED_BY` source.
- `Additive` phải có `ins`.
- `Nutrient` phải có `external_code` và `default_unit`.
- `Ingredient` phải có `external_code`.

## Import Cypher

CLI dùng `src/load/neo4j_loader.py`. Nếu muốn chạy thủ công, xem:

```text
cypher/import_wiki.cypher
```

Chỉ chạy file này trên Neo4j đích `ViFood-KG`.
