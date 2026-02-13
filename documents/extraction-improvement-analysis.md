# Expert Analysis: PCB Footprint Extraction Improvement Plan

## Executive Summary

**Do this first:** Implement a **2-stage "Parse-Then-Extract" pipeline** that separates table/variable parsing from geometry extraction. This alone should yield 30-40% accuracy improvement on table-variable format datasheets with minimal implementation effort (2-3 days).

**Then:** Add a **verification pass** where the model self-checks extracted values against the image. Skip CV preprocessing—it's over-engineered for this problem and Claude's vision already handles shape detection well.

---

## Confirmed Failure Modes (All Observed)

Based on user feedback, **all four failure modes** are occurring:
1. ✓ Pad vs Pitch confusion
2. ✓ Table correlation errors
3. ✓ Missing elements (thermal pads, vias)
4. ✓ Position errors

This confirms the multi-stage pipeline is the correct approach because:
- **Stage 1** (table parsing) → Fixes #2 (table correlation)
- **Stage 2** (focused extraction) → Fixes #3 (missing elements) and #4 (positions)
- **Verification pass** → Catches #1 (pad vs pitch) and validates all above

---

## Approach Analysis

| Approach | Feasibility | Impact | Time | Recommendation |
|----------|-------------|--------|------|----------------|
| Multi-Stage AI Pipeline | 8/10 | 8/10 | 2-3 days | **DO FIRST** - High ROI |
| CV Pre-processing | 4/10 | 3/10 | 4-5 days | **SKIP** - Over-engineered |
| Dimension Line Detection | 3/10 | 4/10 | 5+ days | **SKIP** - Too fragile |
| Template-Based + Fallback | 7/10 | 5/10 | 3 days | **DEFER** - Do after MVP |
| User-Guided Hints | 9/10 | 9/10 | 2 days | **DO SECOND** - Low effort, high impact |
| Verification Pass | 9/10 | 7/10 | 1 day | **DO THIRD** - Nearly free |
| Ensemble Voting | 5/10 | 4/10 | 4 days | **SKIP** - 3x cost for marginal gain |

---

## Recommended Implementation Plan

### Phase 1: Parse-Then-Extract Pipeline (Days 1-3)

**Why this first:** The ATECC608A example shows a table-variable format—the model must correctly parse the dimension table AND apply those values to the drawing. Separating these tasks reduces cognitive load on each prompt.

**Current failure mode hypothesis:** The model tries to do everything at once: identify shapes, read the table, correlate variables, calculate positions—leading to errors when any step is ambiguous.

**Implementation:**

```
Stage 1: Scene Analysis + Table Parsing (Haiku - cheap)
├── Identify drawing type and format
├── Parse the dimension table (if present)
│   └── Extract mapping: {X1: 0.30, X2: 1.60, Y1: 0.85, Y2: 1.40, ...}
├── Identify package style and pad arrangement
└── Output: metadata + parsed_table

Stage 2: Geometry Extraction (Sonnet - accurate)
├── Input: image + parsed_table from Stage 1
├── Focus ONLY on identifying shapes and assigning dimensions
├── "The table says X1=0.30mm. Which dimension in the drawing is X1?"
└── Output: final footprint JSON
```

**Exact prompt modifications:**

```python
# Stage 1 prompt (new file: prompts_staged.py)
STAGE1_PROMPT = """Analyze this datasheet image and extract metadata.

## Task 1: Identify Drawing Format
- Is this a table-variable format (dimensions shown as A, B, C with a table)?
- Or inline dimensions (values shown directly on the drawing)?

## Task 2: Parse Dimension Table (if present)
If there's a table mapping variable names to values, extract it:
- Look for tables with columns like "Symbol", "MIN", "NOM", "MAX"
- Extract the NOM (nominal) or TYP (typical) values
- Map each variable to its millimeter value

## Task 3: Package Analysis
- Package type (UDFN, QFN, SOIC, connector, etc.)
- Pad arrangement (peripheral, linear rows, grid)
- Approximate pad count
- Units used (mm, mil, inch)

Return JSON:
{
  "drawing_format": "table_variable" | "inline",
  "dimension_table": {
    "X1": 0.30,
    "X2": 1.60,
    "Y1": 0.85,
    ...
  },
  "package_type": "UDFN-8",
  "pad_arrangement": "peripheral",
  "pad_count": 9,
  "units": "mm"
}"""

# Stage 2 prompt - inject parsed data
STAGE2_PROMPT = """Extract footprint geometry from this datasheet image.

## Context from Analysis
{stage1_output}

## Your Task
Using the dimension values from the table above, identify what each
variable refers to in the drawing and build the complete footprint.

## Dimension Assignments
For each dimension variable, identify what it measures:
- X1 = {X1}mm → likely pad width (horizontal dimension of one pad)
- X2 = {X2}mm → likely thermal pad width
- Y1 = {Y1}mm → likely pad height/length (vertical dimension)
- G1 = {G1}mm → likely pad-to-center distance
- E = {E}mm → likely pad pitch (distance between pad centers)

## Critical Rules
[... existing rules about pad vs pitch, etc ...]

Return the complete footprint JSON with all pads positioned."""
```

**Success metric:** Table-variable format extraction accuracy improves from baseline to >85% on ATECC608A-style datasheets

**Cost estimate:** ~2x API calls but Stage 1 uses Haiku (~$0.001), Stage 2 uses Sonnet (~$0.02) = ~$0.025/extraction vs current ~$0.02

---

### Phase 2: Confidence-Based User Hints (Days 3-4)

**Why this second:** The current system has no escape hatch when the model is uncertain. Adding targeted user prompts for low-confidence elements dramatically improves accuracy with minimal user friction.

**Implementation:**

```python
# In extraction.py - add after main extraction

def request_user_hints(extraction_result: ExtractionResult) -> list[UserHint]:
    """Identify what to ask the user based on confidence scores."""
    hints_needed = []

    # Pin 1 uncertain
    if not extraction_result.pin1_detected or extraction_result.overall_confidence < 0.7:
        hints_needed.append(UserHint(
            type="pin1_click",
            prompt="Click on Pin 1 location",
            required=True
        ))

    # Pitch value uncertain (common failure)
    pitches = detect_likely_pitch(extraction_result.pads)
    if len(set(pitches)) > 1:  # Multiple pitch values detected
        hints_needed.append(UserHint(
            type="pitch_confirm",
            prompt=f"Confirm pad pitch: {pitches[0]:.2f}mm?",
            options=[f"{p:.2f}mm" for p in sorted(set(pitches))]
        ))

    # Scale reference (if positions seem wrong)
    if extraction_result.overall_confidence < 0.5:
        hints_needed.append(UserHint(
            type="scale_reference",
            prompt="Click two points and enter the distance between them"
        ))

    return hints_needed
```

**Frontend changes:**
- Add "confidence indicator" colors to preview (green/yellow/red)
- Pin 1 click handler (already partially implemented)
- Optional pitch confirmation dialog

**Success metric:** User can resolve 90% of low-confidence extractions with 1-2 clicks/inputs

---

### Phase 3: Self-Verification Pass (Day 5)

**Why this third:** Nearly free to implement and catches obvious errors. The model reviews its own extraction against the image.

**Implementation:**

```python
VERIFICATION_PROMPT = """I extracted this footprint from the image:

{extraction_json}

Please verify each extracted value by checking against the image:

1. Pad count: I found {pad_count} pads. Count the pads in the image - is this correct?

2. Pad dimensions: I extracted pad width={pad_width}mm, height={pad_height}mm.
   - Is this the size of ONE pad, or is this a spacing/pitch value?
   - The pitch/spacing between pads should be LARGER than pad width.

3. Positions: Pads are positioned at X={x_positions}.
   - Does this match the symmetry shown in the drawing?

4. Thermal pad: {thermal_status}

Return corrections if any values are wrong:
{
  "verified": true/false,
  "corrections": [
    {"field": "pad_width", "old": 1.27, "new": 0.5, "reason": "1.27 is pitch, not pad width"}
  ],
  "confidence_adjustment": 0.9
}"""
```

**Cost:** ~$0.005 additional per extraction (Haiku can do verification)

**Success metric:** Catches 50%+ of pad-vs-pitch confusion errors

---

## Technical Deep-Dives

### Issue 1: Table-Variable Format Correlation

**Current bottleneck:** The model sees "X1" in the drawing and "X1=0.30" in the table but may not correctly link them when other dimensions are similar.

**Proposed solution:** Explicit table parsing with structured handoff.

**Key insight from ATECC608A image:**
- X1 = 0.30mm (pad width)
- X2 = 1.60mm (thermal pad width)
- Y1 = 0.85mm (pad height)
- Y2 = 1.40mm (thermal pad height)
- G1 = 0.20mm (pad-to-center horizontal)
- G2 = 0.33mm (pad-to-center vertical)
- E = 0.50mm (pad pitch)
- V = 0.30mm (via diameter)
- EV = 1.00mm (via pitch)

The model must understand that X1 (0.30mm) describes the pad COPPER size, while E (0.50mm) describes the SPACING between pads.

**Prompt engineering fix:**

```
## Dimension Semantics Guide for UDFN/QFN Packages

Typical variable naming conventions:
- X1, W, Pad Width → COPPER width of one pad (typically 0.2-0.5mm)
- X2, Center Pad Width → THERMAL PAD width (typically 1-3mm)
- Y1, L, Pad Length → COPPER height/length of one pad
- E, Pitch → SPACING between pad centers (NOT pad size!)
- G, Pad-to-Edge → Distance from pad center to package edge

CRITICAL: If you see E=0.50mm, this is PITCH, not pad width!
The pad width will be smaller (typically 0.5-0.7 × pitch).
```

---

### Issue 2: Pad Dimension vs Pitch Confusion

**Current bottleneck:** Despite 50+ lines in the prompt about this, the model still confuses pad dimensions with spacing.

**Root cause hypothesis:** The prompt is too long—critical information is buried.

**Proposed solution:** Restructure prompt with examples at the top.

```python
EXTRACTION_PROMPT = """## CRITICAL EXAMPLE - Read First

This is a CORRECT extraction:
- Pitch (E) = 0.50mm → distance between pad centers
- Pad width (X1) = 0.30mm → copper width of ONE pad
- Pad width is 60% of pitch (0.30/0.50) ✓

This is WRONG:
- Pitch (E) = 0.50mm
- Pad width = 0.50mm ← WRONG! Used pitch for pad width!
- Pad width should be ~0.25-0.35mm for 0.50mm pitch

If pad_width ≈ pitch, you probably made this mistake.

---

[Rest of prompt...]"""
```

---

## Do Not Pursue

### CV Pre-processing (Option 2)
**Why it won't work:**
1. Claude's vision already does shape detection better than OpenCV on varied datasheet styles
2. Datasheet quality varies wildly—CV parameters would need constant tuning
3. OCR (Tesseract) struggles with technical drawing fonts and special symbols (⌀, ±)
4. Adds system dependencies (Tesseract install) complicating deployment
5. 4-5 days of work for likely worse results than prompt engineering

**Evidence:** The current system's failures aren't "can't see the shapes"—it's "sees shapes but misinterprets dimensions." CV doesn't help with interpretation.

### Dimension Line Detection (Option 3)
**Why it won't work:**
1. Dimension line notation varies between manufacturers
2. Arrow styles, extension lines, and leader lines have many formats
3. Table-variable format doesn't use dimension lines at all
4. Would require building a full CAD drawing parser

### Ensemble Voting (Option 7)
**Why it won't work:**
1. 3x cost ($0.06/extraction) exceeds budget target
2. If all approaches have the same bias (pitch vs pad confusion), voting doesn't help
3. Complexity of implementing vote reconciliation

---

## Testing Protocol

### Test Dataset (5 examples)
1. **ATECC608A** (SMD, table-variable, thermal+vias) - EXISTING
2. **RJ45 Connector** (TH, mixed pad sizes, mounting holes) - EXISTING
3. **USB 3.0** (TH, slotted holes) - EXISTING
4. **M.2 Mini PCIe** (SMD edge connector, 79 pads, 0.5mm pitch) - EXISTING
5. **SO-8EP** (SMD with thermal pad) - EXISTING

### Metrics Per Extraction

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Pad count | Exact match | Count comparison |
| Pad positions | ±0.1mm | Euclidean distance from ground truth |
| Pad dimensions | ±0.05mm | Absolute difference |
| Pin 1 correct | 100% | Boolean |
| Thermal pad detected | 100% | Boolean |
| Via count | Exact | Count comparison |

### A/B Test Structure

```
Run 1: Current single-shot (baseline)
Run 2: Parse-Then-Extract pipeline
Run 3: Pipeline + verification pass
Run 4: Pipeline + verification + user hints (if needed)

Each run: 3 extractions per test image (account for variance)
Compare: mean accuracy, std deviation, cost
```

### Stopping Criteria

- **Abandon Parse-Then-Extract if:** <10% improvement on 3+ test images after Day 2
- **Abandon verification pass if:** <5% error correction rate
- **Ship if:** Overall accuracy >85% on test suite

---

## Cost Analysis

| Approach | Estimated Cost/Extraction | Notes |
|----------|--------------------------|-------|
| Current (Sonnet single-shot) | ~$0.02 | Baseline |
| Parse-Then-Extract | ~$0.025 | Stage 1: Haiku, Stage 2: Sonnet |
| + Verification | ~$0.03 | Haiku verification pass |
| + User hints | ~$0.03 | No additional API cost |

All options within $0.05 budget target.

---

## Implementation Files to Create/Modify

```
backend/
  prompts_staged.py      # NEW: Stage 1 + Stage 2 prompts
  extraction_staged.py   # NEW: Pipeline orchestration
  verification.py        # NEW: Self-verification pass
  extraction.py          # MODIFY: Add pipeline option flag

frontend/
  src/components/
    ConfidenceIndicator.jsx  # NEW: Color-coded confidence display
    PitchConfirmDialog.jsx   # NEW: User hint for pitch
```

---

## Next Steps

1. **Day 1:** Implement Stage 1 (table parsing) prompt and test on ATECC608A
2. **Day 2:** Implement Stage 2 (geometry extraction) with table context
3. **Day 3:** Run full test suite, measure improvement
4. **Day 4:** Add verification pass if needed
5. **Day 5:** Add user hints for remaining edge cases
6. **Day 6-7:** Polish, integrate with frontend, test end-to-end

---

## Final Recommendation

**Implement in this order:**

1. **Parse-Then-Extract Pipeline** (Days 1-3) - Highest impact, addresses 3 of 4 failure modes
2. **Verification Pass** (Day 4) - Catches remaining pad vs pitch errors
3. **User Hints** (Day 5) - Escape hatch for edge cases

**Skip:** CV preprocessing, dimension line detection, ensemble voting (all over-engineered for this problem)
