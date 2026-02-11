"""
Altium .PcbLib ASCII file generator.

This module generates Altium Designer 26 compatible PCB footprint library files
in ASCII format. The ASCII format is a structured text file that can be directly
imported into Altium's PcbLib editor.

File Format Overview:
    The .PcbLib ASCII format consists of:
    1. Header section with file metadata
    2. Component record with footprint name/description
    3. Pad records for each pad (SMD or through-hole)
    4. Via records for thermal vias
    5. Track records for silkscreen outline
    6. Arc records for Pin 1 indicator

Coordinate System:
    - Origin at component center
    - +X points right, +Y points up
    - All dimensions in millimeters (mm)
    - Rotations in degrees

Reference:
    Ground truth data from documents/Raw Ground Truth Data - Altium Exports.pdf
"""

from typing import TextIO
from io import StringIO

from models import (
    Footprint,
    Pad,
    PadType,
    PadShape,
    DrillType,
    Via,
    Outline,
)


# =============================================================================
# Constants - Altium ASCII format values
# =============================================================================

# Layer names used in Altium ASCII format
LAYER_TOP = "Top Layer"
LAYER_MULTI = "MultiLayer"
LAYER_TOP_OVERLAY = "Top Overlay"

# Shape names as they appear in Altium format
SHAPE_ROUND = "Round"
SHAPE_RECTANGULAR = "Rectangular"
SHAPE_ROUNDED_RECTANGLE = "Rounded Rectangle"
SHAPE_OVAL = "Oval"

# Drill type names
DRILL_ROUND = "Round"
DRILL_SLOT = "Slot"


# =============================================================================
# Shape Mapping - Convert our enum values to Altium format strings
# =============================================================================

SHAPE_MAP = {
    PadShape.ROUND: SHAPE_ROUND,
    PadShape.RECTANGULAR: SHAPE_RECTANGULAR,
    PadShape.ROUNDED_RECTANGLE: SHAPE_ROUNDED_RECTANGLE,
    PadShape.OVAL: SHAPE_OVAL,
}


# =============================================================================
# Generator Class
# =============================================================================


class AltiumGenerator:
    """
    Generator for Altium .PcbLib ASCII format files.

    This class converts a Footprint model into the ASCII text format that
    Altium Designer can import directly.

    Usage:
        generator = AltiumGenerator(footprint)
        ascii_content = generator.generate()

        # Or write directly to file
        generator.write_to_file("output.PcbLib")

    Attributes:
        footprint: The Footprint model to generate
        _record_id: Auto-incrementing record ID counter
    """

    def __init__(self, footprint: Footprint):
        """
        Initialize the generator with a footprint.

        Args:
            footprint: The Footprint model containing all pad/via/outline data
        """
        self.footprint = footprint
        self._record_id = 0  # Record ID counter for unique IDs

    def _next_record_id(self) -> int:
        """Get the next unique record ID."""
        self._record_id += 1
        return self._record_id

    def generate(self) -> str:
        """
        Generate the complete .PcbLib ASCII content.

        Returns:
            String containing the full ASCII file content ready for import.
        """
        output = StringIO()

        # Write file header
        self._write_header(output)

        # Write component/footprint record
        self._write_component_record(output)

        # Write all pads
        for pad in self.footprint.pads:
            self._write_pad_record(output, pad)

        # Write all vias
        for via in self.footprint.vias:
            self._write_via_record(output, via)

        # Write silkscreen outline if present
        if self.footprint.outline:
            self._write_outline_tracks(output, self.footprint.outline)
            self._write_pin1_indicator(output)

        # Write file footer
        self._write_footer(output)

        return output.getvalue()

    def write_to_file(self, filepath: str) -> None:
        """
        Generate and write the ASCII content to a file.

        Args:
            filepath: Path to the output .PcbLib file
        """
        content = self.generate()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    # =========================================================================
    # Private Methods - Section Writers
    # =========================================================================

    def _write_header(self, output: TextIO) -> None:
        """
        Write the file header section.

        The header identifies this as a PCB Library file and sets up
        the format version and encoding.
        """
        output.write("PCB Library Document\n")
        output.write("Version=1.0\n")
        output.write("Encoding=UTF-8\n")
        output.write("\n")

    def _write_footer(self, output: TextIO) -> None:
        """Write the file footer section."""
        output.write("\n")
        output.write("End PCB Library\n")

    def _write_component_record(self, output: TextIO) -> None:
        """
        Write the component/footprint definition record.

        This establishes the footprint name and description that will
        appear in Altium's library browser.
        """
        output.write("[Component]\n")
        output.write(f"Name={self.footprint.name}\n")
        if self.footprint.description:
            output.write(f"Description={self.footprint.description}\n")
        output.write(f"RecordID={self._next_record_id()}\n")
        output.write("\n")

    def _write_pad_record(self, output: TextIO, pad: Pad) -> None:
        """
        Write a pad record.

        Handles both SMD and through-hole pads, with proper layer assignment
        and drill specifications.

        Args:
            output: Output stream to write to
            pad: The Pad model to write
        """
        output.write("[Pad]\n")
        output.write(f"RecordID={self._next_record_id()}\n")
        output.write(f"Designator={pad.designator}\n")

        # Layer depends on pad type
        layer = LAYER_TOP if pad.pad_type == PadType.SMD else LAYER_MULTI
        output.write(f"Layer={layer}\n")

        # Position (in mm)
        output.write(f"X={self._format_coord(pad.x)}\n")
        output.write(f"Y={self._format_coord(pad.y)}\n")

        # Rotation
        output.write(f"Rotation={self._format_rotation(pad.rotation)}\n")

        # Pad shape
        shape_name = SHAPE_MAP.get(pad.shape, SHAPE_RECTANGULAR)
        output.write(f"Shape={shape_name}\n")

        # Pad size (XSize and YSize)
        # Note: For rotated pads, width/height are pre-rotation dimensions
        output.write(f"XSize={self._format_dim(pad.width)}\n")
        output.write(f"YSize={self._format_dim(pad.height)}\n")

        # Through-hole specific: drill hole
        if pad.pad_type == PadType.THROUGH_HOLE and pad.drill:
            self._write_drill_info(output, pad)

        output.write("\n")

    def _write_drill_info(self, output: TextIO, pad: Pad) -> None:
        """
        Write drill hole information for through-hole pads.

        Handles both round and slotted holes.

        Args:
            output: Output stream to write to
            pad: The Pad model with drill information
        """
        drill = pad.drill

        # Drill diameter (hole size)
        output.write(f"HoleSize={self._format_dim(drill.diameter)}\n")

        # Drill type (Round or Slot)
        if drill.drill_type == DrillType.SLOT and drill.slot_length:
            output.write(f"DrillType={DRILL_SLOT}\n")
            output.write(f"SlotLength={self._format_dim(drill.slot_length)}\n")
        else:
            output.write(f"DrillType={DRILL_ROUND}\n")

    def _write_via_record(self, output: TextIO, via: Via) -> None:
        """
        Write a via record.

        Vias are always MultiLayer (through-hole) with round shape.

        Args:
            output: Output stream to write to
            via: The Via model to write
        """
        output.write("[Via]\n")
        output.write(f"RecordID={self._next_record_id()}\n")
        output.write(f"Layer={LAYER_MULTI}\n")
        output.write(f"X={self._format_coord(via.x)}\n")
        output.write(f"Y={self._format_coord(via.y)}\n")
        output.write(f"Diameter={self._format_dim(via.diameter)}\n")
        output.write(f"HoleSize={self._format_dim(via.drill_diameter)}\n")
        output.write("\n")

    def _write_outline_tracks(self, output: TextIO, outline: Outline) -> None:
        """
        Write silkscreen outline as track segments.

        Creates a rectangular outline on the Top Overlay layer representing
        the component body boundary.

        Args:
            output: Output stream to write to
            outline: The Outline model with dimensions
        """
        # Calculate corner coordinates (centered at origin)
        half_w = outline.width / 2
        half_h = outline.height / 2
        line_width = outline.line_width

        # Define the four corners
        corners = [
            (-half_w, -half_h),  # Bottom-left
            (half_w, -half_h),   # Bottom-right
            (half_w, half_h),    # Top-right
            (-half_w, half_h),   # Top-left
        ]

        # Write four track segments forming the rectangle
        for i in range(4):
            start = corners[i]
            end = corners[(i + 1) % 4]  # Wrap around to close rectangle

            output.write("[Track]\n")
            output.write(f"RecordID={self._next_record_id()}\n")
            output.write(f"Layer={LAYER_TOP_OVERLAY}\n")
            output.write(f"X1={self._format_coord(start[0])}\n")
            output.write(f"Y1={self._format_coord(start[1])}\n")
            output.write(f"X2={self._format_coord(end[0])}\n")
            output.write(f"Y2={self._format_coord(end[1])}\n")
            output.write(f"Width={self._format_dim(line_width)}\n")
            output.write("\n")

    def _write_pin1_indicator(self, output: TextIO) -> None:
        """
        Write Pin 1 indicator mark on silkscreen.

        Places a small dot/circle near Pin 1 position on the Top Overlay layer.
        Pin 1 is identified as the first pad with designator "1" or the first
        pad in the list if no "1" exists.
        """
        # Find Pin 1 position
        pin1 = self._find_pin1()
        if not pin1:
            return

        # Place indicator slightly offset from pad center
        # Offset in the direction away from component center
        indicator_x = pin1.x
        indicator_y = pin1.y

        # Offset away from center
        if pin1.x < 0:
            indicator_x -= 0.5
        else:
            indicator_x += 0.5

        if pin1.y > 0:
            indicator_y += 0.5
        else:
            indicator_y -= 0.5

        # Write a small arc (dot) as Pin 1 indicator
        output.write("[Arc]\n")
        output.write(f"RecordID={self._next_record_id()}\n")
        output.write(f"Layer={LAYER_TOP_OVERLAY}\n")
        output.write(f"X={self._format_coord(indicator_x)}\n")
        output.write(f"Y={self._format_coord(indicator_y)}\n")
        output.write("Radius=0.25mm\n")
        output.write("StartAngle=0\n")
        output.write("EndAngle=360\n")
        output.write("Width=0.15mm\n")
        output.write("\n")

    def _find_pin1(self) -> Pad | None:
        """
        Find Pin 1 in the footprint.

        Returns:
            The Pad designated as Pin 1, or None if not found.

        Search order:
            1. Pad with designator "1"
            2. First pad in list (fallback)
        """
        # Look for explicit Pin 1
        for pad in self.footprint.pads:
            if pad.designator == "1":
                return pad

        # Fallback to first pad
        if self.footprint.pads:
            return self.footprint.pads[0]

        return None

    # =========================================================================
    # Private Methods - Formatting Helpers
    # =========================================================================

    def _format_coord(self, value: float) -> str:
        """
        Format a coordinate value for output.

        Args:
            value: Coordinate in mm

        Returns:
            Formatted string with 'mm' suffix (e.g., "2.54mm")
        """
        # Use enough precision to preserve accuracy
        # Round to 3 decimal places (micrometer precision)
        return f"{value:.3f}mm"

    def _format_dim(self, value: float) -> str:
        """
        Format a dimension value for output.

        Args:
            value: Dimension in mm

        Returns:
            Formatted string with 'mm' suffix (e.g., "0.802mm")
        """
        return f"{value:.3f}mm"

    def _format_rotation(self, value: float) -> str:
        """
        Format a rotation angle for output.

        Args:
            value: Rotation in degrees

        Returns:
            Formatted string (e.g., "90.000")
        """
        return f"{value:.3f}"


# =============================================================================
# Convenience Functions
# =============================================================================


def generate_pcblib(footprint: Footprint) -> str:
    """
    Generate Altium .PcbLib ASCII content from a footprint.

    This is a convenience function that wraps AltiumGenerator.

    Args:
        footprint: The Footprint model to convert

    Returns:
        String containing the ASCII file content

    Example:
        footprint = Footprint(name="SO-8", pads=[...])
        content = generate_pcblib(footprint)
    """
    generator = AltiumGenerator(footprint)
    return generator.generate()


def write_pcblib(footprint: Footprint, filepath: str) -> None:
    """
    Generate and write a .PcbLib file from a footprint.

    This is a convenience function that wraps AltiumGenerator.

    Args:
        footprint: The Footprint model to convert
        filepath: Path to write the output file

    Example:
        footprint = Footprint(name="SO-8", pads=[...])
        write_pcblib(footprint, "SO-8.PcbLib")
    """
    generator = AltiumGenerator(footprint)
    generator.write_to_file(filepath)
