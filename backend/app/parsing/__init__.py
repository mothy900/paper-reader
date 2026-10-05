"""PDF → 블록 구조 파서.

지금은 PyMuPDF 기반 휴리스틱 파서. 정확도가 부족해지면 같은 ParsedDocument를
반환하는 Docling/Marker 파서를 추가하고 parse_pdf에서 교체한다.
"""

from app.parsing.base import ParsedBlock, ParsedDocument
from app.parsing.pymupdf_parser import parse_pdf

__all__ = ["ParsedBlock", "ParsedDocument", "parse_pdf"]
