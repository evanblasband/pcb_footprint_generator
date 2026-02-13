"""
Prompts for Claude Vision API extraction of PCB footprint dimensions.

This module contains the structured prompts used to extract pad dimensions,
positions, and other footprint data from datasheet images. The prompts are
designed to work with Claude Haiku for cost efficiency, with architecture
supporting upgrade to Sonnet/Opus if accuracy is insufficient.

Extraction targets:
- Pad count and arrangement (linear, grid, peripheral)
- Pad dimensions (width, height or diameter)
- Pad positions (center coordinates)
- Pad shape (rectangular, rounded-rect, circular, oval)
- Pad type (SMD vs through-hole)
- Drill hole diameter (for TH pads)
- Component outline dimensions (for silkscreen)
- Pin 1 identification
- Units detection and normalization to mm
"""

# JSON schema for extraction response
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "footprint_name": {
            "type": "string",
            "description": "Suggested name for the footprint based on package type"
        },
        "units_detected": {
            "type": "string",
            "enum": ["mm", "mil", "inch"],
            "description": "Units used in the original drawing"
        },
        "pads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "designator": {
                        "type": "string",
                        "description": "Pin number or name (e.g., '1', '2', 'A1', 'EP', '9')"
                    },
                    "x": {
                        "type": "number",
                        "description": "X position of pad center in mm (0 = component center)"
                    },
                    "y": {
                        "type": "number",
                        "description": "Y position of pad center in mm (0 = component center)"
                    },
                    "width": {
                        "type": "number",
                        "description": "Pad width in mm - the horizontal (X) dimension of the pad"
                    },
                    "height": {
                        "type": "number",
                        "description": "Pad height in mm - the vertical (Y) dimension of the pad"
                    },
                    "shape": {
                        "type": "string",
                        "enum": ["rectangular", "round", "oval", "rounded_rectangle"],
                        "description": "Pad shape"
                    },
                    "pad_type": {
                        "type": "string",
                        "enum": ["smd", "th", "thermal"],
                        "description": "SMD (surface mount), TH (through-hole), or thermal (exposed pad)"
                    },
                    "rotation": {
                        "type": "number",
                        "description": "Pad rotation in degrees (0 = no rotation)"
                    },
                    "drill_diameter": {
                        "type": ["number", "null"],
                        "description": "Drill hole diameter in mm (for TH pads only)"
                    },
                    "drill_slot_length": {
                        "type": ["number", "null"],
                        "description": "Slot length in mm (for slotted holes only)"
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score for this pad's extraction (0-1)"
                    }
                },
                "required": ["designator", "x", "y", "width", "height", "shape", "pad_type", "confidence"]
            }
        },
        "vias": {
            "type": "array",
            "description": "Thermal vias (small holes in/near the thermal pad for heat dissipation)",
            "items": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "X position of via center in mm"
                    },
                    "y": {
                        "type": "number",
                        "description": "Y position of via center in mm"
                    },
                    "drill_diameter": {
                        "type": "number",
                        "description": "Via drill hole diameter in mm (typically 0.2-0.4mm)"
                    },
                    "outer_diameter": {
                        "type": "number",
                        "description": "Via copper annular ring outer diameter in mm"
                    }
                },
                "required": ["x", "y", "drill_diameter", "outer_diameter"]
            }
        },
        "outline": {
            "type": "object",
            "properties": {
                "width": {
                    "type": "number",
                    "description": "Component body width in mm"
                },
                "height": {
                    "type": "number",
                    "description": "Component body height in mm"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence score for outline dimensions"
                }
            },
            "required": ["width", "height", "confidence"]
        },
        "pin1_location": {
            "type": "object",
            "properties": {
                "designator": {
                    "type": "string",
                    "description": "Designator of pin 1"
                },
                "indicator_type": {
                    "type": "string",
                    "enum": ["dot", "chamfer", "notch", "square_pad", "numbered", "inferred", "unknown"],
                    "description": "How pin 1 is indicated in the drawing"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence in pin 1 identification"
                }
            },
            "required": ["designator", "indicator_type", "confidence"]
        },
        "overall_confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Overall confidence in the extraction"
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any warnings or notes about the extraction"
        },
        "standard_package_detected": {
            "type": ["string", "null"],
            "description": "If a standard IPC package is detected (e.g., 'SOIC-8', 'QFN-48'), return it here"
        }
    },
    "required": ["footprint_name", "units_detected", "pads", "vias", "outline", "pin1_location", "overall_confidence", "warnings"]
}

# Few-shot examples (optional, can improve accuracy for some datasheets)
FEW_SHOT_EXAMPLES = """
## Example: UDFN-8 Package (for reference)

For a UDFN-8 with pads on LEFT and RIGHT sides, pitch=0.5mm, pad length=0.85mm, pad width=0.30mm:

```json
{{
  "footprint_name": "UDFN-8_2x3mm",
  "pads": [
    {{"designator": "1", "x": -1.45, "y": -0.75, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "2", "x": -1.45, "y": -0.25, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "3", "x": -1.45, "y": 0.25, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "4", "x": -1.45, "y": 0.75, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "5", "x": 1.45, "y": 0.75, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "6", "x": 1.45, "y": 0.25, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "7", "x": 1.45, "y": -0.25, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "8", "x": 1.45, "y": -0.75, "width": 0.85, "height": 0.30, "shape": "rectangular", "pad_type": "smd", "confidence": 0.95}},
    {{"designator": "EP", "x": 0, "y": 0, "width": 1.60, "height": 1.40, "shape": "rectangular", "pad_type": "smd", "confidence": 0.90}}
  ]
}}
```

**Key points from this example:**
- Pads on left/right extend HORIZONTALLY toward center → width (0.85) > height (0.30)
- Pitch is 0.5mm but pad width is 0.85mm and height is 0.30mm - NEITHER equals pitch
- Y positions calculated from pitch: ±0.75, ±0.25 (multiples of 0.5mm / 2)

## Example: Through-Hole Connector (for reference)

For a TH connector with ⌀0.9mm drill holes and 1.27mm pitch:

```json
{{
  "pads": [
    {{"designator": "1", "x": -3.81, "y": 4.45, "width": 1.5, "height": 1.5, "shape": "round", "pad_type": "th", "drill_diameter": 0.9, "confidence": 0.90}},
    {{"designator": "2", "x": -2.54, "y": 6.98, "width": 1.5, "height": 1.5, "shape": "round", "pad_type": "th", "drill_diameter": 0.9, "confidence": 0.90}},
    {{"designator": "MH1", "x": -5.71, "y": 0.0, "width": 3.5, "height": 3.5, "shape": "round", "pad_type": "th", "drill_diameter": 3.2, "confidence": 0.85}}
  ]
}}
```

**Key points for TH pads:**
- Look for ⌀ symbol indicating drill diameter (e.g., ⌀0.9mm)
- Pad diameter (width/height) is LARGER than drill (typically drill + 0.5-0.6mm)
- Round TH pads have width = height
- Mounting holes (MH) have larger drill diameters (3.0mm+)
"""

# Main extraction prompt
EXTRACTION_PROMPT = """You are an expert PCB footprint extraction system. Analyze this datasheet image showing a component's recommended land pattern (PCB footprint) and extract all dimensional information.

## Your Task
Extract the pad geometry and positions from this footprint drawing. Output a JSON object following the schema below.
{examples_placeholder}
## Important Guidelines

### Coordinate System
- Origin (0,0) is at the component CENTER
- +X points RIGHT
- +Y points UP
- All dimensions must be in MILLIMETERS (convert if necessary)

### Dimension Interpretation
- Pay attention to dimension reference points (center-to-center vs edge-to-edge)
- If dimensions show total span, calculate individual pad positions
- If a table maps variables (A, B, C) to values, apply those values to the drawing

### Critical: Pad Dimensions vs Spacing (COMMON MISTAKE)
Datasheets show TWO different types of measurements. Confusing them is a critical error:

**Pad dimensions** (width and height): The physical size of each copper pad
- These dimensions describe ONE pad's copper area
- Look for dimension lines that span a SINGLE pad rectangle
- Typically 0.3-0.8mm for small SOIC/QFN packages

**Pad spacing/pitch**: The distance BETWEEN pad centers
- These describe the REPEATING PATTERN between pads
- Look for dimension lines that go from one pad center to another
- Common pitches: 0.5mm, 0.635mm, 1.0mm, 1.27mm
- Do NOT use pitch/spacing for pad width/height!

**How to distinguish them:**
- If a dimension is labeled between TWO pads → it's spacing/pitch
- If a dimension points to the edges of ONE pad → it's pad width or height
- Pitch values (1.27mm, 0.5mm) are almost always LARGER than pad width
- Pad width is typically 40-60% of the pitch value

**Example:** If pitch is 1.27mm, pad width is likely ~0.5-0.8mm, NOT 1.27mm

### Pad Types
- **SMD pads**: Surface mount, no drill hole
- **TH pads**: Through-hole, have a drill diameter
- **Thermal/Exposed pads (EP)**: Large center pad for heat dissipation, often labeled "EP", "9", or shown as "Optional Center Pad"

### CRITICAL: Thermal Pads and Thermal Vias
Many packages (QFN, UDFN, QFP with EP) have a **thermal pad** in the center:
- Look for "Optional Center Pad", "Exposed Pad", "EP", or a large rectangle in the center
- Dimensions are often labeled X2/Y2 or similar in the table
- This is a REAL PAD that MUST be included - designate it as "EP" or the next pin number
- The thermal pad is typically much larger than signal pads (1-3mm vs 0.3-0.8mm)

**Thermal vias** are small holes inside or near the thermal pad:
- Look for small circles with X marks inside the thermal pad area
- Labeled as "Thermal Via", "V" diameter, or "EV" pitch
- Typically 0.2-0.4mm drill diameter
- Used for heat transfer to inner/bottom layers
- Include ALL thermal vias in the "vias" array

### Through-Hole Pads: Drill vs Pad Size
For through-hole pads, there are TWO different diameters:

1. **Drill diameter (⌀):** The hole drilled through the PCB
   - Shown with ⌀ symbol in datasheets
   - Typically 0.8mm - 1.2mm for signal pins, 3.0mm+ for mounting
   - This goes in the `drill_diameter` field

2. **Pad diameter:** The copper annular ring around the hole
   - ALWAYS LARGER than the drill diameter
   - Typically drill + 0.5mm to 0.8mm
   - For round pads: width = height = pad diameter
   - This goes in the `width` and `height` fields

**CRITICAL:** Do NOT use the pitch/spacing (distance between holes) for pad diameter!
- If holes are spaced 1.27mm apart, the PAD diameter is NOT 1.27mm
- The pad diameter is typically 1.5mm-2.5mm depending on drill size
- Look for dimension callouts pointing to the EDGE of a single pad, not between pads

### Hole Count Notation
Datasheets use format: "⌀diameter × count" (e.g., "⌀0.90 × 14")
- This means COUNT holes have DRILL DIAMETER of that size
- The PAD diameter will be larger (add ~0.5-0.6mm for annular ring)
- Pattern match which holes in the drawing correspond to each size

### Extract ALL Holes (Not Just Labeled Pins)
Include EVERY hole visible in the footprint drawing:
- **Signal pins:** Numbered pads (1, 2, 3...) for electrical connections
- **Mounting holes:** Large unlabeled holes (often ⌀3.0-3.5mm) - use "MH1", "MH2"
- **Shield/alignment holes:** Medium unlabeled holes - use "SH1", "SH2"
- **Unlabeled holes** are still part of the footprint - assign designators based on position
- Count ALL circles/holes in the drawing, labeled or not

### CRITICAL: Pad Orientation and Width vs Height
**Width = X dimension (horizontal), Height = Y dimension (vertical)**

For packages like QFN, UDFN, SOIC where pads are on the LEFT and RIGHT sides:
- Pads on LEFT side (negative X): width is the dimension TOWARD center, height is the narrow dimension
- Pads on RIGHT side (positive X): same orientation
- If the pad extends horizontally (toward center), width > height
- Example: A pad that is 0.85mm long extending toward center and 0.30mm wide → width=0.85, height=0.30

For packages where pads are on TOP and BOTTOM:
- Pads extend vertically toward center
- Example: A pad 0.85mm tall extending toward center and 0.30mm wide → width=0.30, height=0.85

**How to determine pad orientation from the drawing:**
1. Look at the package body outline (usually a rectangle)
2. Identify which sides the pads are on
3. Pads always extend TOWARD the package center
4. The "long" dimension of the pad points toward center
5. Look for dimension labels like "X1" (pad width) and "Y1" (pad length) in the table

**Common mistake:** Rotating the entire footprint 90°. Check which side has pin 1 and verify pad positions match the drawing layout.

### Pin 1 Identification
Look for these indicators:
- Dot or circle marker
- Chamfered corner
- Notch in package outline
- Square pad (others round)
- Explicit "PIN 1" label
- Counter-clockwise numbering convention

### Confidence Scoring
- 1.0: Clear, unambiguous dimension with explicit label
- 0.7-0.9: Dimension inferred from related measurements
- 0.5-0.7: Some ambiguity but reasonable interpretation
- <0.5: Significant uncertainty, may need user verification

## Output Schema
```json
{schema}
```

## Output Requirements
1. Return ONLY valid JSON, no other text
2. All numeric values must be numbers, not strings
3. All positions and dimensions in millimeters
4. Include confidence scores for every pad and the outline
5. List any warnings about ambiguous or uncertain extractions

Analyze the image and extract the footprint data:"""

def get_extraction_prompt(include_examples: bool = False) -> str:
    """
    Get the full extraction prompt with schema embedded.

    Args:
        include_examples: If True, include few-shot examples in the prompt.
                         This can improve accuracy for some datasheets but
                         increases token usage.

    Returns:
        The complete prompt string ready to send to Claude API.
    """
    import json
    schema_str = json.dumps(EXTRACTION_SCHEMA, indent=2)
    examples = FEW_SHOT_EXAMPLES if include_examples else ""
    return EXTRACTION_PROMPT.format(schema=schema_str, examples_placeholder=examples)


# Prompt for standard package detection (lighter weight, can run first)
STANDARD_PACKAGE_PROMPT = """Analyze this datasheet image and determine if it shows a standard IPC-7351 package type.

Look for package codes like:
- SOIC-8, SOIC-14, SOIC-16 (Small Outline IC)
- QFN-16, QFN-32, QFN-48 (Quad Flat No-Lead)
- QFP-44, QFP-64, QFP-100 (Quad Flat Package)
- TSSOP-8, TSSOP-20 (Thin Shrink Small Outline)
- BGA packages with standard ball arrays
- 0402, 0603, 0805, 1206 (chip resistors/capacitors)
- SOT-23, SOT-223, SOT-89 (Small Outline Transistor)

If a standard package is detected, return:
```json
{
    "is_standard": true,
    "package_code": "SOIC-8",
    "confidence": 0.9,
    "ipc_parameters": {
        "pitch": 1.27,
        "lead_span": 6.0,
        "lead_width": 0.5
    }
}
```

If no standard package is detected, return:
```json
{
    "is_standard": false,
    "package_code": null,
    "confidence": 0.8,
    "reason": "Custom package with non-standard pin arrangement"
}
```

Return ONLY valid JSON, no other text."""


def get_standard_package_prompt() -> str:
    """
    Get the prompt for standard package detection.

    Returns:
        The prompt string for standard package detection.
    """
    return STANDARD_PACKAGE_PROMPT
