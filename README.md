# FootprintAI - PCB Footprint Generator

AI-powered extraction of PCB footprint data from component datasheet images with Altium Designer 26 compatible output.

## Overview

Hardware engineers frequently encounter components without existing PCB footprints. Creating footprints manually from datasheets takes 15-60 minutes per component. FootprintAI uses Claude Vision to extract footprint dimensions from datasheet images and generates Altium Designer `.PcbLib` files automatically.

## Features

- **AI Vision Extraction**: Upload cropped datasheet images or PDF pages
- **Confidence Scoring**: Low-confidence values highlighted in yellow/orange
- **Standard Package Detection**: Detects IPC-7351 packages and redirects to Altium's IPC wizard
- **Pin 1 Selection**: Interactive selection when AI is uncertain
- **2D Preview**: Visual verification of pad positions and dimensions
- **Altium Export**: Direct `.PcbLib` ASCII format output for Altium Designer 26

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Tailwind CSS |
| Backend | Python FastAPI |
| AI | Anthropic Claude API (Haiku) |
| Hosting | Railway (local dev first) |

## Project Structure

```
pcb_footprint_generator/
├── backend/
│   ├── main.py           # FastAPI app and routes
│   ├── extraction.py     # Claude Vision API integration
│   ├── generator.py      # Altium .PcbLib file generation
│   ├── models.py         # Pydantic data models
│   ├── prompts.py        # AI extraction prompts
│   ├── utils.py          # Unit conversion, helpers
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   ├── package.json
│   └── tailwind.config.js
├── documents/            # PRD and ground truth data
├── example_datasheets/   # Test images
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

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at http://localhost:5173

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload image/PDF, returns job_id |
| GET | `/api/extract/{job_id}` | Get extracted dimensions with confidence |
| POST | `/api/confirm/{job_id}` | Confirm dimensions + Pin 1 selection |
| GET | `/api/generate/{job_id}` | Download .PcbLib file |
| GET | `/api/detect-standard` | Check for IPC-7351 standard packages |

## Usage

1. **Upload**: Drag-drop or click to upload a cropped datasheet image showing the land pattern
2. **Review**: Check extracted dimensions, yellow highlights indicate uncertain values
3. **Pin 1**: If prompted, click to select Pin 1 location on the preview
4. **Confirm**: Verify the 2D preview matches expected footprint
5. **Download**: Get the `.PcbLib` file and import into Altium Designer

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

Target: $0.01-0.05 per extraction using Claude Haiku. Architecture supports model swapping to Sonnet/Opus if higher accuracy needed.

## License

MIT
