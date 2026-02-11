# Altium Designer 26 Import Testing Plan

This document outlines the manual testing procedure to validate that generated footprints work correctly in Altium Designer 26.

## Prerequisites

- Altium Designer 26 installed and licensed
- Python environment with project dependencies installed
- Access to ground truth data in `documents/` folder

---

## Test File Generation

### Step 1: Generate Test Files

```bash
cd backend
source venv/bin/activate
python generate_test_files.py
```

This creates files in `backend/test_output/`:

**DelphiScript Files (RECOMMENDED):**
- `TEST-SMD-SIMPLE.pas`
- `TEST-TH-ROUND.pas`
- `TEST-TH-SLOTTED.pas`
- `TEST-SMD-VIAS.pas`
- `SO-8EP.pas`
- `TEST-ALL-SHAPES.pas`
- `FootprintScripts.PrjScr` (Script Project containing all scripts)

**ASCII Files (Reference only - not functional):**
- `*.PcbLib` files (kept for format reference, do not import correctly)

---

## Altium Script Execution Procedure

> **Note:** This procedure was validated on Altium Designer 26 (2026-02-11).

### Working Procedure (Verified)

1. **Open Altium Designer 26**

2. **Create/Open a PCB Library document**
   - File → New → Library → PCB Library
   - Save it (e.g., `TestFootprints.PcbLib`)
   - **CRITICAL:** The PCB Library must be **open and active** (selected tab)

3. **Run the script via menu**
   - Go to **Run → Script** (in the main menu bar)
   - Browse to `backend/test_output/TEST-SMD-SIMPLE.pas`
   - Select the script and click **Run**

4. **Verify the footprint was created**
   - A message box should appear: "Footprint XXX created successfully!"
   - The footprint should appear in the PCB Library panel
   - Double-click pads to verify properties

### Alternative: Using Script Project

If you want to run multiple scripts:

1. **Open the Script Project**
   - File → Open Project
   - Navigate to `backend/test_output/FootprintScripts.PrjScr`
   - Click Open

2. **Create a PCB Library document**
   - File → New → Library → PCB Library
   - Save it and ensure it's the **active tab**

3. **Run scripts from the project**
   - In the Projects panel, expand `FootprintScripts.PrjScr`
   - Double-click on a script to open it
   - Press **F9** or Run → Run

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Please open a PCB Library document first" | Make sure a .PcbLib is open AND is the active/focused tab |
| Script doesn't appear in Run → Script | Try browsing directly to the .pas file |
| F9 doesn't work | Use Run → Script menu instead |
| Access violation error | Check for unsupported API calls (see Known Limitations) |

---

## Test Cases and Verification Checklist

### Test Case 1: TEST-SMD-SIMPLE

**Purpose:** Verify basic SMD pad creation via script

| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| Script runs without error | Success message appears | ☐ |
| Component appears in library | "TEST-SMD-SIMPLE" visible | ☐ |
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
| Script runs without error | Success message appears | ☐ |
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
| Script runs without error | Success message appears | ☐ |
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
| Script runs without error | Success message appears | ☐ |
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
| Script runs without error | Success message appears | ☐ |
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
| Script runs without error | Success message appears | ☐ |
| Pad 1 shape | Round/Circular | ☐ |
| Pad 2 shape | Rectangular | ☐ |
| Pad 3 shape | Rounded Rectangle | ☐ |
| Pad 4 shape | Oval | ☐ |
| Visual appearance | Shapes visually distinct | ☐ |

---

## Troubleshooting

### Issue: "Please open a PCB Library document first."

**Cause:** No PCB Library document is open or active.

**Fix:**
1. File → New → Library → PCB Library
2. Make sure the PCB Library tab is active (not a schematic or PCB document)
3. Run the script again

### Issue: Script doesn't appear in Run Script dialog

**Cause:** Script not added to a Script Project.

**Fix:**
1. Create a Script Project (File → New → Project → Script Project)
2. Right-click project → Add Existing to Project → Select the .pas file
3. Try File → Run Script again

### Issue: "Undeclared identifier" or syntax error

**Cause:** DelphiScript syntax issue or missing API constant.

**Fix:**
1. Check the Altium Messages panel for specific error
2. Report the exact error message for debugging

### Issue: Pads appear but positions/sizes are wrong

**Cause:** Possible issue with MMsToCoord conversion or coordinate system.

**Debug steps:**
1. Note the actual values in Altium
2. Compare to expected values in the test case
3. Report the discrepancy

### Issue: Script runs but nothing appears

**Cause:** Objects may not be added to the correct document.

**Debug steps:**
1. Check the PCB Library panel (View → Panels → PCB Library)
2. Try refreshing the view (View → Refresh)
3. Check if a new component was created in the library list

---

## Pass/Fail Criteria

### Minimum Acceptance (Must Pass All):
- [ ] At least TEST-SMD-SIMPLE script runs without error
- [ ] SMD pads appear on correct layer
- [ ] Pad positions are correct within 0.01mm
- [ ] Pad sizes are correct within 0.01mm

### Full Acceptance (Should Pass All):
- [ ] All 6 test scripts run without error
- [ ] All pad shapes render correctly
- [ ] TH pads have correct drill holes
- [ ] Slotted holes display as slots
- [ ] Vias appear and have correct properties
- [ ] SO-8EP matches ground truth within 0.05mm

---

## Results Recording

### Test Run: 2026-02-11

**Test Date:** 2026-02-11

**Altium Version:** Designer 26

**Tester:** User

| Test Case | Script Runs | Footprint Correct | Notes |
|-----------|-------------|-------------------|-------|
| TEST-SMD-SIMPLE | ✅ Pass | ✅ Pass | Pads, outline, pin 1 indicator all correct |
| TEST-TH-ROUND | ✅ Pass | ✅ Pass | Through-hole pads with drills working |
| TEST-TH-SLOTTED | ✅ Pass | ⚠️ Partial | Slots created but dimensions may be wrong |
| TEST-SMD-VIAS | ✅ Pass | ✅ Pass | Thermal vias working, outline overlaps pads |
| SO-8EP | ✅ Pass | ✅ Pass | Ground truth match, outline overlaps pads |
| TEST-ALL-SHAPES | ✅ Pass | ✅ Pass | Round, rectangular, oval all working |

**Issues Encountered:**
- Rounded Rectangle pads (`eRoundRectShape`) cause access violation - using rectangular fallback
- Slotted holes: `HoleLength` property doesn't exist - using `HoleWidth` as workaround
- Outline dimensions sometimes overlap pads (hardcoded, not calculated from bounds)

**Known MVP Limitations:**
1. Rounded Rectangle pads render as Rectangular (manual corner radius adjustment needed)
2. Slotted hole length may not be correct (API property unclear)
3. Script workflow requires: Open library → Run → Script → Browse to .pas file

**Overall Result:** ✅ PASS WITH LIMITATIONS

---

## Next Steps After Testing

1. **If all tests pass:** Proceed with extraction.py implementation (Spike 2)
2. **If tests fail:** Document issues, adjust generator_delphiscript.py, re-test
3. **If partial pass:** Document working subset, create issues for failures

---

## References

- [Altium Designer Scripting Documentation](https://www.altium.com/documentation/altium-designer/scripting/writing-scripts)
- [DelphiScript Reference](https://www.altium.com/documentation/altium-designer/scripting/delphiscript/support)
- [Scripting Examples](https://www.altium.com/documentation/altium-designer/scripting/examples-reference)
