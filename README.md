# FootprintAI - PCB Footprint Generator

AI-powered extraction of PCB footprint data from component datasheet images with Altium Designer 26 compatible output.

## Status

| Component | Status |
|-----------|--------|
| Backend API | ✅ Complete (186 tests passing) |
| Vision Extraction | ✅ Complete (Sonnet/Opus) |
| DelphiScript Generator | ✅ Complete & verified in Altium 26 |
| Frontend | ⏳ Not started |

## Overview

Hardware engineers frequently encounter components without existing PCB footprints. Creating footprints manually from datasheets takes 15-60 minutes per component. FootprintAI uses Claude Vision to extract footprint dimensions from datasheet images and generates Altium Designer footprint files automatically.

## Features

- **AI Vision Extraction**: Upload cropped datasheet images or PDF pages
- **Confidence Scoring**: Low-confidence values highlighted in yellow/orange
- **Standard Package Detection**: Detects IPC-7351 packages and redirects to Altium's IPC wizard
- **Pin 1 Selection**: Interactive selection when AI is uncertain
- **2D Preview**: Visual verification of pad positions and dimensions
- **Altium Export**: DelphiScript (.pas) files that create footprints in Altium Designer 26

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Tailwind CSS |
| Backend | Python FastAPI |
| AI | Anthropic Claude API (Sonnet default, Haiku/Opus available) |
| Hosting | Railway (local dev first) |

## Project Structure

```
pcb_footprint_generator/
├── backend/
│   ├── main.py                    # FastAPI app and routes
│   ├── extraction.py              # Claude Vision API integration
│   ├── generator_delphiscript.py  # DelphiScript (.pas) generation
│   ├── models.py                  # Pydantic data models
│   ├── prompts.py                 # AI extraction prompts
│   ├── requirements.txt
│   ├── pytest.ini                 # Test configuration
│   └── tests/                     # 186 unit tests
├── frontend/                      # React app (not yet implemented)
├── documents/                     # PRD and ground truth data
├── example_datasheets/            # Test images
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variable
export ANTHROPIC_API_KEY=your_key_here

# Run server
uvicorn main:app --reload --port 8000
```

### Running Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

186 tests covering models, extraction, prompts, API endpoints, and generators.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at http://localhost:5173

**Note:** Frontend is not yet implemented.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/api/upload` | Upload image (PNG/JPEG/GIF/WebP), returns job_id |
| GET | `/api/extract/{job_id}?model=sonnet` | Extract dimensions with confidence (model: haiku/sonnet/opus) |
| POST | `/api/confirm/{job_id}` | Confirm dimensions + Pin 1 selection |
| GET | `/api/generate/{job_id}` | Download DelphiScript (.pas) file |
| POST | `/api/detect-standard` | Check for IPC-7351 standard packages |
| GET | `/api/job/{job_id}/status` | Get job status |
| DELETE | `/api/job/{job_id}` | Delete job |

## Usage

1. **Upload**: Drag-drop or click to upload a cropped datasheet image showing the land pattern
2. **Review**: Check extracted dimensions, yellow highlights indicate uncertain values
3. **Pin 1**: If prompted, click to select Pin 1 location on the preview
4. **Confirm**: Verify the 2D preview matches expected footprint
5. **Download**: Get the DelphiScript (.pas) file
6. **Import to Altium**: Open Altium Designer → Run script in a PCB Library document

## Supported Pad Types

- **SMD**: Rectangular, Round, Rounded Rectangle, Oval
- **Through-Hole**: Circular and slotted drill holes
- **Thermal Pads**: Basic size/position (no paste mask patterns in MVP)

## Ground Truth Examples

Five validated footprints for testing:
1. RJ45 Connector - Through-hole, 22 pads
2. USB 3.0 Connector - Through-hole with slotted holes
3. M.2 Mini PCIe - SMD edge connector, 79 pads
4. Samtec HLE Socket - Mixed SMD + TH, 42 pads
5. SO-8EP - SOIC-8 with exposed thermal pad

## Cost

Approximately $0.002-0.004 per extraction using Claude Sonnet (default). Sonnet chosen over Haiku for accuracy - Haiku confused pad dimensions with pitch/spacing. Opus available for complex through-hole connectors.

| Model | Cost/Extraction | Best For |
|-------|-----------------|----------|
| Haiku | ~$0.002 | Not recommended (accuracy issues) |
| Sonnet | ~$0.003 | Simple SMD packages (default) |
| Opus | ~$0.004 | Complex TH connectors |

## License

MIT
