import logging
from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParsedPage

logger = logging.getLogger(__name__)


class ImageParser(BaseParser):
    MAX_DIMENSION = 10000  # Maximum pixel dimension

    def parse(self, file_path: Path):
        from PIL import Image
        # Validate image with Pillow
        try:
            with Image.open(str(file_path)) as img:
                img.verify()
        except Exception as e:
            raise ValueError(f'Invalid image file: {e}')

        # Re-open (verify() closes the file)
        with Image.open(str(file_path)) as img:
            width, height = img.size
            if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                raise ValueError(
                    f'Image dimensions {width}x{height} exceed maximum '
                    f'{self.MAX_DIMENSION}x{self.MAX_DIMENSION}'
                )

        from app.services.ocr.provider_factory import get_ocr_provider
        provider = get_ocr_provider()

        if provider is None:
            logger.warning('No OCR provider available — cannot extract text from image: %s', file_path.name)
            return [ParsedPage(page_number=1, text='', metadata={'ocr_available': False})]

        try:
            result = provider.ocr_image(Path(file_path))
            if result.error:
                logger.error('OCR error for %s: %s', file_path.name, result.error)
                return [ParsedPage(page_number=1, text='', metadata={'ocr_error': result.error})]
            return [
                ParsedPage(
                    page_number=p.page_number,
                    text=p.text or '',
                    metadata={'ocr_provider': provider.name}
                )
                for p in result.pages
            ] or [ParsedPage(page_number=1, text='', metadata={'ocr_provider': provider.name})]
        except Exception as e:
            logger.error('OCR extraction failed for %s: %s', file_path.name, e)
            return [ParsedPage(page_number=1, text='', metadata={'ocr_error': str(e)})]
