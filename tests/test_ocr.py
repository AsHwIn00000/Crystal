"""OCR provider tests with mocked HTTP."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


# ── UnlimitedOCRProvider tests ─────────────────────────────────────────────────
class TestUnlimitedOCRProvider:
    def test_is_available_returns_true_on_200(self):
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        provider = UnlimitedOCRProvider(base_url='http://mock:8000')
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            assert provider.is_available() is True

    def test_is_available_returns_false_on_connection_error(self):
        import requests
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        provider = UnlimitedOCRProvider(base_url='http://mock:8000')
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError):
            assert provider.is_available() is False

    def test_ocr_image_parses_response(self, tmp_path):
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        provider = UnlimitedOCRProvider(base_url='http://mock:8000')
        fake_response = {
            'model': 'baidu/Unlimited-OCR',
            'results': [{
                'name': 'test.png',
                'scenario': 'image',
                'page_count': 1,
                'text': 'Hello World',
                'error': None
            }]
        }
        img = tmp_path / 'test.png'
        img.write_bytes(b'fake')
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: fake_response
            )
            result = provider.ocr_image(img)
        assert result.error is None
        assert 'Hello World' in result.full_text

    def test_ocr_image_handles_http_error(self, tmp_path):
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        provider = UnlimitedOCRProvider(base_url='http://mock:8000')
        img = tmp_path / 'test.png'
        img.write_bytes(b'fake')
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=500,
                text='Internal Server Error'
            )
            result = provider.ocr_image(img)
        assert result.error is not None

    def test_ocr_image_handles_timeout(self, tmp_path):
        import requests
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        provider = UnlimitedOCRProvider(base_url='http://mock:8000')
        img = tmp_path / 'test.png'
        img.write_bytes(b'fake')
        with patch('requests.post', side_effect=requests.exceptions.Timeout):
            result = provider.ocr_image(img)
        assert result.error is not None

    def test_remove_det_strips_markers(self):
        from app.services.ocr.unlimited_ocr import remove_det
        raw = '<|det|>text [0,0,100,20]<|/det|>Hello World\n<|det|>image [0,20,100,80]<|/det|>chart'
        result = remove_det(raw)
        assert 'Hello World' in result
        assert 'chart' not in result  # image category stripped
        assert '<|det|>' not in result

    def test_remove_det_plain_text_unchanged(self):
        from app.services.ocr.unlimited_ocr import remove_det
        raw = 'This is plain text without markers.'
        result = remove_det(raw)
        assert result == raw


# ── TesseractOCRProvider tests ─────────────────────────────────────────────────
class TestTesseractOCRProvider:
    def test_is_available_when_tesseract_found(self):
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        provider = TesseractOCRProvider()
        with patch('shutil.which', return_value='/usr/bin/tesseract'):
            assert provider.is_available() is True

    def test_is_not_available_when_tesseract_missing(self):
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        provider = TesseractOCRProvider()
        with patch('shutil.which', return_value=None):
            assert provider.is_available() is False


# ── Provider factory tests ─────────────────────────────────────────────────────
class TestProviderFactory:
    def test_returns_unlimited_when_enabled_and_available(self):
        from app.services.ocr import provider_factory
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        with patch.dict('os.environ', {'UNLIMITED_OCR_ENABLED': 'true'}):
            with patch.object(UnlimitedOCRProvider, 'is_available', return_value=True):
                p = provider_factory.get_ocr_provider()
                assert isinstance(p, UnlimitedOCRProvider)

    def test_falls_back_to_tesseract_when_unlimited_unavailable(self):
        from app.services.ocr import provider_factory
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        with patch.dict('os.environ', {'UNLIMITED_OCR_ENABLED': 'true'}):
            with patch.object(UnlimitedOCRProvider, 'is_available', return_value=False):
                with patch.object(TesseractOCRProvider, 'is_available', return_value=True):
                    p = provider_factory.get_ocr_provider()
                    assert isinstance(p, TesseractOCRProvider)

    def test_returns_none_when_nothing_available(self):
        from app.services.ocr import provider_factory
        from app.services.ocr.unlimited_ocr import UnlimitedOCRProvider
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        with patch.dict('os.environ', {'UNLIMITED_OCR_ENABLED': 'false'}):
            with patch.object(TesseractOCRProvider, 'is_available', return_value=False):
                p = provider_factory.get_ocr_provider()
                assert p is None

    def test_returns_none_when_unlimited_disabled_and_tesseract_unavailable(self):
        from app.services.ocr import provider_factory
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        with patch.dict('os.environ', {'UNLIMITED_OCR_ENABLED': 'false'}):
            with patch.object(TesseractOCRProvider, 'is_available', return_value=False):
                p = provider_factory.get_ocr_provider()
                assert p is None
