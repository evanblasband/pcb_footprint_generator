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
                        "description": "Pin number or name (e.g., '1', '2', 'A1', 'GND')"
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
                        "description": "Pad width in mm (X dimension)"
                    },
                    "height": {
                        "type": "number",
                        "description": "Pad height in mm (Y dimension)"
                    },
                    "shape": {
                        "type": "string",
                        "enum": ["rectangular", "round", "oval", "rounded_rectangle"],
                        "description": "Pad shape"
                    },
                    "pad_type": {
                        "type": "string",
                        "enum": ["smd", "th"],
                        "description": "SMD (surface mount) or TH (through-hole)"
                    },
                    "rotation": {
                        "type": "number",
                        "description": "Pad rotation in degrees (0 = horizontal)"
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
    "required": ["footprint_name", "units_detected", "pads", "outline", "pin1_location", "overall_confidence", "warnings"]
}

# Main extraction prompt
EXTRACTION_PROMPT = """You are an expert PCB footprint extraction system. Analyze this datasheet image showing a component's recommended land pattern (PCB footprint) and extract all dimensional information.

## Your Task
Extract the pad geometry and positions from this footprint drawing. Output a JSON object following the schema below.

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
- SMD pads: Surface mount, no drill hole
- TH pads: Through-hole, have a drill diameter

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

def get_extraction_prompt() -> str:
    """
    Get the full extraction prompt with schema embedded.

    Returns:
        The complete prompt string ready to send to Claude API.
    """
    import json
    schema_str = json.dumps(EXTRACTION_SCHEMA, indent=2)
    return EXTRACTION_PROMPT.format(schema=schema_str)


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
