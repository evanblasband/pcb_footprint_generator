"""
FastAPI backend for PCB Footprint Generator.

Provides REST API endpoints for:
- Image upload and extraction job creation
- Footprint dimension extraction using Claude Vision
- User confirmation of extracted dimensions
- DelphiScript file generation for Altium import
- Standard package detection

Usage:
    uvicorn main:app --reload --port 8000
"""

import io
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from extraction import FootprintExtractor, ExtractionResponse, estimate_cost
from generator_delphiscript import DelphiScriptGenerator
from models import Footprint, Pad, PadShape, PadType, Outline, ExtractionResult


# =============================================================================
# Configuration
# =============================================================================

# Supported image formats for upload
SUPPORTED_FORMATS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# Job expiration time (jobs are cleaned up after this)
JOB_EXPIRATION_HOURS = 1

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title="PCB Footprint Generator API",
    description="Extract PCB footprint dimensions from datasheet images using AI vision",
    version="0.1.0",
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# In-Memory Job Storage
# =============================================================================

class Job:
    """Represents an extraction job with its state and results."""

    def __init__(self, job_id: str, filename: str, image_bytes: bytes, content_type: str):
        self.job_id = job_id
        self.filename = filename
        self.image_bytes = image_bytes
        self.content_type = content_type
        self.created_at = datetime.utcnow()

        # Extraction results (populated after extraction)
        self.extraction_response: Optional[ExtractionResponse] = None
        self.extracted = False

        # Confirmation (populated after user confirms)
        self.confirmed = False
        self.confirmed_footprint: Optional[Footprint] = None
        self.pin1_index: Optional[int] = None


# In-memory job storage (dict keyed by job_id)
jobs: dict[str, Job] = {}


def cleanup_expired_jobs():
    """Remove jobs older than JOB_EXPIRATION_HOURS."""
    cutoff = datetime.utcnow() - timedelta(hours=JOB_EXPIRATION_HOURS)
    expired = [jid for jid, job in jobs.items() if job.created_at < cutoff]
    for jid in expired:
        del jobs[jid]


def get_job(job_id: str) -> Job:
    """Get a job by ID, raising 404 if not found."""
    cleanup_expired_jobs()
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return jobs[job_id]


# =============================================================================
# Request/Response Models
# =============================================================================

class UploadResponse(BaseModel):
    """Response from upload endpoint."""
    job_id: str
    filename: str
    message: str


class ExtractResponse(BaseModel):
    """Response from extract endpoint."""
    job_id: str
    success: bool
    error: Optional[str] = None
    footprint_name: Optional[str] = None
    pad_count: Optional[int] = None
    overall_confidence: Optional[float] = None
    pin1_detected: Optional[bool] = None
    pin1_index: Optional[int] = None
    warnings: list[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None
    # Full extraction data
    footprint: Optional[dict] = None
    extraction_result: Optional[dict] = None


class ConfirmRequest(BaseModel):
    """Request body for confirm endpoint."""
    pin1_index: Optional[int] = None
    # Future: could include edited pad values


class ConfirmResponse(BaseModel):
    """Response from confirm endpoint."""
    job_id: str
    confirmed: bool
    message: str


class StandardPackageResponse(BaseModel):
    """Response from standard package detection."""
    is_standard: bool
    package_code: Optional[str] = None
    confidence: float = 0.0
    ipc_parameters: Optional[dict] = None
    reason: Optional[str] = None


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "PCB Footprint Generator API"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    Upload a datasheet image for footprint extraction.

    Accepts PNG, JPEG, GIF, or WebP images up to 10MB.
    Returns a job_id for subsequent extraction and generation.
    """
    # Validate content type
    if file.content_type not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Supported: PNG, JPEG, GIF, WebP"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Create job
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        filename=file.filename or "uploaded_image",
        image_bytes=content,
        content_type=file.content_type,
    )
    jobs[job_id] = job

    return UploadResponse(
        job_id=job_id,
        filename=job.filename,
        message="Image uploaded successfully. Call /api/extract/{job_id} to extract dimensions."
    )


@app.get("/api/extract/{job_id}", response_model=ExtractResponse)
async def extract_dimensions(job_id: str, model: str = "sonnet"):
    """
    Extract footprint dimensions from the uploaded image.

    Uses Claude Vision API to analyze the datasheet image and extract
    pad positions, dimensions, and other footprint data.

    Args:
        job_id: The job ID from upload
        model: Model to use (haiku, sonnet, opus). Default: sonnet
    """
    job = get_job(job_id)

    # Check if already extracted
    if job.extracted and job.extraction_response:
        resp = job.extraction_response
        return _build_extract_response(job_id, resp)

    # Create extractor and run extraction
    try:
        extractor = FootprintExtractor(model=model)
        result = extractor.extract_from_bytes(job.image_bytes, job.content_type)

        # Store result
        job.extraction_response = result
        job.extracted = True

        return _build_extract_response(job_id, result)

    except Exception as e:
        return ExtractResponse(
            job_id=job_id,
            success=False,
            error=str(e),
        )


def _build_extract_response(job_id: str, result: ExtractionResponse) -> ExtractResponse:
    """Build ExtractResponse from ExtractionResponse."""
    if not result.success:
        return ExtractResponse(
            job_id=job_id,
            success=False,
            error=result.error,
            model_used=result.model_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    # Calculate estimated cost
    cost = None
    if result.input_tokens and result.output_tokens and result.model_used:
        cost = estimate_cost(result.input_tokens, result.output_tokens, result.model_used)

    # Convert footprint to dict for JSON serialization
    footprint_dict = None
    if result.footprint:
        footprint_dict = {
            "name": result.footprint.name,
            "description": result.footprint.description,
            "pads": [
                {
                    "designator": p.designator,
                    "x": p.x,
                    "y": p.y,
                    "width": p.width,
                    "height": p.height,
                    "shape": p.shape.value,
                    "pad_type": p.pad_type.value,
                    "rotation": p.rotation,
                    "drill": {
                        "diameter": p.drill.diameter,
                        "drill_type": p.drill.drill_type.value,
                        "slot_length": p.drill.slot_length,
                    } if p.drill else None,
                }
                for p in result.footprint.pads
            ],
            "outline": {
                "width": result.footprint.outline.width,
                "height": result.footprint.outline.height,
            } if result.footprint.outline else None,
        }

    # Convert extraction result to dict
    extraction_dict = None
    if result.extraction_result:
        er = result.extraction_result
        extraction_dict = {
            "package_type": er.package_type,
            "standard_detected": er.standard_detected,
            "units": er.units,
            "pin1_detected": er.pin1_detected,
            "pin1_index": er.pin1_index,
            "overall_confidence": er.overall_confidence,
            "warnings": er.warnings,
        }

    return ExtractResponse(
        job_id=job_id,
        success=True,
        footprint_name=result.footprint.name if result.footprint else None,
        pad_count=len(result.footprint.pads) if result.footprint else None,
        overall_confidence=result.extraction_result.overall_confidence if result.extraction_result else None,
        pin1_detected=result.extraction_result.pin1_detected if result.extraction_result else None,
        pin1_index=result.extraction_result.pin1_index if result.extraction_result else None,
        warnings=result.extraction_result.warnings if result.extraction_result else [],
        model_used=result.model_used,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost=cost,
        footprint=footprint_dict,
        extraction_result=extraction_dict,
    )


@app.post("/api/confirm/{job_id}", response_model=ConfirmResponse)
async def confirm_extraction(job_id: str, request: ConfirmRequest):
    """
    Confirm the extracted dimensions and optionally set Pin 1.

    This endpoint is called after the user reviews the extraction
    and confirms the dimensions are correct (or selects Pin 1 if needed).
    """
    job = get_job(job_id)

    if not job.extracted or not job.extraction_response:
        raise HTTPException(
            status_code=400,
            detail="Extraction not yet performed. Call /api/extract first."
        )

    if not job.extraction_response.success:
        raise HTTPException(
            status_code=400,
            detail="Extraction failed. Cannot confirm."
        )

    # Store confirmation
    job.confirmed = True
    job.confirmed_footprint = job.extraction_response.footprint
    job.pin1_index = request.pin1_index

    return ConfirmResponse(
        job_id=job_id,
        confirmed=True,
        message="Extraction confirmed. Call /api/generate/{job_id} to download the footprint file."
    )


@app.get("/api/generate/{job_id}")
async def generate_footprint(job_id: str):
    """
    Generate and download the DelphiScript (.pas) footprint file.

    The file can be run in Altium Designer to create the footprint
    in a PCB Library.
    """
    job = get_job(job_id)

    if not job.confirmed or not job.confirmed_footprint:
        raise HTTPException(
            status_code=400,
            detail="Extraction not confirmed. Call /api/confirm first."
        )

    # Generate DelphiScript
    generator = DelphiScriptGenerator(job.confirmed_footprint)
    script_content = generator.generate()

    # Return as downloadable file
    filename = f"{job.confirmed_footprint.name}.pas"

    return Response(
        content=script_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.post("/api/detect-standard")
async def detect_standard_package(file: UploadFile = File(...)):
    """
    Detect if the image shows a standard IPC-7351 package.

    This is a lightweight check that can be run before full extraction
    to potentially redirect users to Altium's built-in IPC wizard.
    """
    # Validate content type
    if file.content_type not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}"
        )

    content = await file.read()

    try:
        extractor = FootprintExtractor(model="haiku")  # Use Haiku for quick detection
        result = extractor.detect_standard_package(content, file.content_type)

        return StandardPackageResponse(
            is_standard=result.is_standard,
            package_code=result.package_code,
            confidence=result.confidence,
            ipc_parameters=result.ipc_parameters,
            reason=result.reason,
        )

    except Exception as e:
        return StandardPackageResponse(
            is_standard=False,
            reason=f"Detection failed: {str(e)}"
        )


# =============================================================================
# Additional Utility Endpoints
# =============================================================================

@app.get("/api/job/{job_id}/status")
async def get_job_status(job_id: str):
    """Get the current status of a job."""
    job = get_job(job_id)

    return {
        "job_id": job_id,
        "filename": job.filename,
        "created_at": job.created_at.isoformat(),
        "extracted": job.extracted,
        "confirmed": job.confirmed,
        "extraction_success": job.extraction_response.success if job.extraction_response else None,
    }


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated data."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    del jobs[job_id]
    return {"message": f"Job {job_id} deleted"}
