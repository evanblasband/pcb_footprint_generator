"""
Tests for prompts.py - extraction prompt generation.

These tests verify that the prompts are correctly formatted and contain
all necessary instructions for the Claude Vision API.
"""

import json
import pytest

from prompts import (
    EXTRACTION_SCHEMA,
    EXTRACTION_PROMPT,
    get_extraction_prompt,
    get_standard_package_prompt,
)


class TestExtractionSchema:
    """Tests for the extraction JSON schema."""

    def test_schema_is_valid_json_schema(self):
        """Test that schema is a valid JSON schema structure."""
        assert "type" in EXTRACTION_SCHEMA
        assert EXTRACTION_SCHEMA["type"] == "object"
        assert "properties" in EXTRACTION_SCHEMA
        assert "required" in EXTRACTION_SCHEMA

    def test_schema_has_required_fields(self):
        """Test that schema defines all required top-level fields."""
        required = EXTRACTION_SCHEMA["required"]
        assert "footprint_name" in required
        assert "units_detected" in required
        assert "pads" in required
        assert "outline" in required
        assert "pin1_location" in required
        assert "overall_confidence" in required
        assert "warnings" in required

    def test_pads_schema_structure(self):
        """Test that pads array schema is correctly defined."""
        pads_schema = EXTRACTION_SCHEMA["properties"]["pads"]
        assert pads_schema["type"] == "array"

        pad_item = pads_schema["items"]
        assert pad_item["type"] == "object"

        pad_props = pad_item["properties"]
        assert "designator" in pad_props
        assert "x" in pad_props
        assert "y" in pad_props
        assert "width" in pad_props
        assert "height" in pad_props
        assert "shape" in pad_props
        assert "pad_type" in pad_props
        assert "confidence" in pad_props

    def test_pad_shape_enum_values(self):
        """Test that pad shape enum contains expected values."""
        shape_schema = EXTRACTION_SCHEMA["properties"]["pads"]["items"]["properties"]["shape"]
        assert shape_schema["type"] == "string"
        assert "enum" in shape_schema

        shapes = shape_schema["enum"]
        assert "rectangular" in shapes
        assert "round" in shapes
        assert "oval" in shapes
        assert "rounded_rectangle" in shapes

    def test_pad_type_enum_values(self):
        """Test that pad type enum contains expected values."""
        type_schema = EXTRACTION_SCHEMA["properties"]["pads"]["items"]["properties"]["pad_type"]
        assert type_schema["type"] == "string"
        assert "enum" in type_schema

        types = type_schema["enum"]
        assert "smd" in types
        assert "th" in types

    def test_units_enum_values(self):
        """Test that units enum contains expected values."""
        units_schema = EXTRACTION_SCHEMA["properties"]["units_detected"]
        assert "enum" in units_schema

        units = units_schema["enum"]
        assert "mm" in units
        assert "mil" in units
        assert "inch" in units

    def test_confidence_range(self):
        """Test that confidence fields have correct range."""
        confidence_schema = EXTRACTION_SCHEMA["properties"]["pads"]["items"]["properties"]["confidence"]
        assert confidence_schema["type"] == "number"
        assert confidence_schema["minimum"] == 0
        assert confidence_schema["maximum"] == 1

    def test_outline_schema(self):
        """Test that outline schema is correctly defined."""
        outline = EXTRACTION_SCHEMA["properties"]["outline"]
        assert outline["type"] == "object"
        assert "width" in outline["properties"]
        assert "height" in outline["properties"]
        assert "confidence" in outline["properties"]

    def test_pin1_location_schema(self):
        """Test that pin1_location schema is correctly defined."""
        pin1 = EXTRACTION_SCHEMA["properties"]["pin1_location"]
        assert pin1["type"] == "object"
        assert "designator" in pin1["properties"]
        assert "indicator_type" in pin1["properties"]
        assert "confidence" in pin1["properties"]

    def test_pin1_indicator_types(self):
        """Test that pin1 indicator types include expected values."""
        indicator_schema = EXTRACTION_SCHEMA["properties"]["pin1_location"]["properties"]["indicator_type"]
        indicators = indicator_schema["enum"]

        assert "dot" in indicators
        assert "chamfer" in indicators
        assert "notch" in indicators
        assert "square_pad" in indicators
        assert "numbered" in indicators
        assert "unknown" in indicators


class TestExtractionPrompt:
    """Tests for the extraction prompt content."""

    def test_prompt_contains_coordinate_system(self):
        """Test that prompt explains coordinate system."""
        prompt = get_extraction_prompt()
        assert "Origin (0,0)" in prompt
        assert "component CENTER" in prompt.upper() or "component center" in prompt.lower()
        assert "+X" in prompt
        assert "+Y" in prompt

    def test_prompt_requests_json_output(self):
        """Test that prompt requests JSON output."""
        prompt = get_extraction_prompt()
        assert "JSON" in prompt
        assert "valid json" in prompt.lower()

    def test_prompt_contains_schema(self):
        """Test that prompt embeds the JSON schema."""
        prompt = get_extraction_prompt()
        # Schema should be embedded
        assert '"footprint_name"' in prompt
        assert '"pads"' in prompt
        assert '"confidence"' in prompt

    def test_prompt_explains_millimeters(self):
        """Test that prompt specifies millimeter units."""
        prompt = get_extraction_prompt()
        assert "millimeter" in prompt.lower() or "mm" in prompt

    def test_prompt_explains_confidence_scoring(self):
        """Test that prompt explains confidence scoring."""
        prompt = get_extraction_prompt()
        assert "confidence" in prompt.lower()
        assert "0" in prompt and "1" in prompt  # Range mentioned

    def test_prompt_explains_pin1_identification(self):
        """Test that prompt explains pin 1 identification methods."""
        prompt = get_extraction_prompt()
        assert "Pin 1" in prompt or "pin 1" in prompt
        assert "dot" in prompt.lower()
        assert "chamfer" in prompt.lower()

    def test_prompt_mentions_smd_and_th(self):
        """Test that prompt explains SMD and TH pad types."""
        prompt = get_extraction_prompt()
        assert "SMD" in prompt
        assert "TH" in prompt or "through-hole" in prompt.lower()


class TestStandardPackagePrompt:
    """Tests for the standard package detection prompt."""

    def test_prompt_lists_common_packages(self):
        """Test that prompt lists common package types."""
        prompt = get_standard_package_prompt()
        assert "SOIC" in prompt
        assert "QFN" in prompt
        assert "QFP" in prompt
        assert "BGA" in prompt
        assert "SOT-23" in prompt

    def test_prompt_requests_json_output(self):
        """Test that prompt requests JSON output."""
        prompt = get_standard_package_prompt()
        assert "JSON" in prompt

    def test_prompt_shows_example_response(self):
        """Test that prompt includes example responses."""
        prompt = get_standard_package_prompt()
        assert '"is_standard"' in prompt
        assert '"package_code"' in prompt
        assert '"confidence"' in prompt


class TestPromptFunctions:
    """Tests for prompt helper functions."""

    def test_get_extraction_prompt_returns_string(self):
        """Test that get_extraction_prompt returns a string."""
        result = get_extraction_prompt()
        assert isinstance(result, str)
        assert len(result) > 100  # Should be substantial

    def test_get_standard_package_prompt_returns_string(self):
        """Test that get_standard_package_prompt returns a string."""
        result = get_standard_package_prompt()
        assert isinstance(result, str)
        assert len(result) > 100  # Should be substantial

    def test_schema_is_json_serializable(self):
        """Test that schema can be serialized to JSON."""
        # This should not raise
        json_str = json.dumps(EXTRACTION_SCHEMA)
        assert len(json_str) > 0

        # And can be parsed back
        parsed = json.loads(json_str)
        assert parsed == EXTRACTION_SCHEMA
