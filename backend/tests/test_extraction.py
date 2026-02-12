"""
Tests for extraction.py - Claude Vision API integration.

These tests use mocking to avoid actual API calls during unit testing.
Integration tests with real API calls are marked with @pytest.mark.integration
and require ANTHROPIC_API_KEY environment variable.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from extraction import (
    FootprintExtractor,
    ExtractionResponse,
    StandardPackageResponse,
    extract_footprint,
    estimate_cost,
    DEFAULT_MODEL,
    MODELS,
    SUPPORTED_MEDIA_TYPES,
)
from models import PadShape, PadType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_anthropic_response():
    """Create a mock Claude API response with valid extraction data."""
    return {
        "footprint_name": "TEST-FOOTPRINT",
        "units_detected": "mm",
        "pads": [
            {
                "designator": "1",
                "x": -1.27,
                "y": 0,
                "width": 0.6,
                "height": 1.0,
                "shape": "rectangular",
                "pad_type": "smd",
                "rotation": 0,
                "confidence": 0.95
            },
            {
                "designator": "2",
                "x": 1.27,
                "y": 0,
                "width": 0.6,
                "height": 1.0,
                "shape": "rectangular",
                "pad_type": "smd",
                "rotation": 0,
                "confidence": 0.92
            }
        ],
        "outline": {
            "width": 4.0,
            "height": 2.0,
            "confidence": 0.88
        },
        "pin1_location": {
            "designator": "1",
            "indicator_type": "numbered",
            "confidence": 0.9
        },
        "overall_confidence": 0.91,
        "warnings": [],
        "standard_package_detected": None
    }


@pytest.fixture
def mock_th_response():
    """Create a mock response with through-hole pads."""
    return {
        "footprint_name": "TH-TEST",
        "units_detected": "mm",
        "pads": [
            {
                "designator": "1",
                "x": 0,
                "y": 0,
                "width": 1.5,
                "height": 1.5,
                "shape": "round",
                "pad_type": "th",
                "drill_diameter": 0.9,
                "confidence": 0.9
            }
        ],
        "outline": {"width": 3.0, "height": 3.0, "confidence": 0.8},
        "pin1_location": {"designator": "1", "indicator_type": "numbered", "confidence": 0.9},
        "overall_confidence": 0.85,
        "warnings": ["Drill diameter estimated from pad size"],
        "standard_package_detected": None
    }


@pytest.fixture
def mock_client():
    """Create a mock Anthropic client."""
    with patch('extraction.anthropic.Anthropic') as mock:
        yield mock


# =============================================================================
# Configuration Tests
# =============================================================================

class TestConfiguration:
    """Tests for extractor configuration."""

    def test_default_model_is_haiku(self):
        """Test that default model is Haiku."""
        assert "haiku" in DEFAULT_MODEL.lower()

    def test_models_dict_contains_expected_models(self):
        """Test that MODELS dict has expected entries."""
        assert "haiku" in MODELS
        assert "sonnet" in MODELS
        assert "opus" in MODELS

    def test_supported_media_types(self):
        """Test that common image types are supported."""
        assert "image/png" in SUPPORTED_MEDIA_TYPES
        assert "image/jpeg" in SUPPORTED_MEDIA_TYPES
        assert "image/gif" in SUPPORTED_MEDIA_TYPES
        assert "image/webp" in SUPPORTED_MEDIA_TYPES


class TestExtractorInit:
    """Tests for FootprintExtractor initialization."""

    def test_init_requires_api_key(self):
        """Test that init fails without API key."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="API key required"):
                FootprintExtractor()

    def test_init_accepts_api_key_parameter(self, mock_client):
        """Test that API key can be passed as parameter."""
        extractor = FootprintExtractor(api_key="test-key")
        assert extractor is not None

    def test_init_uses_env_var(self, mock_client):
        """Test that API key is read from environment."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key'}):
            extractor = FootprintExtractor()
            assert extractor is not None

    def test_init_resolves_model_alias(self, mock_client):
        """Test that model aliases are resolved."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor(model="haiku")
            assert "haiku" in extractor.model.lower()

    def test_init_accepts_full_model_name(self, mock_client):
        """Test that full model names are accepted."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor(model="claude-haiku-4-5-20251001")
            assert extractor.model == "claude-haiku-4-5-20251001"


# =============================================================================
# Image Extraction Tests
# =============================================================================

class TestImageExtraction:
    """Tests for image-based extraction."""

    def test_extract_from_nonexistent_file(self, mock_client):
        """Test extraction from non-existent file returns error."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            result = extractor.extract_from_image("/nonexistent/path.png")

            assert not result.success
            assert "not found" in result.error.lower()

    def test_extract_from_unsupported_format(self, mock_client, tmp_path):
        """Test extraction from unsupported format returns error."""
        # Create a test file with unsupported extension
        test_file = tmp_path / "test.bmp"
        test_file.write_bytes(b"fake image data")

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            result = extractor.extract_from_image(test_file)

            assert not result.success
            assert "unsupported" in result.error.lower()

    def test_extract_from_bytes_validates_media_type(self, mock_client):
        """Test that invalid media type is rejected."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            result = extractor.extract_from_bytes(b"fake", "image/bmp")

            assert not result.success
            assert "unsupported media type" in result.error.lower()


# =============================================================================
# Response Parsing Tests
# =============================================================================

class TestResponseParsing:
    """Tests for parsing Claude's response."""

    def test_parse_direct_json(self, mock_client):
        """Test parsing direct JSON response."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            result = extractor._parse_json_response('{"test": "value"}')

            assert result == {"test": "value"}

    def test_parse_json_in_code_block(self, mock_client):
        """Test parsing JSON wrapped in markdown code block."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            response = '```json\n{"test": "value"}\n```'
            result = extractor._parse_json_response(response)

            assert result == {"test": "value"}

    def test_parse_invalid_json_returns_none(self, mock_client):
        """Test that invalid JSON returns None."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            result = extractor._parse_json_response('not json at all')

            assert result is None


# =============================================================================
# Model Conversion Tests
# =============================================================================

class TestModelConversion:
    """Tests for converting API response to models."""

    def test_response_to_footprint_creates_pads(self, mock_client, mock_anthropic_response):
        """Test that response is converted to Footprint with correct pads."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            footprint, result = extractor._response_to_footprint(mock_anthropic_response)

            assert footprint.name == "TEST-FOOTPRINT"
            assert len(footprint.pads) == 2
            assert footprint.pads[0].designator == "1"
            assert footprint.pads[0].x == -1.27
            assert footprint.pads[0].shape == PadShape.RECTANGULAR
            assert footprint.pads[0].pad_type == PadType.SMD

    def test_response_to_footprint_creates_outline(self, mock_client, mock_anthropic_response):
        """Test that outline is created correctly."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            footprint, result = extractor._response_to_footprint(mock_anthropic_response)

            assert footprint.outline.width == 4.0
            assert footprint.outline.height == 2.0

    def test_response_to_footprint_handles_th_pads(self, mock_client, mock_th_response):
        """Test that through-hole pads with drills are handled."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            footprint, result = extractor._response_to_footprint(mock_th_response)

            assert footprint.pads[0].pad_type == PadType.THROUGH_HOLE
            assert footprint.pads[0].drill is not None
            assert footprint.pads[0].drill.diameter == 0.9

    def test_response_to_footprint_includes_confidence(self, mock_client, mock_anthropic_response):
        """Test that extraction result includes confidence scores."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            footprint, result = extractor._response_to_footprint(mock_anthropic_response)

            assert result.overall_confidence == 0.91

    def test_response_to_footprint_includes_pin1(self, mock_client, mock_anthropic_response):
        """Test that pin 1 detection is included."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            extractor = FootprintExtractor()
            footprint, result = extractor._response_to_footprint(mock_anthropic_response)

            assert result.pin1_detected is True
            assert result.pin1_index == 0  # First pad is pin 1


# =============================================================================
# Cost Estimation Tests
# =============================================================================

class TestCostEstimation:
    """Tests for cost estimation."""

    def test_estimate_cost_haiku(self):
        """Test cost estimation for Haiku."""
        cost = estimate_cost(10000, 1000, "haiku")
        # 10000 * 0.25/1M + 1000 * 1.25/1M = 0.0025 + 0.00125 = 0.00375
        assert cost == pytest.approx(0.00375, rel=0.01)

    def test_estimate_cost_sonnet(self):
        """Test cost estimation for Sonnet."""
        cost = estimate_cost(10000, 1000, "sonnet")
        # 10000 * 3/1M + 1000 * 15/1M = 0.03 + 0.015 = 0.045
        assert cost == pytest.approx(0.045, rel=0.01)

    def test_estimate_cost_opus(self):
        """Test cost estimation for Opus."""
        cost = estimate_cost(10000, 1000, "opus")
        # 10000 * 15/1M + 1000 * 75/1M = 0.15 + 0.075 = 0.225
        assert cost == pytest.approx(0.225, rel=0.01)


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_extract_footprint_creates_extractor(self, mock_client, tmp_path):
        """Test that extract_footprint creates an extractor."""
        # This will fail because file doesn't exist, but tests the path
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"fake")

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch.object(FootprintExtractor, 'extract_from_image') as mock_extract:
                mock_extract.return_value = ExtractionResponse(success=True)
                result = extract_footprint(test_file)
                mock_extract.assert_called_once()


# =============================================================================
# Integration Tests (require API key)
# =============================================================================

@pytest.mark.integration
class TestIntegration:
    """
    Integration tests that make real API calls.

    Run with: pytest -m integration

    Requires ANTHROPIC_API_KEY environment variable.
    """

    @pytest.fixture
    def api_key(self):
        """Get API key from environment."""
        import os
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            pytest.skip("ANTHROPIC_API_KEY not set")
        return key

    def test_real_extraction(self, api_key):
        """Test real extraction with example image."""
        # Path to example image
        example_path = Path(__file__).parent.parent.parent / "example_datasheets" / "so-8ep_crop.png"

        if not example_path.exists():
            pytest.skip(f"Example image not found: {example_path}")

        extractor = FootprintExtractor(api_key=api_key, model="haiku")
        result = extractor.extract_from_image(example_path)

        # Basic validation
        assert result.success, f"Extraction failed: {result.error}"
        assert result.footprint is not None
        assert len(result.footprint.pads) > 0
        assert result.extraction_result.overall_confidence > 0

        # Print results for manual inspection
        print(f"\nExtracted footprint: {result.footprint.name}")
        print(f"Pads: {len(result.footprint.pads)}")
        print(f"Confidence: {result.extraction_result.overall_confidence}")
        print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
        print(f"Est. cost: ${estimate_cost(result.input_tokens, result.output_tokens):.4f}")
