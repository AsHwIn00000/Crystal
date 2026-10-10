import logging
import tempfile
from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParsedPage

logger = logging.getLogger(__name__)

SCAN_THRESHOLD = 50  # Characters below this → likely scanned page


class PdfParser(BaseParser):
    def parse(self, file_path: Path):
        import fitz  # PyMuPDF

        # Lazy-import OCR provider to avoid circular imports and startup cost
        from app.services.ocr.provider_factory import get_ocr_provider
        ocr_provider = None  # resolved lazily on first scanned page

        pages = []
        doc = fitz.open(str(file_path))
        try:
            for i, page in enumerate(doc):
                text = page.get_text('text').strip()

                if len(text) < SCAN_THRESHOLD:
                    # Likely a scanned page — try OCR
                    if ocr_provider is None:
                        ocr_provider = get_ocr_provider()  # resolve once

                    if ocr_provider is not None:
                        tmp_path = None
                        try:
                            pix = page.get_pixmap(dpi=200)
                            with tempfile.NamedTemporaryFile(
                                suffix='.png', delete=False
                            ) as tmp:
                                tmp_path = Path(tmp.name)
                            pix.save(str(tmp_path))
                            ocr_result = ocr_provider.ocr_image(tmp_path)
                            if ocr_result and not ocr_result.error and ocr_result.pages:
                                text = ocr_result.pages[0].text or text
                        except Exception as e:
                            logger.warning('OCR failed for page %d of %s: %s', i + 1, file_path.name, e)
                        finally:
                            if tmp_path and tmp_path.exists():
                                tmp_path.unlink()

                pages.append(ParsedPage(
                    page_number=i + 1,
                    text=text or '',
                    metadata={}
                ))
        finally:
            doc.close()
        return pages
