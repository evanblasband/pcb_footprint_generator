"""
Staged extraction prompts for improved accuracy.

This module implements a 2-stage extraction pipeline:
- Stage 1: Scene analysis and dimension table parsing (uses Haiku for cost)
- Stage 2: Geometry extraction with table context (uses Sonnet for accuracy)

The key insight is that separating "parse the table" from "apply dimensions to shapes"
reduces the cognitive load on each prompt and improves accuracy, especially for
table-variable format datasheets where dimensions are shown as labels (X1, Y1, etc.)
that map to values in a table.
"""

import json

# =============================================================================
# Stage 1: Scene Analysis + Table Parsing
# =============================================================================
# Goal: Extract metadata about the drawing format and parse any dimension tables
# Model: Haiku (cheap, sufficient for structured extraction)
# =============================================================================

STAGE1_SCHEMA = {
    "type": "object",
    "properties": {
        "drawing_format": {
            "type": "string",
            "enum": ["table_variable", "inline", "mixed"],
            "description": "table_variable = dimensions shown as labels (A, B, X1) with table mapping to values; inline = values shown directly on drawing; mixed = both"
        },
        "dimension_table": {
            "type": "object",
            "description": "Mapping of dimension labels to their values in mm. Extract NOM/TYP values. Example: {'X1': 0.30, 'X2': 1.60, 'Y1': 0.85}",
            "additionalProperties": {"type": "number"}
        },
        "package_type": {
            "type": "string",
            "description": "Package type: UDFN, QFN, SOIC, TSSOP, BGA, TH_CONNECTOR, MIXED, CUSTOM, etc."
        },
        "pad_arrangement": {
            "type": "string",
            "enum": ["peripheral", "linear_rows", "grid", "dual_row", "edge_connector", "custom"],
            "description": "How pads are arranged: peripheral (QFN/QFP), linear_rows (SOIC), grid (BGA), dual_row (TH connector), edge_connector (M.2/PCIe)"
        },
        "estimated_pad_count": {
            "type": "integer",
            "description": "Approximate number of pads visible in drawing"
        },
        "has_thermal_pad": {
            "type": "boolean",
            "description": "True if there's a center exposed/thermal pad"
        },
        "has_thermal_vias": {
            "type": "boolean",
            "description": "True if thermal vias are visible in/near thermal pad"
        },
        "units_detected": {
            "type": "string",
            "enum": ["mm", "mil", "inch", "mixed", "unknown"],
            "description": "Units used in the drawing"
        },
        "dimension_semantics": {
            "type": "object",
            "description": "For each dimension variable, what it likely represents",
            "properties": {
                "pad_width_label": {"type": "string", "description": "Label for pad width (e.g., 'X1', 'b')"},
                "pad_height_label": {"type": "string", "description": "Label for pad height/length (e.g., 'Y1', 'L')"},
                "pitch_label": {"type": "string", "description": "Label for pad pitch/spacing (e.g., 'E', 'e')"},
                "thermal_width_label": {"type": "string", "description": "Label for thermal pad width (e.g., 'X2', 'D2')"},
                "thermal_height_label": {"type": "string", "description": "Label for thermal pad height (e.g., 'Y2', 'E2')"}
            }
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any ambiguities or issues noticed"
        }
    },
    "required": ["drawing_format", "dimension_table", "package_type", "pad_arrangement",
                 "estimated_pad_count", "has_thermal_pad", "units_detected"]
}

STAGE1_PROMPT = """You are analyzing a PCB component datasheet image to extract metadata and parse dimension tables.

## Your Task
Analyze this datasheet image and extract:
1. The drawing format (table-variable vs inline dimensions)
2. The dimension table (if present) - mapping labels to values
3. Package type and pad arrangement
4. What each dimension label represents

## Understanding Drawing Formats

### Table-Variable Format
The drawing shows dimension LABELS (X1, Y1, E, G1, etc.) pointing to features, with a separate table mapping labels to numeric values:
```
Table:
| Symbol | MIN | NOM | MAX |
|--------|-----|-----|-----|
| X1     | 0.25| 0.30| 0.35|
| Y1     | 0.80| 0.85| 0.90|
| E      |     | 0.50|     |
```
For table-variable format, extract the NOM (nominal) or TYP (typical) values.

### Inline Format
Dimensions are shown directly on the drawing with numeric values (e.g., "0.50" pointing to a feature).

## Common Dimension Label Semantics

For UDFN/QFN/SOIC packages, labels typically mean:
- **X1, b, W** → Pad WIDTH (horizontal dimension of copper pad) - typically 0.2-0.5mm
- **Y1, L** → Pad HEIGHT/LENGTH (vertical dimension) - typically 0.3-1.5mm
- **X2, D2** → Thermal pad WIDTH
- **Y2, E2** → Thermal pad HEIGHT
- **E, e, pitch** → Pad PITCH (spacing between pad centers) - NOT pad size!
- **G, G1** → Distance from pad center to package center
- **C** → Total pad-to-pad span
- **V** → Via diameter
- **EV** → Via pitch

## CRITICAL DISTINCTION: Pitch vs Pad Size
- **Pitch (E, e)** = distance between pad CENTERS (e.g., 0.5mm, 1.27mm)
- **Pad width (X1, b)** = width of ONE pad's copper (typically 40-70% of pitch)
- If E = 0.50mm, the pad width is probably 0.25-0.35mm, NOT 0.50mm

## Output Schema
```json
{schema}
```

Return ONLY valid JSON, no other text. Analyze the image and extract the metadata:"""


def get_stage1_prompt() -> str:
    """
    Get the Stage 1 prompt for scene analysis and table parsing.

    Returns:
        Complete prompt string with schema embedded.
    """
    schema_str = json.dumps(STAGE1_SCHEMA, indent=2)
    return STAGE1_PROMPT.format(schema=schema_str)


# =============================================================================
# Stage 2: Geometry Extraction with Table Context
# =============================================================================
# Goal: Extract precise pad geometry using the parsed dimension values
# Model: Sonnet (accuracy is critical for geometry)
# =============================================================================

STAGE2_SCHEMA = {
    "type": "object",
    "properties": {
        "footprint_name": {
            "type": "string",
            "description": "Suggested footprint name based on package"
        },
        "pads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "designator": {"type": "string", "description": "Pin number (1, 2, 3...) or EP for thermal pad"},
                    "x": {"type": "number", "description": "X position of pad CENTER in mm (origin at component center)"},
                    "y": {"type": "number", "description": "Y position of pad CENTER in mm (origin at component center)"},
                    "width": {"type": "number", "description": "Pad width (X dimension) in mm"},
                    "height": {"type": "number", "description": "Pad height (Y dimension) in mm"},
                    "shape": {"type": "string", "enum": ["rectangular", "round", "oval", "rounded_rectangle"]},
                    "pad_type": {"type": "string", "enum": ["smd", "th"]},
                    "rotation": {"type": "number", "description": "Rotation in degrees (0 = no rotation)"},
                    "drill_diameter": {"type": ["number", "null"], "description": "For TH pads only"},
                    "drill_slot_length": {"type": ["number", "null"], "description": "For slotted holes only"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["designator", "x", "y", "width", "height", "shape", "pad_type", "confidence"]
            }
        },
        "vias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "drill_diameter": {"type": "number"},
                    "outer_diameter": {"type": "number"}
                },
                "required": ["x", "y", "drill_diameter", "outer_diameter"]
            }
        },
        "outline": {
            "type": "object",
            "properties": {
                "width": {"type": "number"},
                "height": {"type": "number"}
            }
        },
        "pin1_location": {
            "type": "object",
            "properties": {
                "designator": {"type": "string"},
                "indicator_type": {"type": "string", "enum": ["dot", "chamfer", "notch", "square_pad", "numbered", "inferred"]},
                "confidence": {"type": "number"}
            }
        },
        "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "warnings": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["footprint_name", "pads", "vias", "outline", "pin1_location", "overall_confidence"]
}

STAGE2_PROMPT_TEMPLATE = """You are extracting precise PCB footprint geometry from a datasheet image.

## Stage 1 Analysis (Already Completed)
The image has been analyzed and the following was determined:

**Drawing Format:** {drawing_format}
**Package Type:** {package_type}
**Pad Arrangement:** {pad_arrangement}
**Estimated Pad Count:** {estimated_pad_count}
**Has Thermal Pad:** {has_thermal_pad}
**Has Thermal Vias:** {has_thermal_vias}
**Units:** {units_detected}

**Dimension Table (parsed values):**
{dimension_table_formatted}

**Dimension Semantics (what each label means):**
{dimension_semantics_formatted}

## Your Task
Using the dimension values above, extract the COMPLETE footprint geometry:
1. Calculate exact pad positions using the parsed dimension values
2. Create ALL pads (including thermal pad if present)
3. Create thermal vias if present
4. Identify Pin 1 location

## Coordinate System
- Origin (0,0) is at the COMPONENT CENTER
- +X points RIGHT
- +Y points UP
- All dimensions in MILLIMETERS

## CRITICAL: Using the Dimension Table Correctly

You MUST use the parsed dimension values from Stage 1. Do NOT re-read values from the image.

For this {package_type} package with {pad_arrangement} arrangement:
{dimension_usage_guide}

## Example Pad Position Calculation for UDFN/QFN

If pitch (E) = 0.5mm and there are 4 pads per side:
- Pad 1: y = +1.5 * 0.5 = +0.75mm
- Pad 2: y = +0.5 * 0.5 = +0.25mm
- Pad 3: y = -0.5 * 0.5 = -0.25mm
- Pad 4: y = -1.5 * 0.5 = -0.75mm

The X position comes from G1 (pad center to component center distance).

## Via Grid Calculation

If via pitch (EV) = 1.0mm and thermal pad has room for a 2x2 grid:
- Via 1: (x=-0.5, y=+0.5)
- Via 2: (x=+0.5, y=+0.5)
- Via 3: (x=-0.5, y=-0.5)
- Via 4: (x=+0.5, y=-0.5)

## Output Schema
```json
{schema}
```

Return ONLY valid JSON. Extract the complete footprint geometry:"""


def get_stage2_prompt(stage1_result: dict) -> str:
    """
    Get the Stage 2 prompt for geometry extraction with Stage 1 context.

    Args:
        stage1_result: Output from Stage 1 analysis containing dimension table
                       and package metadata.

    Returns:
        Complete prompt string with Stage 1 context and schema embedded.
    """
    # Format dimension table
    dim_table = stage1_result.get("dimension_table", {})
    dim_table_lines = [f"  - {k} = {v}mm" for k, v in dim_table.items()]
    dimension_table_formatted = "\n".join(dim_table_lines) if dim_table_lines else "  (no table found)"

    # Format dimension semantics
    semantics = stage1_result.get("dimension_semantics", {})
    sem_lines = [f"  - {k}: {v}" for k, v in semantics.items() if v]
    dimension_semantics_formatted = "\n".join(sem_lines) if sem_lines else "  (no semantics identified)"

    # Generate dimension usage guide based on package type
    pkg_type = stage1_result.get("package_type", "").upper()
    has_thermal = stage1_result.get("has_thermal_pad", False)
    has_vias = stage1_result.get("has_thermal_vias", False)

    # Get specific dimension labels
    pad_width_label = semantics.get("pad_width_label", "X1")
    pad_height_label = semantics.get("pad_height_label", "Y1")
    pitch_label = semantics.get("pitch_label", "E")
    thermal_width_label = semantics.get("thermal_width_label", "X2")
    thermal_height_label = semantics.get("thermal_height_label", "Y2")

    usage_guide = f"""
**For signal pads:**
- Pad width = {pad_width_label} = {dim_table.get(pad_width_label, '?')}mm
- Pad height = {pad_height_label} = {dim_table.get(pad_height_label, '?')}mm
- Pitch (spacing) = {pitch_label} = {dim_table.get(pitch_label, '?')}mm
- Use pitch to calculate Y positions of pads on left/right sides
"""

    if has_thermal:
        usage_guide += f"""
**For thermal pad (designate as 'EP' or '9'):**
- Width = {thermal_width_label} = {dim_table.get(thermal_width_label, '?')}mm
- Height = {thermal_height_label} = {dim_table.get(thermal_height_label, '?')}mm
- Position at center (x=0, y=0)
"""

    if has_vias:
        v_label = "V"
        ev_label = "EV"
        usage_guide += f"""
**For thermal vias:**
- Via drill diameter = {v_label} = {dim_table.get(v_label, dim_table.get('V', '?'))}mm
- Via pitch = {ev_label} = {dim_table.get(ev_label, dim_table.get('EV', '?'))}mm
- Calculate grid positions based on pitch within thermal pad area
- Outer diameter = drill + 0.3mm (typical annular ring)
"""

    # Build final prompt
    schema_str = json.dumps(STAGE2_SCHEMA, indent=2)

    return STAGE2_PROMPT_TEMPLATE.format(
        drawing_format=stage1_result.get("drawing_format", "unknown"),
        package_type=stage1_result.get("package_type", "unknown"),
        pad_arrangement=stage1_result.get("pad_arrangement", "unknown"),
        estimated_pad_count=stage1_result.get("estimated_pad_count", "unknown"),
        has_thermal_pad=stage1_result.get("has_thermal_pad", False),
        has_thermal_vias=stage1_result.get("has_thermal_vias", False),
        units_detected=stage1_result.get("units_detected", "mm"),
        dimension_table_formatted=dimension_table_formatted,
        dimension_semantics_formatted=dimension_semantics_formatted,
        dimension_usage_guide=usage_guide,
        schema=schema_str,
    )
