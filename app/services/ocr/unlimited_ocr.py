import re
import os
import logging
from pathlib import Path
from typing import Optional

import requests

from .base import OCRProvider, OCRResult, OCRPage

logger = logging.getLogger(__name__)

# Regex to clean <|det|>...<|/det|> markers from model output
DET_RE = re.compile(r'<\|det\|>([^<\s]+)(?:\s*\[[^\]]*\])?\s*<\|/det\|>(.*)', re.DOTALL)


def remove_det(raw: str) -> str:
    """Strip <|det|> detection markers from Unlimited-OCR output."""
    blocks = []
    cur = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        m = DET_RE.match(line)
        if m:
            category = m.group(1).strip()
            content = m.group(2).strip()
            if category == 'image':
                # Skip image-only blocks — not text
                continue
            if cur is not None:
                blocks.append(cur)
            cur = [content] if content else []
            continue
        if cur is None:
            cur = []
        cur.append(line)
    if cur is not None:
        blocks.append(cur)
    return '\n\n'.join('\n'.join(b) for b in blocks).strip()


class UnlimitedOCRProvider(OCRProvider):
    """OCR provider using self-hosted Baidu Unlimited-OCR via vLLM/FastAPI endpoint.

    The endpoint is expected to be the FastAPI wrapper from
    github.com/maxoyed/Unlimited-OCR-FastAPI, which exposes:
      GET  /health          — health check
      POST /ocr/image       — multipart file upload, returns JSON
      POST /ocr/pdf         — multipart file upload, returns JSON

    Response shape: {"model": "baidu/Unlimited-OCR",
                     "results": [{"name": str, "scenario": str,
                                  "page_count": int, "text": str,
                                  "error": str|null}]}

    Credentials (from .env):
      UNLIMITED_OCR_URL       base URL of the endpoint (default: http://localhost:8000)
      UNLIMITED_OCR_API_KEY   optional Bearer token (default: empty)
      UNLIMITED_OCR_TIMEOUT   request timeout in seconds (default: 120)
      UNLIMITED_OCR_MAX_FILE_MB  max file size in MB (default: 50)
    """

    def __init__(self, base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout: Optional[int] = None,
                 max_file_mb: Optional[int] = None):
        self.base_url = (base_url or os.getenv('UNLIMITED_OCR_URL', 'http://localhost:8000')).rstrip('/')
        self._api_key = api_key if api_key is not None else os.getenv('UNLIMITED_OCR_API_KEY', '')
        self.timeout = int(timeout or os.getenv('UNLIMITED_OCR_TIMEOUT', '120'))
        self.max_file_mb = int(max_file_mb or os.getenv('UNLIMITED_OCR_MAX_FILE_MB', '50'))

    @property
    def name(self) -> str:
        return 'unlimited_ocr'

    def _headers(self) -> dict:
        headers = {}
        if self._api_key:
            headers['Authorization'] = f'Bearer {self._api_key}'
        return headers

    def is_available(self) -> bool:
        """Check if the Unlimited-OCR endpoint is reachable."""
        try:
            resp = requests.get(
                f'{self.base_url}/health',
                headers=self._headers(),
                timeout=5
            )
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _check_file_size(self, file_path: Path) -> None:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_mb:
            raise ValueError(
                f'File {file_path.name} ({size_mb:.1f} MB) exceeds '
                f'maximum allowed size of {self.max_file_mb} MB'
            )

    def _post_file(self, endpoint: str, file_path: Path) -> OCRResult:
        """POST a file to the given endpoint and parse the OCR response."""
        self._check_file_size(file_path)
        url = f'{self.base_url}{endpoint}'
        try:
            with open(file_path, 'rb') as f:
                resp = requests.post(
                    url,
                    files={'file': (file_path.name, f, 'application/octet-stream')},
                    headers=self._headers(),
                    timeout=self.timeout
                )
        except requests.exceptions.Timeout:
            logger.error('Unlimited-OCR request timed out for %s', file_path.name)
            return OCRResult(
                provider=self.name,
                pages=[],
                total_pages=0,
                error=f'Request timed out after {self.timeout}s'
            )
        except requests.exceptions.RequestException as e:
            logger.error('Unlimited-OCR connection error for %s: %s', file_path.name, e)
            return OCRResult(
                provider=self.name,
                pages=[],
                total_pages=0,
                error=f'Connection error: {e}'
            )

        if resp.status_code != 200:
            logger.error(
                'Unlimited-OCR returned HTTP %d for %s',
                resp.status_code, file_path.name
            )
            return OCRResult(
                provider=self.name,
                pages=[],
                total_pages=0,
                error=f'HTTP {resp.status_code}: {resp.text[:200]}'
            )

        try:
            data = resp.json()
        except ValueError as e:
            logger.error('Unlimited-OCR returned invalid JSON for %s: %s', file_path.name, e)
            return OCRResult(
                provider=self.name,
                pages=[],
                total_pages=0,
                error='Invalid JSON response from OCR endpoint'
            )

        results = data.get('results', [])
        if not results:
            return OCRResult(
                provider=self.name,
                pages=[],
                total_pages=0,
                error='No results in OCR response'
            )

        result = results[0]
        if result.get('error'):
            return OCRResult(
                provider=self.name,
                pages=[],
                total_pages=0,
                error=result['error']
            )

        raw_text = result.get('text', '') or ''
        page_count = result.get('page_count', 1) or 1
        clean_text = remove_det(raw_text)

        # Try to split by page markers; fall back to single page
        page_texts = self._split_pages(clean_text, page_count)
        pages = [
            OCRPage(
                page_number=i + 1,
                text=text,
                raw_response=raw_text if i == 0 else ''
            )
            for i, text in enumerate(page_texts)
        ]
        logger.info(
            'Unlimited-OCR processed %s: %d page(s)',
            file_path.name, len(pages)
        )
        return OCRResult(
            provider=self.name,
            pages=pages,
            total_pages=len(pages)
        )

    def _split_pages(self, text: str, expected_pages: int):
        """Split text by page markers if present, else return as single page."""
        import re as re_mod
        # Common page break markers from PDF processing
        parts = re_mod.split(r'(?m)^---\s*Page\s*\d+\s*---$', text)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]
        # Try form-feed character
        parts = text.split('\x0c')
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]
        return [text]

    def ocr_image(self, file_path: Path) -> OCRResult:
        """OCR a single image file."""
        return self._post_file('/ocr/image', Path(file_path))

    def ocr_pdf(self, file_path: Path) -> OCRResult:
        """OCR a PDF file."""
        return self._post_file('/ocr/pdf', Path(file_path))
