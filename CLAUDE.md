# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FootprintAI is a web application that extracts PCB footprint data from component datasheet images using AI vision and generates Altium Designer 26 compatible footprint files. The target users are hardware engineers who encounter components without existing library footprints.

**Status:** Greenfield project - planning documents complete, implementation not started.

## Tech Stack

- **Frontend:** React + Tailwind CSS
- **Backend:** Python FastAPI
- **AI:** Anthropic Claude API (start with Haiku, upgrade path to Sonnet/Opus)
- **Hosting:** Railway

## Key Domain Concepts

### Altium ASCII Format
- Output format is tab-delimited text importable into Altium's PcbLib editor
- Coordinates in mm, origin at component center (+X right, +Y up)
- Key element types: `Pad`, `Via`, `Track`, `Arc`, `Region`
- Layers: `MultiLayer` (through-hole), `Top Layer` (SMD), `TopOverlay` (silkscreen)

### Pad Types
- **SMD:** Top Layer only, no drill hole
- **Through-Hole (TH):** MultiLayer, circular drill
- **Slotted TH:** MultiLayer, oval/slot drill (uses `Drilled Slot` type)
- **Shapes:** Round, Rectangular, Rounded Rectangle, Oval

### Pin 1 Identification
Pin 1 indicated by: Rounded Rectangle shape, Rectangular/Square shape, Arc on TopOverlay, or corner position inference.

## Documentation

All requirements and ground truth data are in `documents/`:
- `footprint-prd.md` - Full PRD with user stories, API endpoints, extraction schema
- `Implementation Context - PCB Footprint Generator.pdf` - Technical specs and 5 ground truth examples
- `Raw Ground Truth Data - Altium Exports.pdf` - Raw Altium export data for validation

Example datasheet images for testing are in `example_datasheets/`.

## Planned Architecture

```
backend/
  main.py           # FastAPI endpoints
  extraction.py     # Claude Vision API integration
  generator.py      # Altium ASCII file generation
  models.py         # Pydantic models
  utils.py          # Unit conversion, validation

frontend/
  # React components: Upload, ExtractionResults, FootprintPreview, Download
```

### API Endpoints
- `POST /api/upload` - Image/PDF upload, returns job_id
- `GET /api/extract/{job_id}` - Returns extracted dimensions JSON
- `POST /api/confirm` - Submit confirmed/edited dimensions
- `GET /api/generate/{job_id}` - Download Altium footprint file
- `GET /api/detect-standard` - Detect IPC-7351 standard packages

## Ground Truth Examples

Five validated footprints available for testing extraction accuracy:
1. **RJ45 Connector** - Through-hole, 22 pads, mixed sizes
2. **USB 3.0 Connector** - Through-hole with slotted holes
3. **M.2 Mini PCIe** - SMD edge connector, 79 pads, 0.5mm pitch
4. **Samtec HLE Socket** - Mixed SMD + TH, 42 pads
5. **SO-8EP** - SOIC-8 with exposed thermal pad and vias
