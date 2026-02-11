"""
Unit tests for Altium .PcbLib ASCII generator.

Tests cover:
- File structure (header, footer, sections)
- SMD pad generation
- Through-hole pad generation (round and slotted drills)
- Via generation
- Silkscreen outline generation
- Pin 1 indicator placement
- Coordinate and dimension formatting
- Complex footprints matching ground truth examples

Run with: pytest backend/tests/test_generator.py -v
"""

import pytest
import tempfile
import os

from models import (
    Footprint,
    Pad,
    PadType,
    PadShape,
    Drill,
    DrillType,
    Via,
    Outline,
)
from generator import (
    AltiumGenerator,
    generate_pcblib,
    write_pcblib,
    LAYER_TOP,
    LAYER_MULTI,
    LAYER_TOP_OVERLAY,
    SHAPE_ROUND,
    SHAPE_RECTANGULAR,
    SHAPE_ROUNDED_RECTANGLE,
)


# =============================================================================
# Fixtures - Reusable test data
# =============================================================================


@pytest.fixture
def minimal_footprint():
    """Create a minimal footprint with just a name."""
    return Footprint(name="TEST-MINIMAL")


@pytest.fixture
def smd_footprint():
    """Create a footprint with SMD pads (like SOIC-8)."""
    pads = [
        Pad(designator="1", x=-2.498, y=1.905, width=0.802, height=1.505,
            rotation=90, shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        Pad(designator="2", x=-2.498, y=0.635, width=0.802, height=1.505,
            rotation=90, shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
    ]
    return Footprint(name="SMD-TEST", pads=pads)


@pytest.fixture
def th_footprint():
    """Create a footprint with through-hole pads."""
    pads = [
        # Pin 1 with rounded rectangle (indicator)
        Pad(designator="1", x=-5.715, y=8.89, width=1.5, height=1.5,
            shape=PadShape.ROUNDED_RECTANGLE, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)),
        # Regular round pad
        Pad(designator="2", x=-4.445, y=6.35, width=1.5, height=1.5,
            shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)),
    ]
    return Footprint(name="TH-TEST", pads=pads)


@pytest.fixture
def slotted_hole_footprint():
    """Create a footprint with slotted holes (like USB connector shield)."""
    pads = [
        Pad(designator="SH1", x=-6.4, y=0, width=3.05, height=1.25,
            rotation=90, shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT)),
    ]
    return Footprint(name="SLOT-TEST", pads=pads)


@pytest.fixture
def footprint_with_vias():
    """Create a footprint with thermal vias."""
    vias = [
        Via(x=0.55, y=1.1, diameter=0.5, drill_diameter=0.2),
        Via(x=-0.55, y=1.1, diameter=0.5, drill_diameter=0.2),
        Via(x=0.55, y=0, diameter=0.5, drill_diameter=0.2),
        Via(x=-0.55, y=0, diameter=0.5, drill_diameter=0.2),
    ]
    return Footprint(name="VIA-TEST", vias=vias)


@pytest.fixture
def footprint_with_outline():
    """Create a footprint with silkscreen outline."""
    pads = [
        Pad(designator="1", x=-1.0, y=0, width=0.5, height=1.0),
    ]
    outline = Outline(width=5.0, height=4.0, line_width=0.15)
    return Footprint(name="OUTLINE-TEST", pads=pads, outline=outline)


# =============================================================================
# File Structure Tests
# =============================================================================


class TestFileStructure:
    """Tests for overall file structure."""

    def test_header_present(self, minimal_footprint):
        """Test that file header is present."""
        content = generate_pcblib(minimal_footprint)

        assert "PCB Library Document" in content
        assert "Version=1.0" in content
        assert "Encoding=UTF-8" in content

    def test_footer_present(self, minimal_footprint):
        """Test that file footer is present."""
        content = generate_pcblib(minimal_footprint)

        assert "End PCB Library" in content

    def test_component_section_present(self, minimal_footprint):
        """Test that component record is present."""
        content = generate_pcblib(minimal_footprint)

        assert "[Component]" in content
        assert "Name=TEST-MINIMAL" in content
        assert "RecordID=" in content

    def test_component_with_description(self):
        """Test component with description."""
        footprint = Footprint(
            name="WITH-DESC",
            description="Test component description"
        )
        content = generate_pcblib(footprint)

        assert "Description=Test component description" in content


# =============================================================================
# SMD Pad Tests
# =============================================================================


class TestSMDPads:
    """Tests for SMD pad generation."""

    def test_smd_pad_section(self, smd_footprint):
        """Test that pad section is generated."""
        content = generate_pcblib(smd_footprint)

        assert "[Pad]" in content

    def test_smd_pad_layer(self, smd_footprint):
        """Test that SMD pads use Top Layer."""
        content = generate_pcblib(smd_footprint)

        assert f"Layer={LAYER_TOP}" in content

    def test_smd_pad_designator(self, smd_footprint):
        """Test pad designators are included."""
        content = generate_pcblib(smd_footprint)

        assert "Designator=1" in content
        assert "Designator=2" in content

    def test_smd_pad_coordinates(self, smd_footprint):
        """Test pad coordinates are formatted correctly."""
        content = generate_pcblib(smd_footprint)

        # Check for coordinate with mm suffix
        assert "X=-2.498mm" in content
        assert "Y=1.905mm" in content

    def test_smd_pad_dimensions(self, smd_footprint):
        """Test pad dimensions are formatted correctly."""
        content = generate_pcblib(smd_footprint)

        assert "XSize=0.802mm" in content
        assert "YSize=1.505mm" in content

    def test_smd_pad_rotation(self, smd_footprint):
        """Test pad rotation is included."""
        content = generate_pcblib(smd_footprint)

        assert "Rotation=90.000" in content

    def test_smd_pad_shape(self, smd_footprint):
        """Test pad shape is included."""
        content = generate_pcblib(smd_footprint)

        assert f"Shape={SHAPE_RECTANGULAR}" in content

    def test_smd_no_drill(self, smd_footprint):
        """Test that SMD pads don't have drill info."""
        content = generate_pcblib(smd_footprint)

        # Count occurrences - should only be in through-hole pads
        # SMD pads should not have HoleSize
        lines = content.split("\n")
        pad_sections = []
        current_section = []

        for line in lines:
            if line == "[Pad]":
                if current_section:
                    pad_sections.append(current_section)
                current_section = [line]
            elif current_section:
                current_section.append(line)
                if line == "":
                    pad_sections.append(current_section)
                    current_section = []

        # For SMD pads, verify no HoleSize in each section
        for section in pad_sections:
            section_text = "\n".join(section)
            if f"Layer={LAYER_TOP}" in section_text:
                assert "HoleSize" not in section_text


# =============================================================================
# Through-Hole Pad Tests
# =============================================================================


class TestThroughHolePads:
    """Tests for through-hole pad generation."""

    def test_th_pad_layer(self, th_footprint):
        """Test that TH pads use MultiLayer."""
        content = generate_pcblib(th_footprint)

        assert f"Layer={LAYER_MULTI}" in content

    def test_th_pad_drill_size(self, th_footprint):
        """Test drill hole size is included."""
        content = generate_pcblib(th_footprint)

        assert "HoleSize=0.900mm" in content

    def test_th_pad_drill_type_round(self, th_footprint):
        """Test round drill type is specified."""
        content = generate_pcblib(th_footprint)

        assert "DrillType=Round" in content

    def test_th_pad_rounded_rectangle_shape(self, th_footprint):
        """Test rounded rectangle shape for Pin 1."""
        content = generate_pcblib(th_footprint)

        assert f"Shape={SHAPE_ROUNDED_RECTANGLE}" in content

    def test_th_pad_round_shape(self, th_footprint):
        """Test round shape for regular pads."""
        content = generate_pcblib(th_footprint)

        assert f"Shape={SHAPE_ROUND}" in content


# =============================================================================
# Slotted Hole Tests
# =============================================================================


class TestSlottedHoles:
    """Tests for slotted hole generation."""

    def test_slot_drill_type(self, slotted_hole_footprint):
        """Test slotted drill type is specified."""
        content = generate_pcblib(slotted_hole_footprint)

        assert "DrillType=Slot" in content

    def test_slot_length(self, slotted_hole_footprint):
        """Test slot length is included."""
        content = generate_pcblib(slotted_hole_footprint)

        assert "SlotLength=2.450mm" in content

    def test_slot_diameter(self, slotted_hole_footprint):
        """Test slot diameter (width) is included."""
        content = generate_pcblib(slotted_hole_footprint)

        assert "HoleSize=0.650mm" in content


# =============================================================================
# Via Tests
# =============================================================================


class TestVias:
    """Tests for via generation."""

    def test_via_section(self, footprint_with_vias):
        """Test that via section is generated."""
        content = generate_pcblib(footprint_with_vias)

        assert "[Via]" in content

    def test_via_layer(self, footprint_with_vias):
        """Test that vias use MultiLayer."""
        content = generate_pcblib(footprint_with_vias)

        # Count via sections with MultiLayer
        assert content.count("[Via]") == 4

    def test_via_coordinates(self, footprint_with_vias):
        """Test via coordinates."""
        content = generate_pcblib(footprint_with_vias)

        assert "X=0.550mm" in content
        assert "X=-0.550mm" in content

    def test_via_diameter(self, footprint_with_vias):
        """Test via pad diameter."""
        content = generate_pcblib(footprint_with_vias)

        assert "Diameter=0.500mm" in content

    def test_via_drill_diameter(self, footprint_with_vias):
        """Test via drill diameter."""
        content = generate_pcblib(footprint_with_vias)

        # Via hole size
        assert "HoleSize=0.200mm" in content


# =============================================================================
# Outline/Silkscreen Tests
# =============================================================================


class TestOutline:
    """Tests for silkscreen outline generation."""

    def test_track_section(self, footprint_with_outline):
        """Test that track sections are generated for outline."""
        content = generate_pcblib(footprint_with_outline)

        assert "[Track]" in content

    def test_outline_layer(self, footprint_with_outline):
        """Test that outline uses Top Overlay layer."""
        content = generate_pcblib(footprint_with_outline)

        assert f"Layer={LAYER_TOP_OVERLAY}" in content

    def test_outline_four_tracks(self, footprint_with_outline):
        """Test that four tracks are generated (rectangle)."""
        content = generate_pcblib(footprint_with_outline)

        # Should have 4 track segments for rectangular outline
        assert content.count("[Track]") == 4

    def test_outline_coordinates(self, footprint_with_outline):
        """Test outline corner coordinates."""
        content = generate_pcblib(footprint_with_outline)

        # Half width = 2.5, half height = 2.0
        # Corners should be at ±2.5, ±2.0
        assert "X1=-2.500mm" in content or "X2=-2.500mm" in content
        assert "X1=2.500mm" in content or "X2=2.500mm" in content
        assert "Y1=-2.000mm" in content or "Y2=-2.000mm" in content
        assert "Y1=2.000mm" in content or "Y2=2.000mm" in content

    def test_outline_line_width(self, footprint_with_outline):
        """Test outline line width."""
        content = generate_pcblib(footprint_with_outline)

        assert "Width=0.150mm" in content


# =============================================================================
# Pin 1 Indicator Tests
# =============================================================================


class TestPin1Indicator:
    """Tests for Pin 1 indicator generation."""

    def test_pin1_arc_present(self, footprint_with_outline):
        """Test that Pin 1 indicator arc is generated."""
        content = generate_pcblib(footprint_with_outline)

        assert "[Arc]" in content

    def test_pin1_arc_layer(self, footprint_with_outline):
        """Test Pin 1 indicator is on Top Overlay."""
        content = generate_pcblib(footprint_with_outline)

        # Find the arc section and verify layer
        arc_index = content.find("[Arc]")
        arc_section = content[arc_index:arc_index + 200]
        assert LAYER_TOP_OVERLAY in arc_section

    def test_pin1_arc_is_circle(self, footprint_with_outline):
        """Test Pin 1 indicator is a full circle (0-360 degrees)."""
        content = generate_pcblib(footprint_with_outline)

        assert "StartAngle=0" in content
        assert "EndAngle=360" in content

    def test_no_pin1_without_pads(self, minimal_footprint):
        """Test no Pin 1 indicator when no pads exist."""
        # Add outline but no pads
        minimal_footprint.outline = Outline(width=5.0, height=4.0)
        content = generate_pcblib(minimal_footprint)

        # No arc should be generated
        assert "[Arc]" not in content


# =============================================================================
# Formatting Tests
# =============================================================================


class TestFormatting:
    """Tests for coordinate and dimension formatting."""

    def test_coordinate_precision(self):
        """Test coordinate precision (3 decimal places)."""
        footprint = Footprint(
            name="PRECISION",
            pads=[Pad(designator="1", x=1.23456789, y=-9.87654321,
                      width=0.5, height=0.5)]
        )
        content = generate_pcblib(footprint)

        # Should be rounded to 3 decimal places
        assert "X=1.235mm" in content
        assert "Y=-9.877mm" in content

    def test_negative_coordinates(self):
        """Test negative coordinate formatting."""
        footprint = Footprint(
            name="NEGATIVE",
            pads=[Pad(designator="1", x=-5.715, y=-8.89,
                      width=1.0, height=1.0)]
        )
        content = generate_pcblib(footprint)

        assert "X=-5.715mm" in content
        assert "Y=-8.890mm" in content

    def test_zero_rotation(self):
        """Test zero rotation formatting."""
        footprint = Footprint(
            name="ZERO-ROT",
            pads=[Pad(designator="1", x=0, y=0, width=1.0, height=1.0,
                      rotation=0)]
        )
        content = generate_pcblib(footprint)

        assert "Rotation=0.000" in content


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_generate_pcblib_function(self, smd_footprint):
        """Test generate_pcblib convenience function."""
        content = generate_pcblib(smd_footprint)

        assert isinstance(content, str)
        assert "PCB Library Document" in content
        assert "Name=SMD-TEST" in content

    def test_write_pcblib_function(self, smd_footprint):
        """Test write_pcblib convenience function."""
        with tempfile.NamedTemporaryFile(suffix=".PcbLib", delete=False) as f:
            filepath = f.name

        try:
            write_pcblib(smd_footprint, filepath)

            # Verify file was created and contains content
            assert os.path.exists(filepath)

            with open(filepath, "r") as f:
                content = f.read()

            assert "PCB Library Document" in content
            assert "Name=SMD-TEST" in content
        finally:
            # Cleanup
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_generator_write_to_file(self, smd_footprint):
        """Test AltiumGenerator.write_to_file method."""
        with tempfile.NamedTemporaryFile(suffix=".PcbLib", delete=False) as f:
            filepath = f.name

        try:
            generator = AltiumGenerator(smd_footprint)
            generator.write_to_file(filepath)

            assert os.path.exists(filepath)
            assert os.path.getsize(filepath) > 0
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


# =============================================================================
# Complex Scenario Tests - Ground Truth Matching
# =============================================================================


class TestGroundTruthScenarios:
    """Tests for complex scenarios matching ground truth examples."""

    def test_so8ep_structure(self):
        """
        Test SO-8EP footprint generation.

        Ground truth: 8 SMD signal pads + 1 thermal pad + 6 vias.
        """
        # Create signal pads (pins 1-8)
        signal_pads = []
        y_positions = [1.905, 0.635, -0.635, -1.905]

        # Left side (pins 1-4)
        for i, y in enumerate(y_positions):
            signal_pads.append(Pad(
                designator=str(i + 1),
                x=-2.498,
                y=y,
                width=0.802,
                height=1.505,
                rotation=90,
                shape=PadShape.RECTANGULAR,
                pad_type=PadType.SMD
            ))

        # Right side (pins 5-8)
        for i, y in enumerate(reversed(y_positions)):
            signal_pads.append(Pad(
                designator=str(i + 5),
                x=2.497,
                y=y,
                width=0.802,
                height=1.505,
                rotation=90,
                shape=PadShape.RECTANGULAR,
                pad_type=PadType.SMD
            ))

        # Thermal pad (pin 9)
        thermal_pad = Pad(
            designator="9",
            x=0,
            y=0,
            width=2.613,
            height=3.502,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD
        )

        # Vias (2x3 grid)
        vias = []
        for x in [-0.55, 0.55]:
            for y in [-1.1, 0, 1.1]:
                vias.append(Via(x=x, y=y, diameter=0.5, drill_diameter=0.2))

        footprint = Footprint(
            name="SO-8EP",
            description="SOIC-8 with exposed thermal pad",
            pads=signal_pads + [thermal_pad],
            vias=vias,
            outline=Outline(width=5.0, height=4.0)
        )

        content = generate_pcblib(footprint)

        # Verify structure
        assert content.count("[Pad]") == 9  # 8 signal + 1 thermal
        assert content.count("[Via]") == 6
        assert content.count("[Track]") == 4  # Outline
        assert "[Arc]" in content  # Pin 1 indicator

        # Verify all designators
        for i in range(1, 10):
            assert f"Designator={i}" in content

        # Verify thermal pad dimensions
        assert "XSize=2.613mm" in content
        assert "YSize=3.502mm" in content

    def test_rj45_connector_structure(self):
        """
        Test RJ45 connector footprint generation.

        Ground truth: 22 through-hole pads with various sizes,
        Pin 1 has rounded rectangle shape.
        """
        pads = [
            # Pin 1 - rounded rectangle
            Pad(designator="1", x=-5.715, y=8.89, width=1.5, height=1.5,
                shape=PadShape.ROUNDED_RECTANGLE, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.9)),
            # Regular pins
            Pad(designator="2", x=-4.445, y=6.35, width=1.5, height=1.5,
                shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.9)),
            # Shield/mounting with larger holes
            Pad(designator="Un1", x=-5.715, y=0, width=3.2, height=3.2,
                shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=3.2)),
            Pad(designator="Un2", x=5.715, y=0, width=3.2, height=3.2,
                shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=3.2)),
        ]

        footprint = Footprint(name="LPJG0926HENL", pads=pads)
        content = generate_pcblib(footprint)

        # Verify through-hole characteristics
        assert f"Layer={LAYER_MULTI}" in content
        assert "DrillType=Round" in content

        # Verify different hole sizes
        assert "HoleSize=0.900mm" in content  # Signal pins
        assert "HoleSize=3.200mm" in content  # Shield pins

        # Verify Pin 1 shape
        assert f"Shape={SHAPE_ROUNDED_RECTANGLE}" in content

    def test_usb_connector_with_slots(self):
        """
        Test USB connector with slotted holes.

        Ground truth: Shield pins use Drilled Slot type.
        """
        pads = [
            # Signal pin
            Pad(designator="1", x=-3.5, y=-0.57, width=1.25, height=1.25,
                shape=PadShape.RECTANGULAR, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.75)),
            # Slotted shield pins
            Pad(designator="SH1", x=-6.4, y=0, width=3.05, height=1.25,
                rotation=90, shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT)),
            Pad(designator="SH2", x=6.4, y=0, width=3.05, height=1.25,
                rotation=90, shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT)),
        ]

        footprint = Footprint(name="GSB3115381RF1HR", pads=pads)
        content = generate_pcblib(footprint)

        # Verify slotted holes
        assert "DrillType=Slot" in content
        assert "SlotLength=2.450mm" in content
        assert content.count("DrillType=Slot") == 2  # Two shield pins

        # Verify signal pin has round drill
        assert "DrillType=Round" in content


# =============================================================================
# Record ID Tests
# =============================================================================


class TestRecordIDs:
    """Tests for unique record IDs."""

    def test_unique_record_ids(self, smd_footprint):
        """Test that each record gets a unique ID."""
        content = generate_pcblib(smd_footprint)

        # Extract all RecordID values
        record_ids = []
        for line in content.split("\n"):
            if line.startswith("RecordID="):
                record_id = int(line.split("=")[1])
                record_ids.append(record_id)

        # All IDs should be unique
        assert len(record_ids) == len(set(record_ids))

        # IDs should be sequential starting from 1
        assert record_ids == list(range(1, len(record_ids) + 1))
