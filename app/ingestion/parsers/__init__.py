"""Parser factory — returns the appropriate parser for a given file type."""
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.pptx_parser import PptxParser
from app.ingestion.parsers.txt_parser import TxtParser
from app.ingestion.parsers.image_parser import ImageParser
from app.ingestion.parsers.excel_parser import ExcelParser


_PARSERS = {
    'pdf': PdfParser,
    'docx': DocxParser,
    'doc': DocxParser,
    'pptx': PptxParser,
    'txt': TxtParser,
    'png': ImageParser,
    'jpg': ImageParser,
    'jpeg': ImageParser,
    'xlsx': ExcelParser,
    'xls': ExcelParser,
}


def parser_for(file_type: str):
    """Return an instantiated parser for the given file type extension."""
    cls = _PARSERS.get(file_type.lower())
    if cls is None:
        raise ValueError(f'No parser available for file type: {file_type}')
    return cls()
