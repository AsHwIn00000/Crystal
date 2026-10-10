import shutil
import logging
import tempfile
from pathlib import Path

from .base import OCRProvider, OCRResult, OCRPage

logger = logging.getLogger(__name__)


class TesseractOCRProvider(OCRProvider):
    """Local OCR fallback using Tesseract (via pytesseract) and PyMuPDF."""

    @property
    def name(self) -> str:
        return 'tesseract'

    def is_available(self) -> bool:
        return shutil.which('tesseract') is not None

    def ocr_image(self, file_path: Path) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
            with Image.open(str(file_path)) as img:
                text = pytesseract.image_to_string(img)
            page = OCRPage(page_number=1, text=text or '', raw_response=text or '')
            return OCRResult(provider=self.name, pages=[page], total_pages=1)
        except Exception as e:
            logger.error('Tesseract OCR failed for %s: %s', file_path.name, e)
            return OCRResult(
                provider=self.name,
                pages=[OCRPage(page_number=1, text='', raw_response='', error=str(e))],
                total_pages=1,
                error=str(e)
            )

    def ocr_pdf(self, file_path: Path) -> OCRResult:
        try:
            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image

            pages = []
            doc = fitz.open(str(file_path))
            try:
                for i, page in enumerate(doc):
                    tmp_path = None
                    try:
                        pix = page.get_pixmap(dpi=200)
                        with tempfile.NamedTemporaryFile(
                            suffix='.png', delete=False
                        ) as tmp:
                            tmp_path = Path(tmp.name)
                        pix.save(str(tmp_path))
                        with Image.open(str(tmp_path)) as img:
                            text = pytesseract.image_to_string(img)
                        pages.append(OCRPage(
                            page_number=i + 1,
                            text=text or '',
                            raw_response=text or ''
                        ))
                    except Exception as e:
                        logger.warning('Tesseract failed on PDF page %d: %s', i + 1, e)
                        pages.append(OCRPage(
                            page_number=i + 1, text='',
                            raw_response='', error=str(e)
                        ))
                    finally:
                        if tmp_path and tmp_path.exists():
                            tmp_path.unlink()
            finally:
                doc.close()

            return OCRResult(
                provider=self.name,
                pages=pages,
                total_pages=len(pages)
            )
        except Exception as e:
            logger.error('Tesseract PDF OCR failed for %s: %s', file_path.name, e)
            return OCRResult(
                provider=self.name, pages=[], total_pages=0, error=str(e)
            )
