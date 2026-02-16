# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FootprintAI is a web application that extracts PCB footprint data from component datasheet images using AI vision and generates Altium Designer 26 compatible footprint files. The target users are hardware engineers who encounter components without existing library footprints.

**Status:** MVP Complete - Deployed to Railway

## Tech Stack

- **Frontend:** React + Tailwind CSS v4
- **Backend:** Python FastAPI
- **AI:** Anthropic Claude API (Sonnet default, Haiku/Opus available)
- **Hosting:** Railway (Docker-based deployment)

## Key Domain Concepts

### DelphiScript Output Format
- Output format is DelphiScript (.pas) files packaged in a Script Project (.zip)
- Uses Altium's official PCB API (`PCBServer`, `IPCB_Library`, etc.)
- Coordinates in mm, origin at component center (+X right, +Y up)
- Key element types: `Pad`, `Via`, `Track`, `Arc`
- Layers: `eMultiLayer` (through-hole), `eTopLayer` (SMD), `eTopOverlay` (silkscreen)

### Pad Types
- **SMD:** Top Layer only, no drill hole
- **Through-Hole (TH):** MultiLayer, circular drill
- **Slotted TH:** MultiLayer, oval/slot drill
- **Shapes:** Round, Rectangular, Oval (Rounded Rectangle falls back to Rectangular in AD26)

### Pin 1 Identification
Pin 1 indicated by: Arc on TopOverlay layer, or user click selection when AI uncertain.

## Documentation

All requirements and ground truth data are in `documents/`:
- `footprint-prd.md` - Full PRD with user stories, API endpoints, extraction schema
- `Implementation Context - PCB Footprint Generator.pdf` - Technical specs and 5 ground truth examples
- `Raw Ground Truth Data - Altium Exports.pdf` - Raw Altium export data for validation

Example datasheet images for testing are in `example_datasheets/`.

## Architecture

```
backend/
  main.py                    # FastAPI endpoints
  extraction.py              # Claude Vision API integration
  generator_delphiscript.py  # DelphiScript (.pas) generation
  models.py                  # Pydantic models
  prompts.py                 # AI extraction prompts
  verification.py            # Extraction verification pass

frontend/
  src/
    App.jsx                  # Main app with two-panel layout
    components/              # React components (UploadPanel, ControlPanel, PreviewCanvas, etc.)
```

### API Endpoints
- `GET /api/health` - Health check
- `POST /api/upload` - Image upload, returns job_id
- `GET /api/extract/{job_id}` - Returns extracted dimensions JSON
- `POST /api/confirm/{job_id}` - Submit confirmed dimensions + Pin 1
- `GET /api/generate/{job_id}` - Download Script Project package (.zip)
- `POST /api/detect-standard` - Detect IPC-7351 standard packages
- `GET /api/docs/{doc_name}` - Serve documentation markdown

### Deployment
- `Dockerfile` - Multi-stage build (Node frontend + Python backend)
- `railway.toml` - Railway deployment configuration
- Rate limiting enabled in production (slowapi)

## Ground Truth Examples

Five validated footprints available for testing extraction accuracy:
1. **RJ45 Connector** - Through-hole, 22 pads, mixed sizes
2. **USB 3.0 Connector** - Through-hole with slotted holes
3. **M.2 Mini PCIe** - SMD edge connector, 79 pads, 0.5mm pitch
4. **Samtec HLE Socket** - Mixed SMD + TH, 42 pads
5. **SO-8EP** - SOIC-8 with exposed thermal pad and vias
