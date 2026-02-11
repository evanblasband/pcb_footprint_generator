#!/usr/bin/env python3
"""
Generate test .PcbLib files for Altium Designer 26 import verification.

This script creates a set of test footprint files covering different
pad types, shapes, and configurations. Use these files to validate
that the generator output is compatible with Altium Designer.

Usage:
    cd backend
    source venv/bin/activate
    python generate_test_files.py

Output:
    Creates .PcbLib files in backend/test_output/

See tests/ALTIUM_TESTING_PLAN.md for the full testing procedure.
"""

import os
import sys

# Ensure we can import from the backend package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
from generator import write_pcblib


# =============================================================================
# Test Case 1: Simple SMD Footprint (2 pads)
# =============================================================================


def generate_test_smd_simple() -> None:
    """
    Generate a minimal SMD footprint to verify basic import.

    This is the simplest possible footprint - just two rectangular
    SMD pads and a silkscreen outline.
    """
    pads = [
        Pad(
            designator="1",
            x=-1.27,
            y=0,
            width=0.6,
            height=1.0,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="2",
            x=1.27,
            y=0,
            width=0.6,
            height=1.0,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
    ]
    footprint = Footprint(
        name="TEST-SMD-SIMPLE",
        description="Simple 2-pad SMD test footprint",
        pads=pads,
        outline=Outline(width=4.0, height=2.0),
    )
    write_pcblib(footprint, "test_output/TEST-SMD-SIMPLE.PcbLib")
    print("  Generated: test_output/TEST-SMD-SIMPLE.PcbLib")


# =============================================================================
# Test Case 2: Through-Hole Footprint with Round Drills
# =============================================================================


def generate_test_th_round() -> None:
    """
    Generate a through-hole footprint with round drill holes.

    Tests:
    - MultiLayer pad assignment
    - Round drill hole specification
    - Rounded Rectangle shape for Pin 1 indicator
    """
    pads = [
        # Pin 1 with rounded rectangle shape (indicator)
        Pad(
            designator="1",
            x=-2.54,
            y=0,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUNDED_RECTANGLE,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9),
        ),
        # Regular round pads
        Pad(
            designator="2",
            x=0,
            y=0,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9),
        ),
        Pad(
            designator="3",
            x=2.54,
            y=0,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9),
        ),
    ]
    footprint = Footprint(
        name="TEST-TH-ROUND",
        description="Through-hole test with round drills",
        pads=pads,
        outline=Outline(width=8.0, height=3.0),
    )
    write_pcblib(footprint, "test_output/TEST-TH-ROUND.PcbLib")
    print("  Generated: test_output/TEST-TH-ROUND.PcbLib")


# =============================================================================
# Test Case 3: Through-Hole with Slotted Holes
# =============================================================================


def generate_test_th_slotted() -> None:
    """
    Generate a through-hole footprint with slotted drill holes.

    Tests:
    - Drilled Slot type specification
    - Slot length parameter
    - Mixed round and slotted holes
    """
    pads = [
        # Regular signal pin with round hole
        Pad(
            designator="1",
            x=0,
            y=2.0,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9),
        ),
        # Slotted mounting holes (like USB connector shields)
        Pad(
            designator="SH1",
            x=-5.0,
            y=0,
            width=3.05,
            height=1.25,
            rotation=90,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT),
        ),
        Pad(
            designator="SH2",
            x=5.0,
            y=0,
            width=3.05,
            height=1.25,
            rotation=90,
            shape=PadShape.ROUND,
            pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT),
        ),
    ]
    footprint = Footprint(
        name="TEST-TH-SLOTTED",
        description="Through-hole test with slotted holes",
        pads=pads,
        outline=Outline(width=12.0, height=5.0),
    )
    write_pcblib(footprint, "test_output/TEST-TH-SLOTTED.PcbLib")
    print("  Generated: test_output/TEST-TH-SLOTTED.PcbLib")


# =============================================================================
# Test Case 4: SMD with Thermal Vias
# =============================================================================


def generate_test_smd_with_vias() -> None:
    """
    Generate an SMD footprint with exposed pad and thermal vias.

    Tests:
    - Via record generation
    - Via positioning
    - Via drill and diameter specifications
    """
    pads = [
        # Signal pads at corners
        Pad(
            designator="1",
            x=-2.5,
            y=1.27,
            width=0.6,
            height=1.2,
            rotation=90,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="2",
            x=-2.5,
            y=-1.27,
            width=0.6,
            height=1.2,
            rotation=90,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="3",
            x=2.5,
            y=-1.27,
            width=0.6,
            height=1.2,
            rotation=90,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="4",
            x=2.5,
            y=1.27,
            width=0.6,
            height=1.2,
            rotation=90,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
        # Thermal/exposed pad at center
        Pad(
            designator="5",
            x=0,
            y=0,
            width=2.0,
            height=2.0,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
    ]
    # 2x2 grid of thermal vias
    vias = [
        Via(x=-0.5, y=0.5, diameter=0.5, drill_diameter=0.2),
        Via(x=0.5, y=0.5, diameter=0.5, drill_diameter=0.2),
        Via(x=-0.5, y=-0.5, diameter=0.5, drill_diameter=0.2),
        Via(x=0.5, y=-0.5, diameter=0.5, drill_diameter=0.2),
    ]
    footprint = Footprint(
        name="TEST-SMD-VIAS",
        description="SMD with thermal pad and vias",
        pads=pads,
        vias=vias,
        outline=Outline(width=6.0, height=4.0),
    )
    write_pcblib(footprint, "test_output/TEST-SMD-VIAS.PcbLib")
    print("  Generated: test_output/TEST-SMD-VIAS.PcbLib")


# =============================================================================
# Test Case 5: Ground Truth - SO-8EP
# =============================================================================


def generate_test_so8ep() -> None:
    """
    Generate SO-8EP footprint matching ground truth data.

    This is the most important test case - it should match the
    ground truth values from documents/Raw Ground Truth Data.

    Ground truth reference:
    - 8 signal pads (pins 1-8)
    - 1 thermal pad (pin 9) at center
    - 6 thermal vias in 2x3 grid
    """
    # Signal pads (pins 1-8)
    signal_pads = []
    y_positions = [1.905, 0.635, -0.635, -1.905]

    # Left side (pins 1-4) - top to bottom
    for i, y in enumerate(y_positions):
        signal_pads.append(
            Pad(
                designator=str(i + 1),
                x=-2.498,
                y=y,
                width=0.802,
                height=1.505,
                rotation=90,
                shape=PadShape.RECTANGULAR,
                pad_type=PadType.SMD,
            )
        )

    # Right side (pins 5-8) - bottom to top
    for i, y in enumerate(reversed(y_positions)):
        signal_pads.append(
            Pad(
                designator=str(i + 5),
                x=2.497,
                y=y,
                width=0.802,
                height=1.505,
                rotation=90,
                shape=PadShape.RECTANGULAR,
                pad_type=PadType.SMD,
            )
        )

    # Thermal pad (pin 9) at center
    thermal_pad = Pad(
        designator="9",
        x=0,
        y=0,
        width=2.613,
        height=3.502,
        shape=PadShape.RECTANGULAR,
        pad_type=PadType.SMD,
    )

    # Thermal vias (2x3 grid)
    vias = []
    for x in [-0.55, 0.55]:
        for y in [-1.1, 0, 1.1]:
            vias.append(Via(x=x, y=y, diameter=0.5, drill_diameter=0.2))

    footprint = Footprint(
        name="SO-8EP",
        description="SOIC-8 with exposed thermal pad - Ground Truth Test",
        pads=signal_pads + [thermal_pad],
        vias=vias,
        outline=Outline(width=5.0, height=4.0),
    )
    write_pcblib(footprint, "test_output/SO-8EP.PcbLib")
    print("  Generated: test_output/SO-8EP.PcbLib")


# =============================================================================
# Test Case 6: All Pad Shapes
# =============================================================================


def generate_test_all_shapes() -> None:
    """
    Generate a footprint with all supported pad shapes.

    Tests:
    - Round shape
    - Rectangular shape
    - Rounded Rectangle shape
    - Oval shape
    """
    pads = [
        Pad(
            designator="1",
            x=-3.0,
            y=0,
            width=1.5,
            height=1.5,
            shape=PadShape.ROUND,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="2",
            x=-1.0,
            y=0,
            width=1.0,
            height=1.5,
            shape=PadShape.RECTANGULAR,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="3",
            x=1.0,
            y=0,
            width=1.0,
            height=1.5,
            shape=PadShape.ROUNDED_RECTANGLE,
            pad_type=PadType.SMD,
        ),
        Pad(
            designator="4",
            x=3.0,
            y=0,
            width=0.8,
            height=1.5,
            shape=PadShape.OVAL,
            pad_type=PadType.SMD,
        ),
    ]
    footprint = Footprint(
        name="TEST-ALL-SHAPES",
        description="Test all pad shapes: Round, Rectangular, Rounded Rectangle, Oval",
        pads=pads,
        outline=Outline(width=10.0, height=3.0),
    )
    write_pcblib(footprint, "test_output/TEST-ALL-SHAPES.PcbLib")
    print("  Generated: test_output/TEST-ALL-SHAPES.PcbLib")


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Generate all test .PcbLib files."""
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("Generating test .PcbLib files for Altium Designer 26")
    print("=" * 60)
    print()

    # Generate all test files
    print("Test Case 1: Simple SMD footprint")
    generate_test_smd_simple()

    print("\nTest Case 2: Through-hole with round drills")
    generate_test_th_round()

    print("\nTest Case 3: Through-hole with slotted holes")
    generate_test_th_slotted()

    print("\nTest Case 4: SMD with thermal vias")
    generate_test_smd_with_vias()

    print("\nTest Case 5: SO-8EP (Ground Truth)")
    generate_test_so8ep()

    print("\nTest Case 6: All pad shapes")
    generate_test_all_shapes()

    print()
    print("=" * 60)
    print(f"All test files generated in: {output_dir}/")
    print()
    print("Next steps:")
    print("  1. Copy test files to a machine with Altium Designer 26")
    print("  2. Follow the testing procedure in tests/ALTIUM_TESTING_PLAN.md")
    print("  3. Record results in the testing plan document")
    print("=" * 60)


if __name__ == "__main__":
    main()
