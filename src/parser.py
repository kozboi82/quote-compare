"""견적서 PDF 파싱 — 3단계 폴백 (docling → pdfplumber → OCR)."""

import os
import fitz  # PyMuPDF


def parse_pdf(path: str) -> tuple[str, str]:
    """PDF를 텍스트로 변환. (텍스트, 사용된_도구) 반환."""

    # 1차: docling
    text, tool = _try_docling(path)
    if text and len(text) > 100:
        return text, tool

    # 2차: pdfplumber
    text, tool = _try_pdfplumber(path)
    if text and len(text) > 100:
        return text, tool

    # 3차: OCR
    text, tool = _try_ocr(path)
    return text, tool


def _try_docling(path: str) -> tuple[str, str]:
    """docling으로 파싱 시도."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(path)
        md = result.document.export_to_markdown()
        if md and len(md.strip()) > 50:
            return md, "docling"
    except Exception as e:
        print(f"  docling 실패: {e}")
    return "", ""


def _try_pdfplumber(path: str) -> tuple[str, str]:
    """pdfplumber로 파싱 시도."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        if text and len(text.strip()) > 50:
            return text, "pdfplumber"
    except Exception as e:
        print(f"  pdfplumber 실패: {e}")
    return "", ""


def _try_ocr(path: str) -> tuple[str, str]:
    """OCR(ocrmac)로 파싱 시도."""
    try:
        from ocrmac.ocrmac import OCR

        doc = fitz.open(path)
        full_text = ""

        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_path = f"/tmp/ocr_temp_{os.getpid()}_{page_num}.png"
            pix.save(img_path)

            annotations = OCR(
                img_path, language_preference=["ko-KR", "en-US"]
            ).recognize()
            page_text = "\n".join([a[0] for a in annotations])
            full_text += page_text + "\n"

            os.remove(img_path)

        doc.close()

        if full_text and len(full_text.strip()) > 30:
            return full_text, "ocr"
    except Exception as e:
        print(f"  OCR 실패: {e}")
    return "", ""
