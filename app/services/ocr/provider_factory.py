import os
import logging

from .unlimited_ocr import UnlimitedOCRProvider
from .tesseract_ocr import TesseractOCRProvider

logger = logging.getLogger(__name__)


def get_ocr_provider():
    """Return the best available OCR provider.

    Priority:
    1. Unlimited-OCR (if UNLIMITED_OCR_ENABLED=true and endpoint is reachable)
    2. Tesseract (if installed)
    3. None (caller must handle missing OCR gracefully)
    """
    enabled = os.getenv('UNLIMITED_OCR_ENABLED', 'false').lower() == 'true'
    if enabled:
        provider = UnlimitedOCRProvider()
        if provider.is_available():
            logger.info('Using Unlimited-OCR provider at %s', provider.base_url)
            return provider
        else:
            logger.warning(
                'Unlimited-OCR enabled but endpoint %s is not reachable. '
                'Falling back to Tesseract.', provider.base_url
            )

    tess = TesseractOCRProvider()
    if tess.is_available():
        logger.info('Using Tesseract OCR provider')
        return tess

    logger.warning('No OCR provider available. Image/scanned PDF text extraction disabled.')
    return None
