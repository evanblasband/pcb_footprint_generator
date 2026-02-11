# Altium Designer 26 Import Testing Plan

This document outlines the manual testing procedure to validate that generated `.PcbLib` ASCII files import correctly into Altium Designer 26.

## Prerequisites

- Altium Designer 26 installed and licensed
- Python environment with project dependencies installed
- Access to ground truth data in `documents/` folder

---

## Test File Generation

### Step 1: Generate Test Files

Run the following Python script from the `backend/` directory to generate test `.PcbLib` files:

```python
# File: backend/generate_test_files.py
"""Generate test .PcbLib files for Altium import verification."""

import sys
sys.path.insert(0, '.')

from models import Footprint, Pad, PadType, PadShape, Drill, DrillType, Via, Outline
from generator import write_pcblib

# =============================================================================
# Test Case 1: Simple SMD Footprint (2 pads)
# =============================================================================

def generate_test_smd_simple():
    """Minimal SMD footprint to verify basic import."""
    pads = [
        Pad(designator="1", x=-1.27, y=0, width=0.6, height=1.0,
            shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        Pad(designator="2", x=1.27, y=0, width=0.6, height=1.0,
            shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
    ]
    footprint = Footprint(
        name="TEST-SMD-SIMPLE",
        description="Simple 2-pad SMD test footprint",
        pads=pads,
        outline=Outline(width=4.0, height=2.0)
    )
    write_pcblib(footprint, "test_output/TEST-SMD-SIMPLE.PcbLib")
    print("Generated: test_output/TEST-SMD-SIMPLE.PcbLib")

# =============================================================================
# Test Case 2: Through-Hole Footprint with Round Drills
# =============================================================================

def generate_test_th_round():
    """Through-hole footprint with round drill holes."""
    pads = [
        # Pin 1 with rounded rectangle shape (indicator)
        Pad(designator="1", x=-2.54, y=0, width=1.5, height=1.5,
            shape=PadShape.ROUNDED_RECTANGLE, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)),
        # Regular round pads
        Pad(designator="2", x=0, y=0, width=1.5, height=1.5,
            shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)),
        Pad(designator="3", x=2.54, y=0, width=1.5, height=1.5,
            shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)),
    ]
    footprint = Footprint(
        name="TEST-TH-ROUND",
        description="Through-hole test with round drills",
        pads=pads,
        outline=Outline(width=8.0, height=3.0)
    )
    write_pcblib(footprint, "test_output/TEST-TH-ROUND.PcbLib")
    print("Generated: test_output/TEST-TH-ROUND.PcbLib")

# =============================================================================
# Test Case 3: Through-Hole with Slotted Holes
# =============================================================================

def generate_test_th_slotted():
    """Through-hole footprint with slotted drill holes."""
    pads = [
        # Regular signal pin
        Pad(designator="1", x=0, y=2.0, width=1.5, height=1.5,
            shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.9)),
        # Slotted mounting holes
        Pad(designator="SH1", x=-5.0, y=0, width=3.05, height=1.25,
            rotation=90, shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT)),
        Pad(designator="SH2", x=5.0, y=0, width=3.05, height=1.25,
            rotation=90, shape=PadShape.ROUND, pad_type=PadType.THROUGH_HOLE,
            drill=Drill(diameter=0.65, slot_length=2.45, drill_type=DrillType.SLOT)),
    ]
    footprint = Footprint(
        name="TEST-TH-SLOTTED",
        description="Through-hole test with slotted holes",
        pads=pads,
        outline=Outline(width=12.0, height=5.0)
    )
    write_pcblib(footprint, "test_output/TEST-TH-SLOTTED.PcbLib")
    print("Generated: test_output/TEST-TH-SLOTTED.PcbLib")

# =============================================================================
# Test Case 4: SMD with Thermal Vias (like SO-8EP)
# =============================================================================

def generate_test_smd_with_vias():
    """SMD footprint with exposed pad and thermal vias."""
    pads = [
        # Signal pads
        Pad(designator="1", x=-2.5, y=1.27, width=0.6, height=1.2,
            rotation=90, shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        Pad(designator="2", x=-2.5, y=-1.27, width=0.6, height=1.2,
            rotation=90, shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        Pad(designator="3", x=2.5, y=-1.27, width=0.6, height=1.2,
            rotation=90, shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        Pad(designator="4", x=2.5, y=1.27, width=0.6, height=1.2,
            rotation=90, shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        # Thermal/exposed pad
        Pad(designator="5", x=0, y=0, width=2.0, height=2.0,
            shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
    ]
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
        outline=Outline(width=6.0, height=4.0)
    )
    write_pcblib(footprint, "test_output/TEST-SMD-VIAS.PcbLib")
    print("Generated: test_output/TEST-SMD-VIAS.PcbLib")

# =============================================================================
# Test Case 5: Ground Truth - SO-8EP
# =============================================================================

def generate_test_so8ep():
    """SO-8EP footprint matching ground truth data."""
    # Signal pads (pins 1-8)
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
        outline=Outline(width=5.0, height=4.0)
    )
    write_pcblib(footprint, "test_output/SO-8EP.PcbLib")
    print("Generated: test_output/SO-8EP.PcbLib")

# =============================================================================
# Test Case 6: All Pad Shapes
# =============================================================================

def generate_test_all_shapes():
    """Test all pad shapes in one footprint."""
    pads = [
        Pad(designator="1", x=-3.0, y=0, width=1.5, height=1.5,
            shape=PadShape.ROUND, pad_type=PadType.SMD),
        Pad(designator="2", x=-1.0, y=0, width=1.0, height=1.5,
            shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        Pad(designator="3", x=1.0, y=0, width=1.0, height=1.5,
            shape=PadShape.ROUNDED_RECTANGLE, pad_type=PadType.SMD),
        Pad(designator="4", x=3.0, y=0, width=0.8, height=1.5,
            shape=PadShape.OVAL, pad_type=PadType.SMD),
    ]
    footprint = Footprint(
        name="TEST-ALL-SHAPES",
        description="Test all pad shapes",
        pads=pads,
        outline=Outline(width=10.0, height=3.0)
    )
    write_pcblib(footprint, "test_output/TEST-ALL-SHAPES.PcbLib")
    print("Generated: test_output/TEST-ALL-SHAPES.PcbLib")

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import os
    os.makedirs("test_output", exist_ok=True)

    print("Generating test .PcbLib files...")
    print("=" * 50)

    generate_test_smd_simple()
    generate_test_th_round()
    generate_test_th_slotted()
    generate_test_smd_with_vias()
    generate_test_so8ep()
    generate_test_all_shapes()

    print("=" * 50)
    print("All test files generated in test_output/")
    print("\nNext: Import each file into Altium Designer 26")
```

### Step 2: Run the Generator

```bash
cd backend
source venv/bin/activate
python generate_test_files.py
```

This creates 6 test files in `backend/test_output/`:
1. `TEST-SMD-SIMPLE.PcbLib`
2. `TEST-TH-ROUND.PcbLib`
3. `TEST-TH-SLOTTED.PcbLib`
4. `TEST-SMD-VIAS.PcbLib`
5. `SO-8EP.PcbLib`
6. `TEST-ALL-SHAPES.PcbLib`

---

## Altium Import Procedure

### Method 1: Direct File Open

1. Open Altium Designer 26
2. File → Open
3. Navigate to `backend/test_output/`
4. Select the `.PcbLib` file
5. If prompted about file format, select "ASCII PCB Library"

### Method 2: Import into Existing Library

1. Open or create a new PCB Library (`.PcbLib`)
2. File → Import → ASCII PCB Library (if available)
3. Select the test file

### Method 3: Paste from ASCII

If direct import fails:
1. Open the `.PcbLib` file in a text editor
2. Copy the content between `[Component]` and `End PCB Library`
3. In Altium, create a new PcbLib component
4. Edit → Paste Special → ASCII Text

---

## Test Cases and Verification Checklist

### Test Case 1: TEST-SMD-SIMPLE

**Purpose:** Verify basic SMD pad import

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| File imports without error | No error dialogs | ☐ |
| Component name | "TEST-SMD-SIMPLE" | ☐ |
| Pad count | 2 pads visible | ☐ |
| Pad 1 position | X=-1.27mm, Y=0 | ☐ |
| Pad 2 position | X=1.27mm, Y=0 | ☐ |
| Pad dimensions | 0.6mm x 1.0mm | ☐ |
| Pad layer | Top Layer (SMD) | ☐ |
| Pad shape | Rectangular | ☐ |
| Silkscreen outline | 4.0mm x 2.0mm rectangle | ☐ |
| Pin 1 indicator | Dot/arc near pad 1 | ☐ |

**How to verify in Altium:**
- Double-click each pad to open properties dialog
- Check X/Y Location, X-Size/Y-Size, Layer, Shape


### Test Case 2: TEST-TH-ROUND

**Purpose:** Verify through-hole pads with round drills

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| File imports without error | No error dialogs | ☐ |
| Pad count | 3 pads visible | ☐ |
| Pad layer | Multi-Layer | ☐ |
| Pad 1 shape | Rounded Rectangle | ☐ |
| Pads 2-3 shape | Round | ☐ |
| Hole size | 0.9mm diameter | ☐ |
| Hole type | Round (not slotted) | ☐ |
| Pad size | 1.5mm x 1.5mm | ☐ |

**How to verify in Altium:**
- Double-click pad → check "Hole Size" field
- Check "Hole Type" dropdown shows "Round"


### Test Case 3: TEST-TH-SLOTTED

**Purpose:** Verify slotted hole support

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| File imports without error | No error dialogs | ☐ |
| Signal pad hole | 0.9mm round | ☐ |
| SH1 hole type | Slotted | ☐ |
| SH1 hole size | 0.65mm width | ☐ |
| SH1 slot length | 2.45mm | ☐ |
| SH2 matches SH1 | Same slot dimensions | ☐ |
| Rotation | SH1/SH2 rotated 90° | ☐ |

**How to verify in Altium:**
- Double-click SH1 pad
- Check "Hole Type" = "Slot"
- Check "Hole Size" and "Slot Length" fields


### Test Case 4: TEST-SMD-VIAS

**Purpose:** Verify thermal via generation

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| File imports without error | No error dialogs | ☐ |
| SMD pad count | 5 pads | ☐ |
| Via count | 4 vias | ☐ |
| Via positions | 2x2 grid at ±0.5mm | ☐ |
| Via diameter | 0.5mm | ☐ |
| Via drill size | 0.2mm | ☐ |
| Thermal pad (5) | 2.0mm x 2.0mm at center | ☐ |

**How to verify in Altium:**
- View → Toggle via visibility if needed
- Double-click via to check properties


### Test Case 5: SO-8EP (Ground Truth)

**Purpose:** Verify against known-good ground truth data

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| File imports without error | No error dialogs | ☐ |
| Total pad count | 9 pads | ☐ |
| Via count | 6 vias | ☐ |
| Pin 1 position | X=-2.498mm, Y=1.905mm | ☐ |
| Pin 1 size | 0.802mm x 1.505mm | ☐ |
| Pin 1 rotation | 90° | ☐ |
| Thermal pad (9) position | X=0, Y=0 | ☐ |
| Thermal pad size | 2.613mm x 3.502mm | ☐ |
| Via grid | 2x3 at ±0.55mm, ±1.1mm/0 | ☐ |

**Ground Truth Comparison:**
Compare the imported values against `documents/Raw Ground Truth Data - Altium Exports.pdf` Example 5 (SO-8EP).


### Test Case 6: TEST-ALL-SHAPES

**Purpose:** Verify all pad shape types render correctly

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| File imports without error | No error dialogs | ☐ |
| Pad 1 shape | Round/Circular | ☐ |
| Pad 2 shape | Rectangular | ☐ |
| Pad 3 shape | Rounded Rectangle | ☐ |
| Pad 4 shape | Oval | ☐ |
| Visual appearance | Shapes visually distinct | ☐ |

---

## Troubleshooting

### Issue: "Unrecognized file format"

**Possible causes:**
1. Header format incorrect
2. Encoding issue (should be UTF-8)
3. Line endings (try converting to Windows CRLF)

**Debug steps:**
1. Open file in text editor, verify header line is `PCB Library Document`
2. Check for BOM or encoding issues
3. Try saving with Windows line endings

### Issue: "Invalid record" or parsing error

**Possible causes:**
1. Missing required field in a record
2. Field value format incorrect (e.g., missing "mm" suffix)
3. Section structure invalid

**Debug steps:**
1. Compare file structure to working Altium export
2. Check that all numeric values have units
3. Verify each `[Section]` has matching fields

### Issue: Pads appear but dimensions wrong

**Possible causes:**
1. Unit mismatch (mils vs mm)
2. Coordinate system orientation
3. Width/Height swapped

**Debug steps:**
1. Verify all dimensions use "mm" suffix
2. Check coordinate signs (+X right, +Y up)
3. Compare to ground truth values

### Issue: Vias not visible

**Possible causes:**
1. Via section format incorrect
2. Via layer assignment wrong
3. Via size too small to display

**Debug steps:**
1. Toggle via visibility in Altium (View menu)
2. Check via `Layer` is `MultiLayer`
3. Increase via diameter for testing

---

## Pass/Fail Criteria

### Minimum Acceptance (Must Pass All):
- [ ] At least one test file imports without error
- [ ] SMD pads appear on correct layer
- [ ] TH pads have drill holes
- [ ] Pad positions match expected values within 0.01mm

### Full Acceptance (Should Pass All):
- [ ] All 6 test files import without error
- [ ] All pad shapes render correctly
- [ ] Slotted holes display as slots
- [ ] Vias appear and have correct properties
- [ ] SO-8EP matches ground truth within 0.05mm

### Known Limitations to Document:
- Any pad shapes that don't import correctly
- Any format adjustments needed for import
- Alternative import methods if direct open fails

---

## Results Recording

After testing, update this section with results:

**Test Date:** ________________

**Altium Version:** Designer 26 Build ____________

**Tester:** ________________

| Test Case | Import Status | Notes |
|-----------|---------------|-------|
| TEST-SMD-SIMPLE | ☐ Pass ☐ Fail | |
| TEST-TH-ROUND | ☐ Pass ☐ Fail | |
| TEST-TH-SLOTTED | ☐ Pass ☐ Fail | |
| TEST-SMD-VIAS | ☐ Pass ☐ Fail | |
| SO-8EP | ☐ Pass ☐ Fail | |
| TEST-ALL-SHAPES | ☐ Pass ☐ Fail | |

**Format Adjustments Required:**
-
-

**Overall Result:** ☐ PASS ☐ FAIL ☐ PASS WITH MODIFICATIONS

---

## Next Steps After Testing

1. **If all tests pass:** Proceed with extraction.py implementation
2. **If tests fail:** Document issues, adjust generator.py format, re-test
3. **If partial pass:** Document working subset, create issues for failures
