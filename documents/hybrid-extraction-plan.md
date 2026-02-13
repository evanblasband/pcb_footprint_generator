# Hybrid Extraction Architecture - Exploration Plan

## Context

The current single-shot AI extraction approach has limitations:
- Prompt engineering can't cover every datasheet format variation
- No learning/improvement over time without fine-tuning
- AI conflates different types of information (dimensions vs. spacing)
- Hard to debug why extraction failed

**Goals:** Improve accuracy AND coverage, minimal user interaction (prompt for hints when stuck)

---

## Architecture Options Considered

### Option 1: Multi-Stage AI Pipeline
Break extraction into discrete stages, each with focused task.

```
Stage 1: Classification
├── Identify drawing type (land pattern, mechanical, package outline)
├── Detect if it's a table-variable format
└── Output: metadata about what we're looking at

Stage 2: Geometry Extraction
├── Identify all shapes (pads, holes, outlines)
├── Count pads, determine arrangement (linear, grid, peripheral)
└── Output: shape list with approximate positions

Stage 3: Dimension Extraction
├── Find all dimension annotations (lines, arrows, text)
├── OCR the numeric values
├── Identify what each dimension refers to
└── Output: list of (value, type, location)

Stage 4: Correlation & Assembly
├── Match dimensions to shapes
├── Resolve variable references (A=2.5mm, B=1.0mm)
├── Build final footprint
└── Output: complete extraction JSON
```

**Pros:**
- Each stage is simpler, easier to prompt
- Failures are easier to diagnose (which stage broke?)
- Stages can use different models (Haiku for simple, Sonnet for complex)
- Can add validation between stages

**Cons:**
- More API calls = higher cost/latency
- Information loss between stages
- Still pure AI, same fundamental limitations

---

### Option 2: Traditional CV + AI Correlation
Use classical computer vision to extract structure, AI to interpret.

```
Pre-processing (Traditional CV):
├── Edge detection (Canny)
├── Contour detection → find closed shapes (pads)
├── Hough transform → find lines (dimension lines)
├── Connected component analysis → find text regions
├── OCR (Tesseract) → extract all text/numbers
└── Output: shapes[], lines[], text_regions[]

AI Correlation:
├── Input: structured CV output + original image
├── Task: "Match these detected shapes to these dimensions"
├── Much simpler task than raw extraction
└── Output: correlated footprint data
```

**Pros:**
- CV provides deterministic, debuggable shape detection
- AI task is simpler (correlation vs. full extraction)
- Separation of concerns
- CV results can be validated independently

**Cons:**
- CV struggles with noisy/varied datasheet styles
- Dimension line detection is non-trivial (arrows, extension lines)
- Two systems to maintain
- May need to tune CV parameters per datasheet style

---

### Option 3: Dimension Line Detection Pipeline
Focus on extracting the dimension annotation system first.

Technical drawings use standard dimension notation:
```
    ←───── 2.54 ─────→
    |                 |
   ─┼─               ─┼─   (extension lines)
    │                 │
    ●                 ●    (pads)
```

**Pipeline:**
1. Detect dimension lines (horizontal/vertical lines with arrows)
2. Find associated text (the value)
3. Trace extension lines to what they measure
4. Build a constraint system
5. AI resolves ambiguities and assembles final geometry

---

### Option 4: Template-Based + AI Fallback
Handle common packages with templates, AI for custom only.

```
Detection Phase:
├── AI identifies package family (QFN, SOIC, TSSOP, TH header, etc.)
├── If standard package detected with high confidence:
│   └── Use parametric template (pitch, pin count, body size)
└── If custom/unknown:
    └── Fall back to full AI extraction
```

---

### Option 5: User-Guided Extraction
Make extraction interactive - user provides hints.

```
Step 1: User uploads image
Step 2: AI makes initial guess, shows overlay
Step 3: User clicks to:
├── Identify Pin 1
├── Mark one pad (AI infers rest from pattern)
├── Click two points + enter dimension (for scale)
├── Confirm/reject pad positions
Step 4: AI refines based on user input
Step 5: Iterate until correct
```

---

### Option 6: Hybrid Shape-First Pipeline
Detect shapes, then read dimensions separately.

```
Phase 1: Shape Detection (CV or AI)
├── Find all pad candidates (rectangles, circles)
├── Determine pattern (linear rows, grid, peripheral)
├── Identify thermal pad if present
├── Count elements
└── Output: shape_candidates[] with relative positions

Phase 2: Dimension Reading (AI)
├── Input: original image + "I see N pads in X pattern"
├── Focus only on reading numeric values
├── Associate values with shape properties
└── Output: dimensions[] with assignments

Phase 3: Assembly
├── Apply dimensions to shape geometry
├── Scale/position from known values
├── Validate consistency
└── Output: final footprint
```

**Key insight:** Separating "what shapes exist" from "what are their sizes" reduces confusion between spacing values and size values.

---

### Option 7: Ensemble / Confidence Voting
Run multiple extraction approaches, vote on results.

---

## Additional Ideas

**Anchor-Based Extraction:**
- Find reliable reference points first (package outline, pin 1 marker, mounting holes)
- Extract positions relative to anchors
- More robust to scaling/positioning errors

**Region Decomposition:**
- Segment image into: main drawing, dimension table, notes section
- Process each region with appropriate strategy
- Table-variable formats become: "parse table" + "apply to drawing"

**Verification Pass:**
- After initial extraction, ask AI to verify: "I extracted a pad at (-2.5, 1.9) with size 0.8x0.3. Looking at the image, is this correct?"
- Catches obvious errors before user sees them

---

## Exploration Strategy

**Approach:** Quick prototypes in parallel, compare on same test set, invest in winner

### Sprint 1: Prototype Both Approaches (3-4 days)

**Day 1-2: Multi-Stage AI Prototype**
```
backend/
  extraction_staged.py   # New staged extraction pipeline
```
- Implement 4-stage prompt chain
- Rough implementation, focus on testing hypothesis
- Run on 5 test datasheets, record metrics

**Day 2-3: CV-Enhanced Prototype**
```
backend/
  cv_preprocessing.py    # OpenCV shape/text detection
  extraction_hybrid.py   # CV + AI correlation
```
- Add dependencies: opencv-python, pytesseract
- Implement shape detection + OCR
- Create AI correlation prompt
- Run on same 5 test datasheets

**Day 4: Comparison & Analysis**
- Compare metrics: accuracy, cost, latency, failure modes
- Document which approach handles which cases better
- Identify if approaches are complementary

---

### Sprint 2: Refine Winning Approach + User Hints (2-3 days)

Based on Sprint 1 results:
- Invest in the better-performing approach
- Add confidence-based user prompting for edge cases
- Polish implementation, add error handling
- Update frontend to support hints if needed

---

## Implementation Details

### Experiment 1: Multi-Stage AI Pipeline

```python
# Stage 1: Scene Understanding
prompt_1 = """
Analyze this datasheet image and identify:
1. Drawing type (land pattern, mechanical, package outline)
2. Package style (QFN, SOIC, TH connector, etc.)
3. Dimension format (inline annotations vs table-variable)
4. Pad arrangement (linear rows, grid, peripheral)
5. Approximate pad count
6. Units visible (mm, mil, inch)

Return JSON: {type, style, format, arrangement, pad_count, units}
"""

# Stage 2: Geometry Extraction (informed by Stage 1)
prompt_2 = """
Given this is a {style} package with {arrangement} arrangement of ~{pad_count} pads:

Identify ALL pad shapes in the image:
- For each pad: approximate position (quadrant), shape type
- Identify thermal pad if present
- Identify any vias/holes

Return JSON: {pads: [{id, quadrant, shape, is_thermal}], has_vias}
"""

# Stage 3: Dimension Reading
prompt_3 = """
Read ALL dimension values visible in this image:
- For each: value, unit, what it measures (pad width, pitch, body size, etc.)
- If table-variable format, parse the table mapping

Return JSON: {dimensions: [{value, unit, measures, label}], table: {...}}
"""

# Stage 4: Assembly
prompt_4 = """
Given:
- Pad layout: {stage_2_output}
- Dimensions: {stage_3_output}
- Package type: {stage_1_output}

Assemble the complete footprint with precise coordinates.
Return the final extraction JSON schema.
"""
```

---

### Experiment 2: CV Pre-processing + AI

```python
import cv2
import numpy as np

def preprocess_datasheet(image):
    """Extract structural information using CV."""

    # Convert to grayscale, threshold
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    # Find contours (potential pads)
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    shapes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 100 or area > 50000:  # Filter noise and page borders
            continue

        # Approximate shape
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)

        # Classify shape
        if len(approx) == 4:
            shape_type = "rectangle"
        elif len(approx) > 6:
            shape_type = "circle"
        else:
            shape_type = "other"

        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        shapes.append({
            "type": shape_type,
            "bbox": [x, y, w, h],
            "area": area,
            "center": [x + w//2, y + h//2]
        })

    return {"shapes": shapes, "text_regions": [...]}

# Then pass to AI
prompt = """
I've pre-processed this datasheet image and detected:
- {len(shapes)} potential pad shapes
- Shape centers at: {centers}
- Text regions containing: {text_values}

Looking at the original image alongside this data:
1. Which detected shapes are actual pads?
2. What dimension does each text value correspond to?
3. Assemble the footprint using this information.
"""
```

**Libraries:**
- OpenCV for basic shape detection
- pytesseract for OCR
- Potentially: DocTR (document text recognition) for better text extraction

---

### Experiment 3: Hybrid with User Hints

```
Flow:
1. Run extraction (staged or CV-enhanced)
2. Calculate confidence scores for each element
3. If overall_confidence < 0.7:
   - Highlight uncertain elements in preview
   - Prompt: "Click to confirm Pin 1" or "Enter the pitch value"
4. Re-run extraction with user hints as constraints
5. Present final result
```

**User hint types:**
- Pin 1 location (click)
- Scale reference (two points + dimension)
- Pad count confirmation
- Pitch/spacing value

---

## Evaluation Framework

**Test Suite:**
1. ATECC608A.png (SMD + thermal + vias) - existing
2. Through-hole connector - need to add
3. QFN with table-variable format - need to find
4. SOIC standard package - need to find
5. Unusual/custom footprint - need to find

**Metrics per extraction:**
| Metric | Target |
|--------|--------|
| Pad count | Exact match |
| Pad positions | Within 0.1mm |
| Pad dimensions | Within 0.05mm |
| Shape types | Correct |
| Pin 1 | Correct |
| Thermal pad | Detected |
| Vias | Detected if present |

**Comparison:**
- Current single-shot vs Multi-stage vs CV-enhanced
- Cost per extraction (API tokens)
- Latency
- Failure modes

---

## Dependencies to Add

```
# requirements.txt additions
opencv-python>=4.8.0
pytesseract>=0.3.10
numpy>=1.24.0
```

**System requirement:** Tesseract OCR installed (`apt install tesseract-ocr`)

---

## Success Criteria

| Approach | Pad Count | Positions | Dimensions | Worth pursuing? |
|----------|-----------|-----------|------------|-----------------|
| Current single-shot | baseline | baseline | baseline | - |
| Multi-stage AI | +10%? | +20%? | +15%? | If yes to any |
| CV + AI hybrid | +15%? | +30%? | +20%? | If yes to any |

If neither significantly improves on baseline, consider:
- Combining elements of both
- More aggressive user hints
- Template-based approach for common packages
