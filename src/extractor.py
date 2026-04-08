"""LLM으로 파싱된 텍스트에서 품목 구조화 추출."""

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

MODEL = os.environ.get("EXTRACT_MODEL", "meta-llama/llama-4-maverick")

SYSTEM_PROMPT = """견적서 텍스트에서 아래 JSON 형식으로 품목 정보를 추출하세요.

출력 형식:
{
  "doc_date": "YYYY-MM-DD",
  "quotes": [
    {
      "supplier": "공급사명",
      "supplier_biz": "사업자번호",
      "subtotal": 공급가액(숫자),
      "vat": 부가세(숫자),
      "total": 합계(숫자),
      "items": [
        {
          "item_type": "product 또는 labor 또는 service",
          "raw_name": "원본 품명 그대로",
          "normalized_name": "정규화된 품명 (예: 볼펜, 복합기, 의자)",
          "brand": "브랜드 (없으면 빈 문자열)",
          "model": "모델명 (없으면 빈 문자열)",
          "spec": "규격/사양 (없으면 빈 문자열)",
          "unit": "단위 (개, 대, 박스 등)",
          "quantity": 수량(숫자),
          "unit_price": 단가(숫자),
          "supply_amount": 공급가액(숫자)
        }
      ]
    }
  ]
}

규칙:
1. 금액은 숫자만 (쉼표, 원, ₩ 제거)
2. 한 PDF에 여러 업체 견적이 있으면 quotes 배열에 각각 추가
3. 빈 행(수량 0, 금액 0)은 제외
4. 인건비/공임은 item_type을 "labor"로
5. normalized_name은 브랜드/모델 제외한 일반 품명 (예: "라미 로고 206 볼펜" → "볼펜")
6. 반드시 유효한 JSON만 출력. 설명 없이 JSON만.
"""


def extract_items(parsed_text: str) -> dict:
    """파싱된 텍스트에서 품목 정보를 LLM으로 추출."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": parsed_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=30,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)
