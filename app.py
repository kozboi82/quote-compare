"""견적서 가격비교 시스템 — Streamlit UI."""

import os
import sys
import json
import tempfile
import streamlit as st
import sqlite3
from datetime import datetime

sys.path.insert(0, "src")
from parser import parse_pdf
from extractor import extract_items
from db import init_db, insert_document, insert_quote, insert_line_item, search_similar_items, get_conn

# DB 초기화
init_db()

st.set_page_config(page_title="견적서 가격비교", page_icon="📊", layout="wide")
st.title("📊 견적서 가격비교 시스템")

tab1, tab2, tab3 = st.tabs(["📤 견적서 업로드", "🔍 품목 검색", "📋 DB 현황"])

# ── 탭 1: 견적서 업로드 ──────────────────────────────────────

with tab1:
    st.header("견적서 PDF 업로드")

    uploaded = st.file_uploader("PDF 파일을 올려주세요", type=["pdf"])

    if uploaded:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        st.info(f"📄 {uploaded.name} ({uploaded.size / 1024:.0f}KB)")

        # 파싱
        with st.spinner("PDF 파싱 중..."):
            text, tool = parse_pdf(tmp_path)

        if not text or len(text) < 30:
            st.error("❌ 파싱 실패 — 텍스트를 추출할 수 없습니다.")
            os.unlink(tmp_path)
            st.stop()

        st.success(f"✅ 파싱 완료 ({tool}, {len(text)}자)")

        with st.expander("파싱 원문 보기"):
            st.code(text[:2000])

        # LLM 추출
        with st.spinner("품목 추출 중 (LLM)..."):
            try:
                result = extract_items(text)
            except Exception as e:
                st.error(f"❌ LLM 추출 실패: {e}")
                os.unlink(tmp_path)
                st.stop()

        os.unlink(tmp_path)

        # 추출 결과 표시
        quotes = result.get("quotes", [])
        doc_date = result.get("doc_date", "")

        st.subheader(f"📋 추출 결과 (견적일: {doc_date}, {len(quotes)}개 업체)")

        for qi, q in enumerate(quotes):
            supplier = q.get("supplier", "업체명 없음")
            total = q.get("total", 0)
            items = q.get("items", [])

            st.markdown(f"### {supplier} (합계: {total:,}원)")

            if items:
                import pandas as pd
                df = pd.DataFrame(items)
                display_cols = ["raw_name", "normalized_name", "brand", "quantity", "unit_price", "supply_amount"]
                display_cols = [c for c in display_cols if c in df.columns]
                col_names = {
                    "raw_name": "품명",
                    "normalized_name": "정규화",
                    "brand": "브랜드",
                    "quantity": "수량",
                    "unit_price": "단가",
                    "supply_amount": "공급가액",
                }
                df_display = df[display_cols].rename(columns=col_names)
                st.dataframe(df_display, use_container_width=True)

                # 각 품목별 과거 가격 비교
                st.markdown("#### 📊 과거 가격 비교")
                for item in items:
                    norm_name = item.get("normalized_name", "")
                    if not norm_name:
                        continue
                    past = search_similar_items(norm_name, limit=5)
                    if past:
                        st.markdown(f"**{norm_name}** — 과거 {len(past)}건")
                        past_df = pd.DataFrame(past)
                        past_cols = ["raw_name", "unit_price", "quantity", "supplier", "doc_date"]
                        past_cols = [c for c in past_cols if c in past_df.columns]
                        past_names = {
                            "raw_name": "품명",
                            "unit_price": "단가",
                            "quantity": "수량",
                            "supplier": "공급사",
                            "doc_date": "견적일",
                        }
                        st.dataframe(
                            past_df[past_cols].rename(columns=past_names),
                            use_container_width=True,
                        )
                    else:
                        st.caption(f"**{norm_name}** — 과거 이력 없음")

        # DB 저장 버튼
        st.divider()
        if st.button("💾 DB에 저장", type="primary"):
            doc_id = insert_document(
                file_name=uploaded.name,
                doc_date=doc_date,
                parse_tool=tool,
                source_type="upload",
            )
            for q in quotes:
                quote_id = insert_quote(
                    doc_id=doc_id,
                    supplier=q.get("supplier", ""),
                    supplier_biz=q.get("supplier_biz", ""),
                    subtotal=q.get("subtotal", 0),
                    vat=q.get("vat", 0),
                    total=q.get("total", 0),
                )
                for item in q.get("items", []):
                    insert_line_item(quote_id, item)

            st.success(f"✅ 저장 완료 (문서 #{doc_id})")
            st.balloons()


# ── 탭 2: 품목 검색 ──────────────────────────────────────────

with tab2:
    st.header("품목 가격 검색")

    query = st.text_input("품목명을 입력하세요", placeholder="예: 볼펜, 복합기, 의자, 컴퓨터")

    if query:
        results = search_similar_items(query, limit=30)

        if results:
            import pandas as pd
            df = pd.DataFrame(results)

            st.subheader(f"🔍 '{query}' 검색 결과 ({len(results)}건)")

            display_cols = ["raw_name", "unit_price", "quantity", "supply_amount", "supplier", "doc_date", "file_name"]
            display_cols = [c for c in display_cols if c in df.columns]
            col_names = {
                "raw_name": "품명",
                "unit_price": "단가",
                "quantity": "수량",
                "supply_amount": "공급가액",
                "supplier": "공급사",
                "doc_date": "견적일",
                "file_name": "파일명",
            }
            st.dataframe(
                df[display_cols].rename(columns=col_names),
                use_container_width=True,
            )

            # 단가 통계
            prices = [r["unit_price"] for r in results if r.get("unit_price")]
            if prices:
                col1, col2, col3 = st.columns(3)
                col1.metric("최저 단가", f"{min(prices):,}원")
                col2.metric("평균 단가", f"{sum(prices)//len(prices):,}원")
                col3.metric("최고 단가", f"{max(prices):,}원")
        else:
            st.warning(f"'{query}'에 해당하는 품목이 없습니다.")


# ── 탭 3: DB 현황 ──────────────────────────────────────────

with tab3:
    st.header("DB 현황")

    conn = get_conn()

    docs = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
    quotes_n = conn.execute("SELECT COUNT(*) as cnt FROM quotes").fetchone()["cnt"]
    items_n = conn.execute("SELECT COUNT(*) as cnt FROM line_items").fetchone()["cnt"]

    col1, col2, col3 = st.columns(3)
    col1.metric("📄 문서", f"{docs}개")
    col2.metric("🏢 견적", f"{quotes_n}개")
    col3.metric("📦 품목", f"{items_n}개")

    st.subheader("최근 등록 문서")
    recent_docs = conn.execute(
        "SELECT d.*, COUNT(q.id) as quote_count "
        "FROM documents d LEFT JOIN quotes q ON d.id = q.doc_id "
        "GROUP BY d.id ORDER BY d.parsed_at DESC LIMIT 20"
    ).fetchall()

    if recent_docs:
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in recent_docs])
        display_cols = ["id", "file_name", "doc_date", "parse_tool", "source_type", "quote_count"]
        display_cols = [c for c in display_cols if c in df.columns]
        col_names = {
            "id": "ID",
            "file_name": "파일명",
            "doc_date": "견적일",
            "parse_tool": "파싱도구",
            "source_type": "유형",
            "quote_count": "업체수",
        }
        st.dataframe(df[display_cols].rename(columns=col_names), use_container_width=True)

    conn.close()
