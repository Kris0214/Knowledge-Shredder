from __future__ import annotations

import io
import re
from pathlib import Path

import pdfplumber
from docx import Document

_SUPPORTED = {".pdf", ".docx", ".doc", ".txt"}

_MIN_READABLE_RATIO = 0.5


def extract_text(file_bytes: bytes, file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()

    if suffix not in _SUPPORTED:
        raise ValueError(
            f"不支援的檔案格式：{suffix}。支援格式：{', '.join(_SUPPORTED)}"
        )

    if suffix == ".pdf":
        text = _parse_pdf(file_bytes)
    elif suffix in (".docx", ".doc"):
        text = _parse_docx(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="replace").strip()

    _validate_text(text, file_name)
    return text


def _parse_pdf(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages).strip()


def _parse_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _validate_text(text: str, file_name: str) -> None:
    if not text or len(text.strip()) < 50:
        raise ValueError(
            f"「{file_name}」擷取的文字內容過少（可能是掃描圖片 PDF 或空白文件）。"
            "請轉換為含有可選取文字的 PDF，或改用 Word / TXT 格式上傳。"
        )

    readable = len(re.findall(
        r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef'   
        r'A-Za-z0-9'                                    
        r'\s\.,!?;:()%\-\+\$\@\#]',                   
        text
    ))
    ratio = readable / len(text)

    if ratio < _MIN_READABLE_RATIO:
        raise ValueError(
            f"「{file_name}」的文字擷取結果疑似亂碼（可讀字元比例 {ratio:.0%}）。"
            "此 PDF 可能使用了非標準字型嵌入，請改用 Word (.docx) 或純文字 (.txt) 格式上傳。"
        )
