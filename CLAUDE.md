# quote_compare — 견적서 가격비교 시스템

## 프로젝트 개요

기안서(견적서) PDF를 파싱하여 품목별 가격을 DB에 저장하고,
신규 견적서 업로드 시 과거 동일/유사 품목의 가격을 비교하는 시스템.

## 아키텍처

```
PDF 업로드 → 파싱(3단계 폴백) → LLM 구조화 → DB 저장 → 유사 품목 검색 → 가격 비교
```

### 파싱 3단계 폴백
1. docling (AI 기반, 테이블 인식 우수)
2. pdfplumber (경량, 텍스트 PDF에 적합)
3. OCR - ocrmac (이미지/스캔 PDF)

### DB
- MVP: SQLite (quote_compare.db)
- 운영: SQL Server (나중에 전환)

## 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 기존 견적서 일괄 파싱
python src/batch_parse.py data/

# 웹 UI
streamlit run app.py
```

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `src/parser.py` | PDF 파싱 (docling → pdfplumber → OCR 폴백) |
| `src/extractor.py` | LLM으로 품목 구조화 추출 |
| `src/db.py` | SQLite CRUD |
| `src/search.py` | 유사 품목 검색 |
| `app.py` | Streamlit 웹 UI |
| `src/batch_parse.py` | 기존 견적서 일괄 처리 |

## DB 스키마

```sql
-- 기안서 헤더
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT,
    doc_date DATE,
    parsed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_type TEXT  -- 'batch' / 'upload'
);

-- 업체별 견적
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER REFERENCES documents(id),
    supplier TEXT,
    supplier_biz TEXT,
    subtotal INTEGER,
    vat INTEGER,
    total INTEGER
);

-- 품목
CREATE TABLE line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER REFERENCES quotes(id),
    item_type TEXT DEFAULT 'product',
    raw_name TEXT,
    normalized_name TEXT,
    brand TEXT,
    model TEXT,
    spec TEXT,
    unit TEXT,
    quantity INTEGER,
    unit_price INTEGER,
    supply_amount INTEGER
);
```
