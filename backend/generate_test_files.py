#!/usr/bin/env python3
"""
Generate test files for Altium Designer 26 import verification.

This script creates test footprint files in TWO formats:
1. DelphiScript (.pas) - Run inside Altium to create footprints (RECOMMENDED)
2. ASCII (.PcbLib) - Direct file open (may not work correctly)

Usage:
    cd backend
    source venv/bin/activate
    python generate_test_files.py

Output:
    Creates files in backend/test_output/:
    - *.pas files (DelphiScript - run via DXP -> Run Script)
    - *.PcbLib files (ASCII format - for reference)

DelphiScript Usage in Altium:
    1. Open a new PCB Library (File -> New -> Library -> PCB Library)
    2. DXP -> Run Script
    3. Browse to the .pas file
    4. Click "Run"
    5. The footprint will be created in the current library

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
from generator_delphiscript import write_delphiscript


# =============================================================================
# Test Footprint Definitions
# =============================================================================


def create_test_smd_simple() -> Footprint:
    """
    Create a minimal SMD footprint to verify basic import.

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
    return Footprint(
        name="TEST-SMD-SIMPLE",
        description="Simple 2-pad SMD test footprint",
        pads=pads,
        outline=Outline(width=4.0, height=2.0),
    )


def create_test_th_round() -> Footprint:
    """
    Create a through-hole footprint with round drill holes.

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
    return Footprint(
        name="TEST-TH-ROUND",
        description="Through-hole test with round drills",
        pads=pads,
        outline=Outline(width=8.0, height=3.0),
    )


def create_test_th_slotted() -> Footprint:
    """
    Create a through-hole footprint with slotted drill holes.

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
    return Footprint(
        name="TEST-TH-SLOTTED",
        description="Through-hole test with slotted holes",
        pads=pads,
        outline=Outline(width=12.0, height=5.0),
    )


def create_test_smd_with_vias() -> Footprint:
    """
    Create an SMD footprint with exposed pad and thermal vias.

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
    return Footprint(
        name="TEST-SMD-VIAS",
        description="SMD with thermal pad and vias",
        pads=pads,
        vias=vias,
        outline=Outline(width=6.0, height=4.0),
    )


def create_test_so8ep() -> Footprint:
    """
    Create SO-8EP footprint matching ground truth data.

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

    return Footprint(
        name="SO-8EP",
        description="SOIC-8 with exposed thermal pad - Ground Truth Test",
        pads=signal_pads + [thermal_pad],
        vias=vias,
        outline=Outline(width=5.0, height=4.0),
    )


def create_test_all_shapes() -> Footprint:
    """
    Create a footprint with all supported pad shapes.

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
    return Footprint(
        name="TEST-ALL-SHAPES",
        description="Test all pad shapes: Round, Rectangular, Rounded Rectangle, Oval",
        pads=pads,
        outline=Outline(width=10.0, height=3.0),
    )


# =============================================================================
# File Generation
# =============================================================================


def generate_both_formats(footprint: Footprint, output_dir: str) -> None:
    """
    Generate both DelphiScript and ASCII formats for a footprint.

    Args:
        footprint: The footprint to generate files for
        output_dir: Directory to write files to
    """
    name = footprint.name

    # Generate DelphiScript (.pas) - RECOMMENDED
    pas_path = os.path.join(output_dir, f"{name}.pas")
    write_delphiscript(footprint, pas_path)
    print(f"  [RECOMMENDED] {name}.pas (DelphiScript)")

    # Generate ASCII (.PcbLib) - for reference
    pcblib_path = os.path.join(output_dir, f"{name}.PcbLib")
    write_pcblib(footprint, pcblib_path)
    print(f"  [Reference]   {name}.PcbLib (ASCII)")


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Generate all test files in both formats."""
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70)
    print("Generating test files for Altium Designer 26")
    print("=" * 70)
    print()
    print("Two formats are generated:")
    print("  1. DelphiScript (.pas) - Run via DXP -> Run Script [RECOMMENDED]")
    print("  2. ASCII (.PcbLib) - Direct file open [May not work]")
    print()

    # Test cases
    test_cases = [
        ("Test Case 1: Simple SMD footprint", create_test_smd_simple),
        ("Test Case 2: Through-hole with round drills", create_test_th_round),
        ("Test Case 3: Through-hole with slotted holes", create_test_th_slotted),
        ("Test Case 4: SMD with thermal vias", create_test_smd_with_vias),
        ("Test Case 5: SO-8EP (Ground Truth)", create_test_so8ep),
        ("Test Case 6: All pad shapes", create_test_all_shapes),
    ]

    for description, create_func in test_cases:
        print(f"{description}")
        footprint = create_func()
        generate_both_formats(footprint, output_dir)
        print()

    print("=" * 70)
    print(f"All test files generated in: {output_dir}/")
    print()
    print("To test DelphiScript files in Altium Designer 26:")
    print("  1. Open Altium Designer")
    print("  2. Create a new PCB Library (File -> New -> Library -> PCB Library)")
    print("  3. Go to DXP -> Run Script")
    print("  4. Browse to a .pas file and click 'Run'")
    print("  5. The footprint will be created in the current library")
    print()
    print("See tests/ALTIUM_TESTING_PLAN.md for detailed testing procedure.")
    print("=" * 70)


if __name__ == "__main__":
    main()
