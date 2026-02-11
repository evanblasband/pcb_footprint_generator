# PRD: AI PCB Footprint Generator

**Product Name:** FootprintAI (working title)  
**Document Owner:** Evan Blasband  
**Status:** Draft v0.1  
**Target:** MVP Demo for Arena AI

---

## Executive Summary

A web application that extracts PCB footprint data from component datasheets using AI vision and generates Altium Designer-compatible footprint files. Targets the gap where engineers encounter parts without existing library footprints—particularly custom/non-standard packages—and must manually create them from datasheet drawings.

**MVP Scope:** Single package type (non-standard/custom), image/PDF input, Altium ASCII output, user confirmation of extracted dimensions.

---

## Problem Statement

When an engineer selects a component without an existing PCB footprint:

1. They locate the "Recommended Land Pattern" or "PCB Layout" section in the datasheet
2. They manually interpret dimensional drawings (often inconsistent in format, units, reference points)
3. They create the footprint in their EDA tool pad-by-pad
4. Errors in interpretation → fabrication issues, rework, schedule slip

**Time cost:** 15-60 minutes per footprint depending on complexity  
**Error cost:** Incorrect footprint → board re-spin ($5K-50K+ depending on complexity and volume)  
**Frequency:** Engineers creating 5-20 custom footprints per project is common

**Why existing solutions fall short:**
- Manufacturer libraries incomplete for newer/custom parts
- IPC-7351 calculators only work for standard packages
- SnapEDA/Ultra Librarian coverage gaps on specialty parts
- Manual creation remains the fallback

---

## Proposed Solution

### High-Level Flow

```
User uploads datasheet image/PDF page(s)
    ↓
System detects if standard IPC-7351 package code present
    ↓
[If standard] → Prompt: "Detected QFN-48. Use IPC calculator, vision extraction, or exit?"
    ↓
[If vision extraction or non-standard] → AI extracts dimensions from drawing
    ↓
Display extracted values for user confirmation/editing
    ↓
User specifies pin names/numbers (AI suggests if context available)
    ↓
Generate Altium ASCII footprint file (.PcbLib or paste-ready)
    ↓
User downloads and imports to Altium
```

### Core Capabilities

**V1 MVP:**
- Image/PDF upload (user-cropped to relevant section)
- Vision-based dimension extraction (pad sizes, positions, pitch, outline)
- User confirmation/edit UI for extracted values
- Pin name/number input (manual, with AI suggestion if datasheet context available)
- Altium ASCII footprint generation (SMD pads, silkscreen outline)
- Download as importable file

**Deferred:**
- Full PDF parsing (multi-page search)
- Through-hole/mixed technology
- 3D model generation
- Paste mask/courtyard layers (use defaults)
- KiCad/Eagle/OrCAD export
- Batch processing
- **Thermal pads:** QFN/QFP exposed pads with paste mask windowing patterns — complex, deferred
- **Post-generation DRC:** Pad spacing validation, silkscreen clearance checks
- **IPC-7351C material conditions:** Automatic pad sizing adjustments per IPC spec

---

## Target Audience

**Primary:** Electrical hardware engineers using Altium Designer who encounter parts without existing footprints.

**Persona:** "Alex the Board Designer"
- Mid-level EE, 3-7 years experience
- Designs 2-4 boards per year
- Comfortable with Altium but not a librarian specialist
- Encounters 5-15 parts per project needing custom footprints
- Pain: Tedious, error-prone manual process; distraction from actual design work

---

## User Stories

### Story 1: Extract Footprint from Datasheet Image
> As Alex, I want to upload a screenshot of a datasheet's land pattern drawing so that I can get a footprint file without manually measuring and entering every dimension.

**Acceptance Criteria:**
- Upload PNG/JPG/PDF (single page)
- System extracts pad dimensions, positions, pitch
- See extracted values in editable form
- Confirm or correct values
- Download Altium-compatible file

### Story 2: Standard Package Detection
> As Alex, I want the system to tell me if the part uses a standard package so that I don't waste time on extraction when I could use Altium's IPC wizard.

**Acceptance Criteria:**
- System detects standard package codes (QFN-XX, SOIC-XX, etc.)
- Prompt with options: use IPC calculator, proceed with extraction, exit
- If user chooses IPC, display relevant parameters for Altium's wizard

### Story 3: Pin Assignment
> As Alex, I want to specify pin names/numbers for the footprint so that the schematic symbol links correctly.

**Acceptance Criteria:**
- UI to enter pin designators (1, 2, 3... or A1, A2, B1...)
- If datasheet context available, AI suggests pin names
- Validate pin count matches extracted pad count

---

## Key Features & Requirements

### 1. Input Processing

**Supported formats:** PNG, JPG, PDF (single page)  
**Assumed input:** User-cropped image containing the land pattern/recommended PCB layout drawing with dimensions

**Extraction targets:**
- Pad count and arrangement (linear, grid, peripheral)
- Pad dimensions (X, Y or diameter)
- Pad positions (center coordinates or pitch + origin)
- Pad shape (rectangular, rounded-rect, circular, oval)
- Pad type (SMD vs through-hole)
- Drill hole diameter (for TH pads)
- Component outline dimensions (for silkscreen)
- Units (mm, mils, inches) — normalize to mm

### 2. Standard Package Detection

**Method:** Rules-based pattern matching on extracted text + geometry
- Regex on package codes: `QFN`, `QFP`, `SOIC`, `TSSOP`, `BGA`, `0402`, `0603`, `SOT-23`, etc.
- If detected, present option to exit and use Altium's built-in IPC Footprint Wizard

**Rationale:** Avoid AI cost/error for cases where deterministic calculation suffices.

### 3. Vision-Based Extraction

**Model:** Start with Claude Haiku (vision) for cost efficiency. Architecture allows swapping to Sonnet/Opus or GPT-4V if accuracy insufficient.

**Prompt strategy:**
- Structured output request (JSON schema for pad array, dimensions, units)
- Few-shot examples of common drawing formats
- Request confidence scores per extracted value

**Known challenges:**
- Dimension leader lines pointing to wrong features
- Tolerance notations (±0.1) — extract nominal
- Inconsistent datum/origin references
- Mixed units in same drawing
- Rotated or skewed images
- **Dimension chaining:** Datasheets often provide total width + gap + pad width, not individual coordinates. AI must perform geometric reasoning to derive pad centers.
- **Table-variable mapping:** TI/ADI-style datasheets use generic drawings with variables (A, B, C) and lookup tables for package variants. AI must map table values to drawing dimensions.
- **Center-to-center vs edge-to-center:** Dimension reference points vary. Misinterpretation causes half-width offset errors.
- **Pin 1 identification:** Critical. Incorrect Pin 1 orientation renders footprint useless. Must detect Pin 1 markers (dot, chamfer, notch) or infer from pin numbering.

**Mitigation:** User confirmation step catches extraction errors before file generation. Pin 1 orientation gets explicit UI confirmation.

### 4. User Confirmation UI

**Display:**
- Visual preview of extracted footprint (2D pad layout)
- Table of extracted values (editable)
- Overlay on original image showing what was detected
- Warnings for suspicious values (e.g., pad larger than pitch)

**Editable fields:**
- Pad count, dimensions, positions
- Pitch (X and Y)
- Origin reference point
- Units

### 5. Pin Assignment

**Input:** Manual entry or paste from spreadsheet  
**Format:** Pin number → pad position mapping  
**AI assist:** If full datasheet context provided, attempt to extract pin names from pin description table

### 6. Footprint Generation

**Output format:** Altium Protel ASCII PCB Library format

**Internal units:** Altium uses 1/10000 mil (1/100,000 inch) internally. Generator must convert from mm.

**Generated elements:**
- SMD pads with correct size, shape, position (rectangular, circular, oval)
- Through-hole pads with drill hole diameter and annular ring
- Silkscreen outline (component boundary)
- Pin 1 indicator (dot or chamfer on silkscreen)
- Designator text placeholder
- Comment text placeholder

**Deferred elements (use Altium defaults post-import):**
- Solder paste mask (expansion/contraction)
- Solder mask expansion  
- Courtyard/assembly layers
- 3D body
- Thermal pad paste windowing

**File structure:** Single component in .PcbLib ASCII format, or ASCII primitives for paste operation.

### 7. Export & Download

- Download button generates file
- Filename: `{component_name}_footprint.PcbLib` or `.txt` for paste
- Include README with import instructions

---

## Technical Architecture

### Stack

**Frontend:** React + Tailwind CSS  
**Backend:** Python FastAPI  
**AI:** Anthropic API (Claude Haiku vision, upgradeable)  
**Hosting:** Railway  
**File generation:** Python library generating Altium ASCII format

### API Endpoints

```
POST /api/upload
  - Accepts image/PDF
  - Returns job_id

GET /api/extract/{job_id}
  - Returns extracted dimensions (JSON)
  - Includes confidence scores

POST /api/generate
  - Accepts confirmed dimensions + pin mapping
  - Returns footprint file (binary download)

GET /api/detect-standard
  - Accepts extracted text/geometry
  - Returns package classification + IPC parameters if standard
```

### Data Flow

```
[Browser] → Upload image → [FastAPI] → Store temp file
                                    → Call Claude Vision API
                                    → Parse response → structured dimensions
                                    → Return to browser

[Browser] → User edits/confirms → [FastAPI] → Generate ASCII footprint
                                           → Return file download
```

### Altium ASCII Format

Altium .PcbLib files are compound documents but support ASCII import via:
1. **ASCII PCB format:** Text representation of PCB primitives that can be pasted into PcbLib editor
2. **Script generation:** DelphiScript that creates footprint when run in Altium (more complex)

**Recommended approach:** Generate ASCII primitive list. User pastes into Altium's PcbLib editor or imports via script.

Example ASCII pad primitive:
```
PAD
  X=0mm
  Y=0mm
  XSIZE=0.5mm
  YSIZE=0.8mm
  SHAPE=RECTANGLE
  LAYER=MULTILAYER
  HOLE=0mm
  NAME=1
END
```

**Technical spike required:** Validate exact ASCII syntax accepted by Altium 23/24. Test import workflow.

---

## Technical Spikes (Pre-Build)

### Spike 1: Altium 26 ASCII Format Validation
**Goal:** Confirm ASCII footprint format imports correctly into Altium Designer 26.  
**Method:** Manually create test footprints (SMD rectangular, SMD oval, through-hole) in ASCII, import into Altium 26, verify pad properties including drill holes.  
**Output:** Documented format spec, working example files for each pad type.  
**Time:** 2-4 hours

### Spike 2: Vision Model Accuracy Test  
**Goal:** Assess Claude Haiku's ability to extract dimensions from datasheet drawings.  
**Method:** Run 5-10 sample datasheet images through Haiku, compare extracted values to ground truth.  
**Output:** Accuracy assessment, prompt refinement, decision on model tier.  
**Time:** 4-6 hours

### Spike 3: Dimension Extraction Prompt Engineering
**Goal:** Develop structured prompt that reliably extracts pad geometry.  
**Method:** Iterate on prompt with few-shot examples, test against varied drawing styles.  
**Output:** Production prompt template, JSON schema for response.  
**Time:** 4-8 hours

---

## MVP Scope Boundaries

### In Scope
- Single footprint extraction per session
- SMD rectangular/circular/oval pads
- Through-hole pads (drill holes, annular rings)
- Mixed SMD/TH footprints
- User-cropped input (no full PDF search)
- Manual pin naming with optional AI suggestion
- Altium 26 ASCII output only
- Web UI (no API-only mode)
- One package type validated end-to-end (targeting non-standard/custom)

### Out of Scope (Future)
- Through-hole pads (drill holes)
- Mixed SMD/TH footprints
- Full PDF parsing and page detection
- Batch processing multiple parts
- 3D model generation
- KiCad, Eagle, OrCAD export
- Paste mask/courtyard layer customization
- Direct Altium plugin integration
- User accounts/saved footprints

---

## Non-Functional Requirements

**Deterministic output:** Same input image + same confirmed dimensions must produce identical output file. No randomness in generation.

**Error states:** Clear UX for failure modes:
- "Could not detect any dimensional information" → prompt manual entry fallback
- "Multiple land patterns detected" → prompt user to select
- "Units ambiguous" → prompt user confirmation
- "Pin 1 marker not found" → require explicit user designation

**Processing latency:** Extraction + generation < 60 seconds for typical input.

**Security:** Uploaded datasheets processed in-memory, not persisted beyond session. No logging of proprietary content.

---

## Success Criteria

### Demo Success (MVP)
- End-to-end flow working: upload → extract → confirm → download → import to Altium
- At least one non-standard package type extracts correctly >70% of time
- Generated footprint imports into Altium without errors
- Extraction + generation completes in <60 seconds

### Accuracy Targets
- Dimension extraction within 0.05mm of ground truth for >70% of values
- Pad count correct 100% of time (user can verify/fix)
- User confirmation step catches remaining errors

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Vision model misreads dimensions | High | High | User confirmation UI; prompt engineering; model upgrade path |
| Altium ASCII format undocumented/fragile | Medium | High | Spike 1 validates before build; fallback to script generation |
| Varied datasheet drawing styles | High | Medium | Start with single style; expand prompt examples over time |
| Units confusion (mm vs mils) | Medium | High | Explicit unit detection; user confirmation; sanity checks |
| Complex pad shapes (custom outlines) | Low | Medium | MVP: rectangular/circular only; defer custom shapes |

---

## Open Questions

1. **Altium version targeting:** Altium 26 (confirmed).
2. **Example datasheets:** Need 5-10 representative samples covering target package types.
3. **Ground truth footprints:** Need known-good footprints for accuracy validation.
4. **Cost ceiling:** What's acceptable per-extraction API cost? ($0.01? $0.05? $0.10?)
5. **Error handling UX:** If extraction fails completely, what's the fallback? Manual entry form?

---

## Implementation Plan

### Phase 0: Spikes (Day 1)
- [ ] Spike 1: Altium ASCII format validation
- [ ] Spike 2: Vision model accuracy test
- [ ] Spike 3: Prompt engineering

### Phase 1: Backend Core (Days 2-3)
- [ ] FastAPI scaffold
- [ ] Image upload endpoint
- [ ] Claude Vision integration
- [ ] Dimension extraction pipeline
- [ ] Altium ASCII generator

### Phase 2: Frontend (Days 3-4)
- [ ] Upload UI
- [ ] Extraction results display
- [ ] Editable confirmation form
- [ ] Visual footprint preview
- [ ] Download flow

### Phase 3: Integration & Polish (Day 5)
- [ ] End-to-end testing
- [ ] Error handling
- [ ] Deploy to Railway
- [ ] Documentation/README

### Phase 4: Validation (Day 6)
- [ ] Test with example datasheets
- [ ] Import generated footprints into Altium
- [ ] Fix issues found
- [ ] Record demo

---

## Future Roadmap

**V1.1:** Full PDF parsing (find land pattern page automatically)  
**V1.2:** KiCad export  
**V2.0:** Batch processing, user accounts, saved library  
**V2.1:** Direct EDA tool plugin (Altium extension)  
**V3.0:** 3D model generation from package drawings

---

## Appendix A: Altium Import Methods

### Method 1: ASCII Paste
1. Open blank PcbLib in Altium
2. Create new component
3. Edit → Paste Special → ASCII Text
4. Paste generated primitives

### Method 2: Script Import
1. Save generated .pas script file
2. In Altium: DXP → Run Script
3. Script creates footprint programmatically

### Method 3: PcbLib File
1. Generate complete .PcbLib file in ASCII format
2. File → Open → select generated file
3. Copy component to target library

**Spike 1 will determine which method is most reliable.**

---

## Appendix B: Example Extraction Schema

```json
{
  "package_type": "custom",
  "standard_detected": null,
  "units": "mm",
  "pad_count": 8,
  "pad_shape": "rectangle",
  "pads": [
    {"index": 1, "x": -1.75, "y": 1.25, "width": 0.6, "height": 1.0},
    {"index": 2, "x": -1.75, "y": 0.0, "width": 0.6, "height": 1.0},
    ...
  ],
  "outline": {
    "width": 5.0,
    "height": 4.0,
    "origin": "center"
  },
  "confidence": {
    "pad_dimensions": 0.85,
    "pad_positions": 0.78,
    "outline": 0.92
  }
}
```

---

## Appendix C: Competitive/Alternative Landscape

| Tool | Coverage | Gap |
|------|----------|-----|
| SnapEDA | Large library | Missing custom/new parts |
| Ultra Librarian | Large library | Same coverage gap |
| Altium Content Vault | Growing | Incomplete |
| IPC-7351 Wizard (Altium) | Standard packages only | No custom support |
| Manual Creation | Universal | Time-consuming, error-prone |

**This tool targets the gap:** Parts not in existing libraries, non-standard packages, new components.
