"""
Unit tests for Pydantic models.

Tests cover:
- Model instantiation with valid data
- Validation of required fields
- Validation of field constraints (min/max, enums)
- Default values
- Computed properties (e.g., Footprint.get_bounds)
- Serialization/deserialization

Run with: pytest backend/tests/test_models.py -v
"""

import pytest
from pydantic import ValidationError

from models import (
    Drill,
    DrillType,
    Pad,
    PadShape,
    PadType,
    Via,
    Outline,
    Footprint,
    ExtractionResult,
    ConfirmRequest,
    Job,
    JobStatus,
)


# =============================================================================
# Drill Model Tests
# =============================================================================


class TestDrill:
    """Tests for the Drill model."""

    def test_round_drill_minimal(self):
        """Test creating a simple round drill hole."""
        drill = Drill(diameter=0.9)

        assert drill.diameter == 0.9
        assert drill.slot_length is None
        assert drill.drill_type == DrillType.ROUND

    def test_slotted_drill(self):
        """Test creating a slotted drill hole."""
        drill = Drill(
            diameter=0.65,
            slot_length=2.45,
            drill_type=DrillType.SLOT
        )

        assert drill.diameter == 0.65
        assert drill.slot_length == 2.45
        assert drill.drill_type == DrillType.SLOT

    def test_drill_requires_diameter(self):
        """Test that diameter is required."""
        with pytest.raises(ValidationError) as exc_info:
            Drill()

        # Check that the error is about the missing diameter field
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("diameter",) for e in errors)

    def test_drill_serialization(self):
        """Test that drill serializes to dict correctly."""
        drill = Drill(diameter=1.0, slot_length=2.0, drill_type=DrillType.SLOT)
        data = drill.model_dump()

        assert data["diameter"] == 1.0
        assert data["slot_length"] == 2.0
        assert data["drill_type"] == "slot"


# =============================================================================
# Pad Model Tests
# =============================================================================


class TestPad:
    """Tests for the Pad model."""

    def test_smd_pad_minimal(self):
        """Test creating a minimal SMD pad."""
        pad = Pad(
            designator="1",
            x=-2.498,
            y=1.905,
            width=0.802,
            height=1.505
        )

        assert pad.designator == "1"
        assert pad.x == -2.498
        assert pad.y == 1.905
        assert pad.width == 0.802
        assert pad.height == 1.505
        # Check defaults
        assert pad.rotation == 0.0
        assert pad.shape == PadShape.RECTANGULAR
        assert pad.pad_type == PadType.SMD
        assert pad.drill is None
        assert pad.confidence == 1.0

    def test_through_hole_pad_with_drill(self):
        """Test creating a through-hole pad with drill specification."""
        pad = Pad(
            designator="1",
            x=-5.715,
            y=8.89,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)
        )

        assert pad.pad_type == PadType.THROUGH_HOLE
        assert pad.shape == PadShape.ROUND
        assert pad.drill is not None
        assert pad.drill.diameter == 0.9

    def test_pad_with_rotation(self):
        """Test pad with 90-degree rotation."""
        pad = Pad(
            designator="5",
            x=2.497,
            y=-1.905,
            width=0.802,
            height=1.505,
            rotation=90.0
        )

        assert pad.rotation == 90.0

    def test_pad_with_low_confidence(self):
        """Test pad with low extraction confidence."""
        pad = Pad(
            designator="1",
            x=0,
            y=0,
            width=1.0,
            height=1.0,
            confidence=0.45
        )

        assert pad.confidence == 0.45

    def test_pad_confidence_validation(self):
        """Test that confidence must be between 0 and 1."""
        # Test value above 1
        with pytest.raises(ValidationError):
            Pad(
                designator="1",
                x=0, y=0, width=1.0, height=1.0,
                confidence=1.5
            )

        # Test negative value
        with pytest.raises(ValidationError):
            Pad(
                designator="1",
                x=0, y=0, width=1.0, height=1.0,
                confidence=-0.1
            )

    def test_pad_all_shapes(self):
        """Test all valid pad shapes."""
        for shape in PadShape:
            pad = Pad(
                designator="1",
                x=0, y=0, width=1.0, height=1.0,
                shape=shape
            )
            assert pad.shape == shape

    def test_pad_requires_core_fields(self):
        """Test that required fields raise validation errors when missing."""
        with pytest.raises(ValidationError) as exc_info:
            Pad()

        errors = exc_info.value.errors()
        required_fields = {"designator", "x", "y", "width", "height"}
        error_fields = {e["loc"][0] for e in errors}

        assert required_fields.issubset(error_fields)

    def test_rounded_rectangle_for_pin1(self):
        """Test rounded rectangle shape typically used for Pin 1."""
        pad = Pad(
            designator="1",
            x=-5.715,
            y=8.89,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUNDED_RECTANGLE,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)
        )

        assert pad.shape == PadShape.ROUNDED_RECTANGLE


# =============================================================================
# Via Model Tests
# =============================================================================


class TestVia:
    """Tests for the Via model."""

    def test_via_creation(self):
        """Test creating a thermal via."""
        via = Via(
            x=0.55,
            y=1.1,
            diameter=0.5,
            drill_diameter=0.2
        )

        assert via.x == 0.55
        assert via.y == 1.1
        assert via.diameter == 0.5
        assert via.drill_diameter == 0.2

    def test_via_requires_all_fields(self):
        """Test that all via fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            Via()

        errors = exc_info.value.errors()
        required_fields = {"x", "y", "diameter", "drill_diameter"}
        error_fields = {e["loc"][0] for e in errors}

        assert required_fields.issubset(error_fields)


# =============================================================================
# Outline Model Tests
# =============================================================================


class TestOutline:
    """Tests for the Outline model."""

    def test_outline_creation(self):
        """Test creating a component outline."""
        outline = Outline(width=5.0, height=4.0)

        assert outline.width == 5.0
        assert outline.height == 4.0
        assert outline.line_width == 0.15  # default

    def test_outline_custom_line_width(self):
        """Test outline with custom line width."""
        outline = Outline(width=5.0, height=4.0, line_width=0.2)

        assert outline.line_width == 0.2


# =============================================================================
# Footprint Model Tests
# =============================================================================


class TestFootprint:
    """Tests for the Footprint model."""

    def test_footprint_minimal(self):
        """Test creating a footprint with just a name."""
        footprint = Footprint(name="TEST-FOOTPRINT")

        assert footprint.name == "TEST-FOOTPRINT"
        assert footprint.description == ""
        assert footprint.pads == []
        assert footprint.vias == []
        assert footprint.outline is None

    def test_footprint_with_pads(self):
        """Test footprint with pad list."""
        pads = [
            Pad(designator="1", x=-1.0, y=0, width=0.5, height=1.0),
            Pad(designator="2", x=1.0, y=0, width=0.5, height=1.0),
        ]
        footprint = Footprint(name="2-PAD", pads=pads)

        assert len(footprint.pads) == 2
        assert footprint.pads[0].designator == "1"
        assert footprint.pads[1].designator == "2"

    def test_get_bounds_empty(self):
        """Test get_bounds returns zeros for empty footprint."""
        footprint = Footprint(name="EMPTY")
        bounds = footprint.get_bounds()

        assert bounds == (0, 0, 0, 0)

    def test_get_bounds_single_pad(self):
        """Test get_bounds with single pad at origin."""
        footprint = Footprint(
            name="SINGLE",
            pads=[Pad(designator="1", x=0, y=0, width=2.0, height=1.0)]
        )
        min_x, min_y, max_x, max_y = footprint.get_bounds()

        # Pad at (0,0) with width=2, height=1
        # Should extend from -1 to +1 in X, -0.5 to +0.5 in Y
        assert min_x == -1.0
        assert max_x == 1.0
        assert min_y == -0.5
        assert max_y == 0.5

    def test_get_bounds_multiple_pads(self):
        """Test get_bounds with multiple pads."""
        pads = [
            Pad(designator="1", x=-5.0, y=5.0, width=1.0, height=1.0),
            Pad(designator="2", x=5.0, y=-5.0, width=1.0, height=1.0),
        ]
        footprint = Footprint(name="MULTI", pads=pads)
        min_x, min_y, max_x, max_y = footprint.get_bounds()

        # Pad 1: center (-5, 5), extends to (-5.5, 4.5) to (-4.5, 5.5)
        # Pad 2: center (5, -5), extends to (4.5, -5.5) to (5.5, -4.5)
        assert min_x == -5.5
        assert max_x == 5.5
        assert min_y == -5.5
        assert max_y == 5.5

    def test_footprint_with_vias(self):
        """Test footprint with thermal vias."""
        vias = [
            Via(x=0.55, y=1.1, diameter=0.5, drill_diameter=0.2),
            Via(x=-0.55, y=1.1, diameter=0.5, drill_diameter=0.2),
        ]
        footprint = Footprint(name="WITH-VIAS", vias=vias)

        assert len(footprint.vias) == 2

    def test_footprint_with_outline(self):
        """Test footprint with outline."""
        footprint = Footprint(
            name="WITH-OUTLINE",
            outline=Outline(width=5.0, height=4.0)
        )

        assert footprint.outline is not None
        assert footprint.outline.width == 5.0


# =============================================================================
# ExtractionResult Model Tests
# =============================================================================


class TestExtractionResult:
    """Tests for the ExtractionResult model."""

    def test_extraction_result_defaults(self):
        """Test extraction result with all defaults."""
        result = ExtractionResult()

        assert result.package_type == "custom"
        assert result.standard_detected is None
        assert result.units == "mm"
        assert result.pads == []
        assert result.vias == []
        assert result.pin1_detected is False
        assert result.pin1_index is None
        assert result.outline is None
        assert result.overall_confidence == 0.0
        assert result.warnings == []

    def test_extraction_result_with_standard_package(self):
        """Test extraction result when standard package detected."""
        result = ExtractionResult(
            package_type="QFN",
            standard_detected="QFN-48",
            overall_confidence=0.95
        )

        assert result.package_type == "QFN"
        assert result.standard_detected == "QFN-48"

    def test_extraction_result_with_warnings(self):
        """Test extraction result with warnings."""
        result = ExtractionResult(
            warnings=[
                "Units ambiguous - defaulted to mm",
                "Pin 1 marker not clearly visible"
            ]
        )

        assert len(result.warnings) == 2

    def test_extraction_result_confidence_validation(self):
        """Test that overall_confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ExtractionResult(overall_confidence=1.5)


# =============================================================================
# ConfirmRequest Model Tests
# =============================================================================


class TestConfirmRequest:
    """Tests for the ConfirmRequest model."""

    def test_confirm_request_empty(self):
        """Test confirm request with no pin1 selection."""
        request = ConfirmRequest()

        assert request.pin1_designator is None

    def test_confirm_request_with_pin1(self):
        """Test confirm request with pin1 designator."""
        request = ConfirmRequest(pin1_designator="1")

        assert request.pin1_designator == "1"


# =============================================================================
# Job Model Tests
# =============================================================================


class TestJob:
    """Tests for the Job model."""

    def test_job_creation(self):
        """Test creating a new job."""
        job = Job(job_id="test-uuid-123")

        assert job.job_id == "test-uuid-123"
        assert job.status == JobStatus.PENDING
        assert job.filename == ""
        assert job.extraction_result is None
        assert job.confirmed_footprint is None
        assert job.error_message is None

    def test_job_status_progression(self):
        """Test job can have different statuses."""
        for status in JobStatus:
            job = Job(job_id="test", status=status)
            assert job.status == status

    def test_job_with_extraction_result(self):
        """Test job with extraction result populated."""
        result = ExtractionResult(
            pads=[Pad(designator="1", x=0, y=0, width=1, height=1)],
            overall_confidence=0.85
        )
        job = Job(
            job_id="test",
            status=JobStatus.EXTRACTED,
            extraction_result=result
        )

        assert job.extraction_result is not None
        assert len(job.extraction_result.pads) == 1

    def test_job_with_error(self):
        """Test job in error state."""
        job = Job(
            job_id="test",
            status=JobStatus.ERROR,
            error_message="Failed to extract dimensions from image"
        )

        assert job.status == JobStatus.ERROR
        assert "Failed to extract" in job.error_message


# =============================================================================
# Integration Tests - Complex Scenarios
# =============================================================================


class TestComplexScenarios:
    """Integration tests combining multiple models."""

    def test_so8ep_footprint_structure(self):
        """
        Test creating a SO-8EP footprint structure matching ground truth.

        SO-8EP has:
        - 8 SMD pads (pins 1-8)
        - 1 thermal/exposed pad (pin 9)
        - 6 thermal vias
        """
        # Create the 8 signal pads
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

        all_pads = signal_pads + [thermal_pad]

        # Create thermal vias (2x3 grid)
        vias = []
        for x in [-0.55, 0.55]:
            for y in [-1.1, 0, 1.1]:
                vias.append(Via(
                    x=x, y=y,
                    diameter=0.5,
                    drill_diameter=0.2
                ))

        # Create footprint
        footprint = Footprint(
            name="SO-8EP",
            description="SOIC-8 with exposed thermal pad",
            pads=all_pads,
            vias=vias,
            outline=Outline(width=5.0, height=4.0)
        )

        # Verify structure
        assert len(footprint.pads) == 9
        assert len(footprint.vias) == 6
        assert footprint.outline is not None

        # Verify bounds include thermal pad
        min_x, min_y, max_x, max_y = footprint.get_bounds()
        assert min_x < -2.0  # Signal pads extend left
        assert max_x > 2.0   # Signal pads extend right

    def test_through_hole_connector_structure(self):
        """
        Test creating a through-hole connector footprint.

        Similar to RJ45 with mixed pad sizes and shapes.
        """
        pads = [
            # Signal pins - round TH
            Pad(
                designator="1",
                x=-5.715,
                y=8.89,
                width=1.5,
                height=1.5,
                shape=PadShape.ROUNDED_RECTANGLE,  # Pin 1 indicator
                pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.9)
            ),
            Pad(
                designator="2",
                x=-4.445,
                y=6.35,
                width=1.5,
                height=1.5,
                shape=PadShape.ROUND,
                pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=0.9)
            ),
            # Shield/mounting pins - larger
            Pad(
                designator="SH1",
                x=-5.715,
                y=0,
                width=3.2,
                height=3.2,
                shape=PadShape.ROUND,
                pad_type=PadType.THROUGH_HOLE,
                drill=Drill(diameter=3.2)
            ),
        ]

        footprint = Footprint(
            name="CONNECTOR-TH",
            pads=pads
        )

        # Verify Pin 1 has rounded rectangle shape
        pin1 = footprint.pads[0]
        assert pin1.designator == "1"
        assert pin1.shape == PadShape.ROUNDED_RECTANGLE

        # Verify shield pin has larger drill
        shield = footprint.pads[2]
        assert shield.drill.diameter == 3.2

    def test_extraction_to_footprint_workflow(self):
        """Test the workflow from extraction result to confirmed footprint."""
        # Simulate extraction result
        extraction = ExtractionResult(
            package_type="custom",
            pads=[
                Pad(designator="1", x=-1.27, y=0, width=0.6, height=1.0, confidence=0.92),
                Pad(designator="2", x=1.27, y=0, width=0.6, height=1.0, confidence=0.88),
            ],
            pin1_detected=True,
            pin1_index=0,
            overall_confidence=0.90
        )

        # Create job with extraction
        job = Job(
            job_id="workflow-test",
            status=JobStatus.EXTRACTED,
            filename="test_datasheet.png",
            extraction_result=extraction
        )

        # Simulate user confirmation - convert to footprint
        confirmed = Footprint(
            name="CUSTOM-2PIN",
            pads=extraction.pads,
            outline=Outline(width=4.0, height=2.0)
        )

        # Update job
        job.status = JobStatus.CONFIRMED
        job.confirmed_footprint = confirmed

        assert job.status == JobStatus.CONFIRMED
        assert job.confirmed_footprint.name == "CUSTOM-2PIN"
        assert len(job.confirmed_footprint.pads) == 2
