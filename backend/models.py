"""
Pydantic models for PCB footprint data.

This module defines all data structures used throughout the FootprintAI application:
- Pad definitions (SMD and through-hole)
- Via definitions (for thermal pad patterns)
- Footprint containers
- Extraction results from AI vision
- Job tracking for async processing

Coordinate System:
    - Origin at component center
    - +X points right
    - +Y points up
    - All dimensions in millimeters
    - Rotations in degrees (0° = horizontal)

Reference: Altium Designer coordinate conventions
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums - Define valid values for categorical fields
# =============================================================================


class PadShape(str, Enum):
    """
    Pad shape types supported by Altium Designer.

    These map directly to Altium's internal shape representations:
    - ROUND: Circular pads (common for through-hole)
    - RECTANGULAR: Standard SMD pads
    - ROUNDED_RECTANGLE: Often used for Pin 1 identification
    - OVAL: Elongated circular pads
    """

    ROUND = "round"
    RECTANGULAR = "rectangular"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    OVAL = "oval"


class PadType(str, Enum):
    """
    Pad mounting type.

    - SMD: Surface Mount Device - pad on Top Layer only, no drill hole
    - THROUGH_HOLE: Pad spans all layers (MultiLayer) with drill hole
    """

    SMD = "smd"
    THROUGH_HOLE = "th"


class DrillType(str, Enum):
    """
    Drill hole geometry for through-hole pads.

    - ROUND: Standard circular drill hole
    - SLOT: Elongated/slotted hole (requires slot_length parameter)
    """

    ROUND = "round"
    SLOT = "slot"


class JobStatus(str, Enum):
    """
    Job processing status for async workflow.

    Workflow progression:
    PENDING -> EXTRACTING -> EXTRACTED -> CONFIRMED -> GENERATED
                    |
                    v
                  ERROR (can occur at any stage)
    """

    PENDING = "pending"  # Job created, waiting to start
    EXTRACTING = "extracting"  # AI extraction in progress
    EXTRACTED = "extracted"  # Extraction complete, awaiting user confirmation
    CONFIRMED = "confirmed"  # User confirmed dimensions
    GENERATED = "generated"  # .PcbLib file generated successfully
    ERROR = "error"  # Processing failed


# =============================================================================
# Core Data Models - Building blocks for footprint definitions
# =============================================================================


class Drill(BaseModel):
    """
    Drill hole specification for through-hole pads.

    Attributes:
        diameter: Drill hole diameter in mm. For round holes, this is the
            only dimension needed. For slots, this is the slot width.
        slot_length: Length of slot in mm. Only used when drill_type is SLOT.
            The total slot dimensions are (diameter x slot_length).
        drill_type: Geometry of the drill hole (round or slot).

    Example:
        # Standard 0.9mm round drill
        Drill(diameter=0.9)

        # 0.65mm x 2.45mm slotted hole
        Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT)
    """

    diameter: float = Field(..., description="Drill diameter in mm")
    slot_length: Optional[float] = Field(
        None, description="Slot length in mm (for slotted holes)"
    )
    drill_type: DrillType = Field(default=DrillType.ROUND)


class Pad(BaseModel):
    """
    Individual pad definition.

    Represents a single copper pad in the footprint. Position is specified
    as the pad center relative to the component origin.

    Attributes:
        designator: Pin name/number (e.g., "1", "A1", "GND", "SH1" for shield).
        x: X position of pad center in mm from origin.
        y: Y position of pad center in mm from origin.
        width: Pad width (X dimension before rotation) in mm.
        height: Pad height (Y dimension before rotation) in mm.
        rotation: Pad rotation in degrees. 0° = horizontal, 90° = vertical.
        shape: Geometric shape of the pad.
        pad_type: SMD or through-hole.
        drill: Drill specification (required for through-hole pads).
        confidence: AI extraction confidence score (0.0-1.0).

    Example:
        # SMD rectangular pad for SOIC pin
        Pad(
            designator="1",
            x=-2.498,
            y=1.905,
            width=0.802,
            height=1.505,
            rotation=90,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD
        )

        # Through-hole round pad
        Pad(
            designator="1",
            x=-5.715,
            y=8.89,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)
        )
    """

    designator: str = Field(..., description="Pin designator (e.g., '1', 'A1', 'GND')")
    x: float = Field(..., description="X position in mm from origin")
    y: float = Field(..., description="Y position in mm from origin")
    width: float = Field(..., description="Pad width (X size) in mm")
    height: float = Field(..., description="Pad height (Y size) in mm")
    rotation: float = Field(default=0.0, description="Rotation in degrees")
    shape: PadShape = Field(default=PadShape.RECTANGULAR)
    pad_type: PadType = Field(default=PadType.SMD)
    drill: Optional[Drill] = Field(None, description="Drill specification for TH pads")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )


class Via(BaseModel):
    """
    Via definition for thermal pad patterns.

    Vias are used in exposed pad footprints (like QFN, QFP) to provide
    thermal connection to inner layers.

    Attributes:
        x: X position of via center in mm from origin.
        y: Y position of via center in mm from origin.
        diameter: Via pad diameter in mm (copper annular ring).
        drill_diameter: Via drill hole diameter in mm.

    Example:
        # Typical thermal via
        Via(x=0.55, y=1.1, diameter=0.5, drill_diameter=0.2)
    """

    x: float = Field(..., description="X position in mm")
    y: float = Field(..., description="Y position in mm")
    diameter: float = Field(..., description="Via pad diameter in mm")
    drill_diameter: float = Field(..., description="Via drill diameter in mm")


class Outline(BaseModel):
    """
    Component outline for silkscreen layer.

    Defines a rectangular outline on the TopOverlay (silkscreen) layer
    representing the component body boundary.

    Attributes:
        width: Total outline width in mm.
        height: Total outline height in mm.
        line_width: Silkscreen line thickness in mm (default 0.15mm).
    """

    width: float = Field(..., description="Outline width in mm")
    height: float = Field(..., description="Outline height in mm")
    line_width: float = Field(default=0.15, description="Silkscreen line width in mm")


# =============================================================================
# Container Models - Aggregate structures
# =============================================================================


class Footprint(BaseModel):
    """
    Complete footprint definition.

    Contains all elements needed to generate an Altium .PcbLib file:
    pads, vias, and silkscreen outline.

    Attributes:
        name: Component/footprint name (used as filename and in library).
        description: Optional description text.
        pads: List of all pads in the footprint.
        vias: List of vias (typically for thermal pad patterns).
        outline: Silkscreen outline dimensions.

    Example:
        footprint = Footprint(
            name="SO-8EP",
            description="SOIC-8 with exposed thermal pad",
            pads=[...],
            vias=[...],
            outline=Outline(width=5.0, height=4.0)
        )
    """

    name: str = Field(..., description="Footprint/component name")
    description: str = Field(default="", description="Component description")
    pads: list[Pad] = Field(default_factory=list)
    vias: list[Via] = Field(default_factory=list)
    outline: Optional[Outline] = Field(None)

    def get_bounds(self) -> tuple[float, float, float, float]:
        """
        Calculate bounding box of all pads.

        Returns:
            Tuple of (min_x, min_y, max_x, max_y) representing the
            bounding box that encloses all pad extents.

        Note:
            Returns (0, 0, 0, 0) if no pads are defined.
        """
        if not self.pads:
            return (0, 0, 0, 0)

        # Calculate extent of each pad considering its size
        min_x = min(p.x - p.width / 2 for p in self.pads)
        max_x = max(p.x + p.width / 2 for p in self.pads)
        min_y = min(p.y - p.height / 2 for p in self.pads)
        max_y = max(p.y + p.height / 2 for p in self.pads)

        return (min_x, min_y, max_x, max_y)


# =============================================================================
# API Models - Request/Response structures for API endpoints
# =============================================================================


class ExtractionResult(BaseModel):
    """
    Result from AI vision extraction.

    Contains all extracted footprint data plus metadata about the
    extraction quality and any detected issues.

    Attributes:
        package_type: Detected package type ("custom" if non-standard).
        standard_detected: IPC-7351 package code if detected (e.g., "QFN-48").
        units: Units used in extraction (always normalized to "mm").
        pads: List of extracted pad definitions.
        vias: List of extracted vias (for thermal pads).
        pin1_detected: Whether Pin 1 was confidently identified.
        pin1_index: Index of Pin 1 in pads list (if detected).
        outline: Extracted component outline.
        overall_confidence: Aggregate confidence score (0.0-1.0).
        warnings: List of extraction warnings/issues for user review.
    """

    package_type: str = Field(default="custom", description="Package type or 'custom'")
    standard_detected: Optional[str] = Field(
        None, description="IPC-7351 standard if detected"
    )
    units: str = Field(default="mm")
    pads: list[Pad] = Field(default_factory=list)
    vias: list[Via] = Field(default_factory=list)
    pin1_detected: bool = Field(default=False)
    pin1_index: Optional[int] = Field(None, description="Index of Pin 1 in pads list")
    outline: Optional[Outline] = Field(None)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    """
    Request body for confirming extraction results.

    Sent by user after reviewing extracted dimensions to confirm
    accuracy and specify Pin 1 if not auto-detected.

    Attributes:
        pin1_designator: User-selected Pin 1 designator. Required if
            pin1_detected was False in the extraction result.
    """

    pin1_designator: Optional[str] = Field(
        None, description="User-selected Pin 1 designator"
    )


class Job(BaseModel):
    """
    Job tracking for async processing workflow.

    Jobs are stored in-memory (for MVP) and track the progress of
    a footprint extraction from upload through file generation.

    Attributes:
        job_id: Unique identifier (UUID) for this job.
        status: Current processing status.
        filename: Original uploaded filename.
        extraction_result: AI extraction results (populated after extraction).
        confirmed_footprint: Final footprint after user confirmation.
        error_message: Error details if status is ERROR.
    """

    job_id: str
    status: JobStatus = JobStatus.PENDING
    filename: str = ""
    extraction_result: Optional[ExtractionResult] = None
    confirmed_footprint: Optional[Footprint] = None
    error_message: Optional[str] = None
