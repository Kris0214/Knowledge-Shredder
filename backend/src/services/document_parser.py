"""從 PDF / Word / TXT 擷取純文字。"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pdfplumber
from docx import Document

_SUPPORTED = {".pdf", ".docx", ".doc", ".txt"}

# 判斷擷取結果是否為亂碼：可讀字元(中英文數字標點)佔比須超過此閾值
_MIN_READABLE_RATIO = 0.5


def extract_text(file_bytes: bytes, file_name: str) -> str:
    """
    根據副檔名選擇解析方式，回傳純文字字串。
    不支援的格式或擷取結果為亂碼時會 raise ValueError。
    """
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
    """
    若擷取的文字太少或可讀字元比例過低（亂碼），raise ValueError 給上層處理。
    可讀字元定義：中文、英文、數字、常見標點符號。
    """
    if not text or len(text.strip()) < 50:
        raise ValueError(
            f"「{file_name}」擷取的文字內容過少（可能是掃描圖片 PDF 或空白文件）。"
            "請轉換為含有可選取文字的 PDF，或改用 Word / TXT 格式上傳。"
        )

    # 計算可讀字元比例
    readable = len(re.findall(
        r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef'   # 中文、全形
        r'A-Za-z0-9'                                    # 英數
        r'\s\.,!?;:()%\-\+\$\@\#]',                   # 常見標點
        text
    ))
    ratio = readable / len(text)

    if ratio < _MIN_READABLE_RATIO:
        raise ValueError(
            f"「{file_name}」的文字擷取結果疑似亂碼（可讀字元比例 {ratio:.0%}）。"
            "此 PDF 可能使用了非標準字型嵌入，請改用 Word (.docx) 或純文字 (.txt) 格式上傳。"
        )
