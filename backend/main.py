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
import os
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import anthropic

from extraction import FootprintExtractor, ExtractionResponse, estimate_cost
from generator_delphiscript import DelphiScriptGenerator
from models import Footprint, Pad, PadShape, PadType, Outline, ExtractionResult
from verification import detect_suspicious_values, verify_extraction, apply_corrections


# =============================================================================
# Environment Configuration
# =============================================================================

# Check if we're in production (Railway sets RAILWAY_ENVIRONMENT)
IS_PRODUCTION = os.environ.get("RAILWAY_ENVIRONMENT") == "production" or \
                os.environ.get("ENVIRONMENT") == "production"

# Rate limiting configuration (only applies in production)
RATE_LIMIT_EXTRACT = "10/hour"  # 10 extractions per hour per IP
RATE_LIMIT_UPLOAD = "30/hour"   # 30 uploads per hour per IP


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
# Rate Limiting Setup (production only)
# =============================================================================

def get_real_ip(request: Request) -> str:
    """Get real client IP, handling proxies."""
    # Check for forwarded headers (Railway/proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key. In production, use IP.
    In development, return a constant to effectively disable limiting.
    """
    if not IS_PRODUCTION:
        return "development"  # Same key for all requests = no effective limit
    return get_real_ip(request)


# Initialize rate limiter
limiter = Limiter(key_func=rate_limit_key)


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title="PCB Footprint Generator API",
    description="Extract PCB footprint dimensions from datasheet images using AI vision",
    version="0.1.0",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration for frontend
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]

# Add production origins if configured
if os.environ.get("FRONTEND_URL"):
    allowed_origins.append(os.environ.get("FRONTEND_URL"))

# Railway provides the public URL
if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    allowed_origins.append(f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN')}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# In-Memory Job Storage
# =============================================================================

class ImageData:
    """Stores data for a single uploaded image."""
    def __init__(self, filename: str, image_bytes: bytes, content_type: str):
        self.filename = filename
        self.image_bytes = image_bytes
        self.content_type = content_type


class Job:
    """Represents an extraction job with its state and results."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.created_at = datetime.utcnow()

        # Multiple images support
        self.images: list[ImageData] = []

        # Extraction results (populated after extraction)
        self.extraction_response: Optional[ExtractionResponse] = None
        self.extracted = False

        # Confirmation (populated after user confirms)
        self.confirmed = False
        self.confirmed_footprint: Optional[Footprint] = None
        self.pin1_index: Optional[int] = None

    def add_image(self, filename: str, image_bytes: bytes, content_type: str):
        """Add an image to this job."""
        self.images.append(ImageData(filename, image_bytes, content_type))
        # Reset extraction if new images added
        if self.extracted:
            self.extracted = False
            self.extraction_response = None

    @property
    def filename(self) -> str:
        """Return first image filename for backward compatibility."""
        return self.images[0].filename if self.images else ""

    @property
    def image_bytes(self) -> bytes:
        """Return first image bytes for backward compatibility."""
        return self.images[0].image_bytes if self.images else b""

    @property
    def content_type(self) -> str:
        """Return first image content type for backward compatibility."""
        return self.images[0].content_type if self.images else ""

    @property
    def image_count(self) -> int:
        """Return number of images in this job."""
        return len(self.images)


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
    image_count: int = 1
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

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "PCB Footprint Generator API",
        "environment": "production" if IS_PRODUCTION else "development",
        "rate_limiting": IS_PRODUCTION
    }


@app.get("/api/status")
async def api_status():
    """
    Get API status including rate limit information.
    """
    return {
        "status": "ok",
        "environment": "production" if IS_PRODUCTION else "development",
        "rate_limits": {
            "extract": RATE_LIMIT_EXTRACT if IS_PRODUCTION else "unlimited",
            "upload": RATE_LIMIT_UPLOAD if IS_PRODUCTION else "unlimited",
        },
        "note": "Rate limits only apply in production environment"
    }


@app.post("/api/upload", response_model=UploadResponse)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_image(request: Request, files: list[UploadFile] = File(...)):
    """
    Upload one or more datasheet images for footprint extraction.

    Accepts PNG, JPEG, GIF, or WebP images up to 10MB each.
    Multiple images provide more context for better extraction accuracy.
    Returns a job_id for subsequent extraction and generation.

    Rate limited to 30 requests/hour in production.
    """
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    # Create job
    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id)

    for file in files:
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
                detail=f"File {file.filename} too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Add image to job
        job.add_image(
            filename=file.filename or "uploaded_image",
            image_bytes=content,
            content_type=file.content_type,
        )

    jobs[job_id] = job

    return UploadResponse(
        job_id=job_id,
        filename=job.filename,
        image_count=job.image_count,
        message=f"{job.image_count} image(s) uploaded successfully. Call /api/extract/{job_id} to extract dimensions."
    )


@app.post("/api/upload/{job_id}/add", response_model=UploadResponse)
async def add_images_to_job(job_id: str, files: list[UploadFile] = File(...)):
    """
    Add additional images to an existing job.

    Adding more images provides more context for extraction.
    This resets any previous extraction results.
    """
    job = get_job(job_id)

    for file in files:
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
                detail=f"File {file.filename} too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Add image to job
        job.add_image(
            filename=file.filename or "uploaded_image",
            image_bytes=content,
            content_type=file.content_type,
        )

    return UploadResponse(
        job_id=job_id,
        filename=job.filename,
        image_count=job.image_count,
        message=f"Added images. Job now has {job.image_count} image(s)."
    )


@app.get("/api/extract/{job_id}", response_model=ExtractResponse)
@limiter.limit(RATE_LIMIT_EXTRACT)
async def extract_dimensions(request: Request, job_id: str, model: str = "sonnet", staged: bool = False, verify: bool = False, examples: bool = False):
    """
    Extract footprint dimensions from the uploaded images.

    Uses Claude Vision API to analyze the datasheet images and extract
    pad positions, dimensions, and other footprint data. Multiple images
    provide additional context for more accurate extraction.

    Rate limited to 10 requests/hour in production.

    Args:
        job_id: The job ID from upload
        model: Model to use (haiku, sonnet, opus). Default: sonnet
        staged: Use 2-stage extraction pipeline for improved accuracy.
                Stage 1 parses dimension table, Stage 2 extracts geometry.
                Better at distinguishing pad dimensions from pitch values.
        verify: Run verification pass to catch common errors like pad vs pitch
                confusion. Uses Haiku model for cost efficiency. Default: False
        examples: Include few-shot examples in prompt. Can improve accuracy
                  for pad orientation but increases token usage. Default: False
    """
    job = get_job(job_id)

    if not job.images:
        raise HTTPException(status_code=400, detail="No images uploaded for this job")

    # Check if already extracted
    if job.extracted and job.extraction_response:
        resp = job.extraction_response
        return _build_extract_response(job_id, resp)

    # Create extractor and run extraction
    try:
        extractor = FootprintExtractor(model=model, include_examples=examples)

        # Prepare images list for extraction
        images = [(img.image_bytes, img.content_type) for img in job.images]

        # Use staged extraction if requested
        if staged:
            result = extractor.extract_staged_from_bytes_multi(images)
        else:
            result = extractor.extract_from_bytes_multi(images)

        # Run verification pass if enabled and extraction succeeded
        if verify and result.success and result.extraction_result:
            result = _run_verification(result, job.images[0].image_bytes, job.images[0].content_type)

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


def _run_verification(result: ExtractionResponse, image_bytes: bytes, media_type: str) -> ExtractionResponse:
    """
    Run verification pass on extraction results to catch common errors.

    Checks for suspicious values like pad dimensions close to pitch,
    and asks the model to verify and correct if needed.

    Args:
        result: Original extraction response
        image_bytes: Image bytes for verification
        media_type: Image MIME type

    Returns:
        Updated ExtractionResponse with any corrections applied
    """
    extraction = result.extraction_result

    # Check if verification is needed
    suspicious = detect_suspicious_values(extraction)
    if not suspicious["needs_verification"]:
        return result

    # Run verification
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Can't verify without API key, return original result
        return result

    client = anthropic.Anthropic(api_key=api_key)
    verification = verify_extraction(
        extraction,
        image_bytes,
        media_type,
        client,
        model="claude-haiku-4-5-20251001"  # Use Haiku for cost efficiency
    )

    if verification.error:
        # Verification failed, return original result with warning
        if extraction.warnings is None:
            extraction.warnings = []
        extraction.warnings.append(f"Verification skipped: {verification.error}")
        return result

    # Apply any corrections
    if verification.pad_dimensions_corrected or not verification.verified:
        corrected_extraction = apply_corrections(extraction, verification)

        # Update tokens to include verification cost
        total_input = (result.input_tokens or 0) + verification.input_tokens
        total_output = (result.output_tokens or 0) + verification.output_tokens

        # Rebuild footprint from corrected extraction
        # The corrected_extraction already has properly typed Pad, Via, and Outline objects
        corrected_footprint = Footprint(
            name=result.footprint.name if result.footprint else "Verified_Footprint",
            description=result.footprint.description if result.footprint else "",
            pads=corrected_extraction.pads,  # Already proper Pad objects
            vias=corrected_extraction.vias,  # Already proper Via objects
            outline=corrected_extraction.outline,  # Already Outline object or None
        )

        return ExtractionResponse(
            success=True,
            extraction_result=corrected_extraction,
            footprint=corrected_footprint,
            model_used=result.model_used,
            input_tokens=total_input,
            output_tokens=total_output,
        )

    # Update tokens even if no corrections
    total_input = (result.input_tokens or 0) + verification.input_tokens
    total_output = (result.output_tokens or 0) + verification.output_tokens
    result.input_tokens = total_input
    result.output_tokens = total_output

    return result


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
            "vias": [
                {
                    "x": v.x,
                    "y": v.y,
                    "diameter": v.diameter,
                    "drill_diameter": v.drill_diameter,
                }
                for v in result.footprint.vias
            ] if result.footprint.vias else [],
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
    Generate and download a Script Project package (.zip) containing:
    - .PrjScr file (Altium Script Project)
    - .pas file (DelphiScript footprint generator)

    The package can be opened in Altium Designer to run the script.
    """
    job = get_job(job_id)

    if not job.confirmed or not job.confirmed_footprint:
        raise HTTPException(
            status_code=400,
            detail="Extraction not confirmed. Call /api/confirm first."
        )

    footprint_name = job.confirmed_footprint.name
    safe_name = _safe_filename(footprint_name)

    # Generate DelphiScript content
    generator = DelphiScriptGenerator(job.confirmed_footprint)
    script_content = generator.generate()

    # Generate .PrjScr project file content
    prjscr_content = _generate_prjscr(safe_name)

    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add script project file
        zf.writestr(f"{safe_name}.PrjScr", prjscr_content)
        # Add DelphiScript file
        zf.writestr(f"{safe_name}.pas", script_content)

    zip_buffer.seek(0)

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_ScriptProject.zip"'
        }
    )


def _generate_prjscr(script_name: str) -> str:
    """Generate Altium Script Project (.PrjScr) file content."""
    return f"""[Design]
Version=1.0
HierarchyMode=0
ChannelRoomNamingStyle=0
OutputPath=
ChannelDesignatorFormatString=$Component_$RoomName
ChannelRoomLevelSeperator=_
ReleasesFolder=
DesignCapture=
ProjectType=Script
LockPanelState=0

[Document1]
DocumentPath={script_name}.pas
AnnotationEnabled=1
"""


def _safe_filename(name: str) -> str:
    """Convert name to safe filename (no special characters)."""
    safe = ""
    for c in name:
        if c.isalnum() or c in "-_":
            safe += c
        else:
            safe += "_"
    return safe or "Footprint"


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


# =============================================================================
# Documentation Endpoints
# =============================================================================

# Document paths for local development (relative to backend/)
LOCAL_DOCS = {
    "readme": "../README.md",
    "prd": "../documents/footprint-prd.md",
    "technical-decisions": "../technical_decisions.md",
}

# Document paths for Docker/production (absolute paths)
DOCKER_DOCS = {
    "readme": "/docs/README.md",
    "prd": "/docs/documents/footprint-prd.md",
    "technical-decisions": "/docs/technical_decisions.md",
}


def get_doc_path(doc_name: str) -> Path:
    """Get document path, checking Docker paths first then local."""
    # Try Docker path first
    docker_path = Path(DOCKER_DOCS.get(doc_name, ""))
    if docker_path.exists():
        return docker_path

    # Fall back to local path
    local_path = Path(__file__).parent / LOCAL_DOCS.get(doc_name, "")
    return local_path


@app.get("/api/docs/{doc_name}")
async def get_documentation(doc_name: str):
    """
    Get documentation markdown content.

    Available docs: readme, prd, technical-decisions
    """
    if doc_name not in LOCAL_DOCS:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {doc_name}. Available: {list(LOCAL_DOCS.keys())}"
        )

    doc_path = get_doc_path(doc_name)

    if not doc_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Document file not found: {doc_name}"
        )

    content = doc_path.read_text(encoding="utf-8")

    return {"name": doc_name, "content": content}


# =============================================================================
# Static File Serving (Production)
# =============================================================================

# In production, serve the built frontend from the static directory
STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/favicon.svg")
    async def serve_favicon():
        """Serve the favicon."""
        favicon_path = STATIC_DIR / "favicon.svg"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="Favicon not found")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        Serve static files or the SPA for any non-API routes.
        This must be the last route defined.
        """
        # Don't serve SPA for API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Check if it's a static file that exists (e.g., .gif, .png, .jpg)
        static_file_path = STATIC_DIR / full_path
        if static_file_path.exists() and static_file_path.is_file():
            # Determine media type based on extension
            ext = static_file_path.suffix.lower()
            media_types = {
                ".gif": "image/gif",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
                ".webp": "image/webp",
                ".css": "text/css",
                ".js": "application/javascript",
            }
            media_type = media_types.get(ext, "application/octet-stream")
            return FileResponse(static_file_path, media_type=media_type)

        # Otherwise serve the SPA
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(), status_code=200)

        raise HTTPException(status_code=404, detail="Frontend not found")
