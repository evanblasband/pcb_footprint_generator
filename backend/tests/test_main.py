"""
Tests for FastAPI backend (main.py).

Uses FastAPI's TestClient for synchronous testing of endpoints.
"""

import io
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app, jobs, Job, SUPPORTED_FORMATS, MAX_FILE_SIZE
from extraction import ExtractionResponse
from models import Footprint, Pad, PadShape, PadType, Outline, ExtractionResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    # Clear jobs before each test
    jobs.clear()
    return TestClient(app)


@pytest.fixture
def sample_image():
    """Create a minimal PNG image for testing."""
    # Minimal valid PNG (1x1 transparent pixel)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])
    return png_data


@pytest.fixture
def mock_extraction_response():
    """Create a mock successful extraction response."""
    footprint = Footprint(
        name="TEST-FOOTPRINT",
        description="Test footprint",
        pads=[
            Pad(designator="1", x=-1.27, y=0, width=0.6, height=1.0,
                shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
            Pad(designator="2", x=1.27, y=0, width=0.6, height=1.0,
                shape=PadShape.RECTANGULAR, pad_type=PadType.SMD),
        ],
        vias=[],
        outline=Outline(width=4.0, height=2.0),
    )

    extraction_result = ExtractionResult(
        package_type="custom",
        standard_detected=None,
        units="mm",
        pads=footprint.pads,
        vias=[],
        pin1_detected=True,
        pin1_index=0,
        outline=footprint.outline,
        overall_confidence=0.9,
        warnings=[],
    )

    return ExtractionResponse(
        success=True,
        footprint=footprint,
        extraction_result=extraction_result,
        raw_response={},
        model_used="claude-sonnet-4-5-20250929",
        input_tokens=1000,
        output_tokens=500,
    )


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for root endpoint."""

    def test_root_returns_ok(self, client):
        """Test that root endpoint returns status ok."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# =============================================================================
# Upload Endpoint Tests
# =============================================================================

class TestUploadEndpoint:
    """Tests for POST /api/upload."""

    def test_upload_png_success(self, client, sample_image):
        """Test successful PNG upload."""
        response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["filename"] == "test.png"
        assert "message" in data

    def test_upload_jpeg_success(self, client):
        """Test successful JPEG upload."""
        # Minimal JPEG
        jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

        response = client.post(
            "/api/upload",
            files={"file": ("test.jpg", io.BytesIO(jpeg_data), "image/jpeg")}
        )

        assert response.status_code == 200

    def test_upload_unsupported_format(self, client):
        """Test upload with unsupported file type."""
        response = client.post(
            "/api/upload",
            files={"file": ("test.bmp", io.BytesIO(b"fake"), "image/bmp")}
        )

        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    def test_upload_creates_job(self, client, sample_image):
        """Test that upload creates a job in storage."""
        response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )

        job_id = response.json()["job_id"]
        assert job_id in jobs
        assert jobs[job_id].filename == "test.png"
        assert jobs[job_id].image_bytes == sample_image


# =============================================================================
# Extract Endpoint Tests
# =============================================================================

class TestExtractEndpoint:
    """Tests for GET /api/extract/{job_id}."""

    def test_extract_job_not_found(self, client):
        """Test extraction with invalid job_id."""
        response = client.get("/api/extract/invalid-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_extract_success(self, client, sample_image, mock_extraction_response):
        """Test successful extraction."""
        # Upload first
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        # Mock the extractor
        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_from_bytes.return_value = mock_extraction_response
            mock_extractor_class.return_value = mock_extractor

            response = client.get(f"/api/extract/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == job_id
        assert data["footprint_name"] == "TEST-FOOTPRINT"
        assert data["pad_count"] == 2
        assert data["overall_confidence"] == 0.9

    def test_extract_caches_result(self, client, sample_image, mock_extraction_response):
        """Test that extraction result is cached."""
        # Upload first
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        # Mock the extractor
        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_from_bytes.return_value = mock_extraction_response
            mock_extractor_class.return_value = mock_extractor

            # First extraction
            response1 = client.get(f"/api/extract/{job_id}")
            # Second extraction (should use cached result)
            response2 = client.get(f"/api/extract/{job_id}")

        # Extractor should only be called once
        assert mock_extractor.extract_from_bytes.call_count == 1
        assert response1.json() == response2.json()

    def test_extract_with_model_parameter(self, client, sample_image, mock_extraction_response):
        """Test extraction with different model parameter."""
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_from_bytes.return_value = mock_extraction_response
            mock_extractor_class.return_value = mock_extractor

            response = client.get(f"/api/extract/{job_id}?model=opus")

        # Check that extractor was created with correct model
        mock_extractor_class.assert_called_with(model="opus")


# =============================================================================
# Confirm Endpoint Tests
# =============================================================================

class TestConfirmEndpoint:
    """Tests for POST /api/confirm/{job_id}."""

    def test_confirm_before_extract(self, client, sample_image):
        """Test confirm before extraction fails."""
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        response = client.post(f"/api/confirm/{job_id}", json={})

        assert response.status_code == 400
        assert "not yet performed" in response.json()["detail"].lower()

    def test_confirm_success(self, client, sample_image, mock_extraction_response):
        """Test successful confirmation."""
        # Upload
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        # Extract
        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_from_bytes.return_value = mock_extraction_response
            mock_extractor_class.return_value = mock_extractor
            client.get(f"/api/extract/{job_id}")

        # Confirm
        response = client.post(f"/api/confirm/{job_id}", json={"pin1_index": 0})

        assert response.status_code == 200
        data = response.json()
        assert data["confirmed"] is True
        assert jobs[job_id].confirmed is True
        assert jobs[job_id].pin1_index == 0


# =============================================================================
# Generate Endpoint Tests
# =============================================================================

class TestGenerateEndpoint:
    """Tests for GET /api/generate/{job_id}."""

    def test_generate_before_confirm(self, client, sample_image, mock_extraction_response):
        """Test generate before confirm fails."""
        # Upload and extract
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_from_bytes.return_value = mock_extraction_response
            mock_extractor_class.return_value = mock_extractor
            client.get(f"/api/extract/{job_id}")

        # Try to generate without confirming
        response = client.get(f"/api/generate/{job_id}")

        assert response.status_code == 400
        assert "not confirmed" in response.json()["detail"].lower()

    def test_generate_success(self, client, sample_image, mock_extraction_response):
        """Test successful script package generation (zip with .PrjScr and .pas)."""
        import zipfile

        # Upload
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        # Extract
        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_from_bytes.return_value = mock_extraction_response
            mock_extractor_class.return_value = mock_extractor
            client.get(f"/api/extract/{job_id}")

        # Confirm
        client.post(f"/api/confirm/{job_id}", json={})

        # Generate
        response = client.get(f"/api/generate/{job_id}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers["content-disposition"]
        assert ".zip" in response.headers["content-disposition"]

        # Check zip contents
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_names = zf.namelist()
            # Should contain .PrjScr and .pas files
            assert any(f.endswith('.PrjScr') for f in file_names)
            assert any(f.endswith('.pas') for f in file_names)

            # Check .pas content is valid DelphiScript
            pas_file = [f for f in file_names if f.endswith('.pas')][0]
            content = zf.read(pas_file).decode('utf-8')
            assert "Procedure" in content  # Pascal case in DelphiScript
            assert "PCBServer" in content
            assert "TEST_FOOTPRINT" in content  # Underscores due to sanitization

            # Check .PrjScr references the .pas file
            prjscr_file = [f for f in file_names if f.endswith('.PrjScr')][0]
            prjscr_content = zf.read(prjscr_file).decode('utf-8')
            assert "ProjectType=Script" in prjscr_content
            assert pas_file in prjscr_content


# =============================================================================
# Standard Package Detection Tests
# =============================================================================

class TestDetectStandardEndpoint:
    """Tests for POST /api/detect-standard."""

    def test_detect_standard_unsupported_format(self, client):
        """Test detection with unsupported format."""
        response = client.post(
            "/api/detect-standard",
            files={"file": ("test.bmp", io.BytesIO(b"fake"), "image/bmp")}
        )

        assert response.status_code == 400

    def test_detect_standard_success(self, client, sample_image):
        """Test standard package detection."""
        from extraction import StandardPackageResponse as ExtStdPkgResp

        mock_result = ExtStdPkgResp(
            is_standard=True,
            package_code="SOIC-8",
            confidence=0.85,
            ipc_parameters={"pitch": 1.27},
            reason=None,
        )

        with patch('main.FootprintExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.detect_standard_package.return_value = mock_result
            mock_extractor_class.return_value = mock_extractor

            response = client.post(
                "/api/detect-standard",
                files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_standard"] is True
        assert data["package_code"] == "SOIC-8"
        assert data["confidence"] == 0.85


# =============================================================================
# Job Status and Delete Tests
# =============================================================================

class TestJobManagement:
    """Tests for job status and deletion."""

    def test_get_job_status(self, client, sample_image):
        """Test getting job status."""
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        response = client.get(f"/api/job/{job_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["extracted"] is False
        assert data["confirmed"] is False

    def test_delete_job(self, client, sample_image):
        """Test deleting a job."""
        upload_response = client.post(
            "/api/upload",
            files={"file": ("test.png", io.BytesIO(sample_image), "image/png")}
        )
        job_id = upload_response.json()["job_id"]

        # Delete
        response = client.delete(f"/api/job/{job_id}")
        assert response.status_code == 200

        # Verify deleted
        assert job_id not in jobs

    def test_delete_nonexistent_job(self, client):
        """Test deleting non-existent job."""
        response = client.delete("/api/job/nonexistent")
        assert response.status_code == 404
