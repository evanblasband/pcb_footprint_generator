"""
Claude Vision API integration for PCB footprint extraction.

This module handles the interaction with Claude's vision API to extract
footprint dimensions from datasheet images. It uses Claude Haiku by default
for cost efficiency, with architecture supporting model upgrades.

Usage:
    extractor = FootprintExtractor()
    result = await extractor.extract_from_image(image_path)

    # Or with bytes
    result = await extractor.extract_from_bytes(image_bytes, media_type="image/png")

Configuration:
    Set ANTHROPIC_API_KEY environment variable for authentication.
    Optionally set CLAUDE_MODEL to override the default model.
"""

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import anthropic

from models import (
    Footprint,
    Pad,
    PadType,
    PadShape,
    Drill,
    DrillType,
    Via,
    Outline,
    ExtractionResult,
)
from prompts import get_extraction_prompt, get_standard_package_prompt
from prompts_staged import get_stage1_prompt, get_stage2_prompt


# =============================================================================
# Configuration
# =============================================================================

# Default model - Sonnet for accuracy (correctly distinguishes pad dimensions from pitch)
# Haiku struggles with pad width vs spacing confusion
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

# Model options for upgrades
MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
}

# Maximum tokens for response
MAX_TOKENS = 4096

# Supported image types
SUPPORTED_MEDIA_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExtractionResponse:
    """
    Response from the extraction API.

    Attributes:
        success: Whether extraction succeeded
        footprint: Extracted footprint data (if successful)
        raw_response: Raw JSON response from Claude
        error: Error message (if failed)
        model_used: Which Claude model was used
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
    """
    success: bool
    footprint: Optional[Footprint] = None
    extraction_result: Optional[ExtractionResult] = None
    raw_response: Optional[dict] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class StandardPackageResponse:
    """
    Response from standard package detection.

    Attributes:
        is_standard: Whether a standard package was detected
        package_code: IPC package code if detected
        confidence: Confidence in detection
        ipc_parameters: Parameters for IPC wizard if applicable
    """
    is_standard: bool
    package_code: Optional[str] = None
    confidence: float = 0.0
    ipc_parameters: Optional[dict] = None
    reason: Optional[str] = None


# =============================================================================
# Main Extractor Class
# =============================================================================

class FootprintExtractor:
    """
    Extracts PCB footprint data from datasheet images using Claude Vision.

    This class handles:
    - Image encoding for the API
    - Prompt construction
    - API calls to Claude
    - Response parsing and validation
    - Conversion to Footprint model

    Attributes:
        model: Claude model to use (default: haiku)
        client: Anthropic API client
    """

    def __init__(self, model: str = None, api_key: str = None, include_examples: bool = False):
        """
        Initialize the extractor.

        Args:
            model: Model name or alias ('haiku', 'sonnet', 'opus')
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            include_examples: Include few-shot examples in prompt (can improve accuracy)
        """
        # Resolve model name
        if model is None:
            model = os.environ.get("CLAUDE_MODEL", "haiku")

        if model in MODELS:
            self.model = MODELS[model]
        else:
            self.model = model

        self.include_examples = include_examples

        # Initialize client
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = anthropic.Anthropic(api_key=api_key)

    def extract_from_image(self, image_path: str | Path) -> ExtractionResponse:
        """
        Extract footprint from an image file.

        Args:
            image_path: Path to the image file (PNG, JPEG, GIF, or WebP)

        Returns:
            ExtractionResponse with extracted footprint or error
        """
        image_path = Path(image_path)

        # Validate file exists
        if not image_path.exists():
            return ExtractionResponse(
                success=False,
                error=f"Image file not found: {image_path}"
            )

        # Determine media type
        suffix = image_path.suffix.lower()
        media_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }

        media_type = media_type_map.get(suffix)
        if not media_type:
            return ExtractionResponse(
                success=False,
                error=f"Unsupported image format: {suffix}. Supported: PNG, JPEG, GIF, WebP"
            )

        # Read and encode image
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        return self.extract_from_bytes(image_bytes, media_type)

    def extract_from_bytes(
        self,
        image_bytes: bytes,
        media_type: str
    ) -> ExtractionResponse:
        """
        Extract footprint from image bytes (single image).

        Args:
            image_bytes: Raw image bytes
            media_type: MIME type (e.g., 'image/png')

        Returns:
            ExtractionResponse with extracted footprint or error
        """
        return self.extract_from_bytes_multi([(image_bytes, media_type)])

    def extract_from_bytes_multi(
        self,
        images: list[tuple[bytes, str]]
    ) -> ExtractionResponse:
        """
        Extract footprint from multiple image bytes.

        Multiple images provide additional context for more accurate extraction.
        Images might include dimension drawings, pin diagrams, tables, etc.

        Args:
            images: List of (image_bytes, media_type) tuples

        Returns:
            ExtractionResponse with extracted footprint or error
        """
        if not images:
            return ExtractionResponse(
                success=False,
                error="At least one image is required"
            )

        # Validate and encode all images
        content_parts = []
        for i, (image_bytes, media_type) in enumerate(images):
            # Validate media type
            if media_type not in SUPPORTED_MEDIA_TYPES:
                return ExtractionResponse(
                    success=False,
                    error=f"Image {i+1}: Unsupported media type: {media_type}. Supported: {SUPPORTED_MEDIA_TYPES}"
                )

            # Encode image as base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_base64,
                },
            })

        # Get extraction prompt with multi-image context
        prompt = get_extraction_prompt(include_examples=self.include_examples)
        if len(images) > 1:
            prompt = f"I'm providing {len(images)} images from a component datasheet. Use ALL images to extract the most accurate footprint dimensions. Cross-reference information between images to verify values and resolve ambiguities.\n\n" + prompt

        # Add text prompt at the end
        content_parts.append({
            "type": "text",
            "text": prompt,
        })

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": content_parts,
                    }
                ],
            )

            # Extract response text
            response_text = response.content[0].text

            # Parse JSON from response
            raw_response = self._parse_json_response(response_text)

            if raw_response is None:
                return ExtractionResponse(
                    success=False,
                    error="Failed to parse JSON from Claude response",
                    model_used=self.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

            # Convert to Footprint model
            footprint, extraction_result = self._response_to_footprint(raw_response)

            return ExtractionResponse(
                success=True,
                footprint=footprint,
                extraction_result=extraction_result,
                raw_response=raw_response,
                model_used=self.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except anthropic.APIError as e:
            return ExtractionResponse(
                success=False,
                error=f"Claude API error: {str(e)}",
                model_used=self.model,
            )
        except Exception as e:
            return ExtractionResponse(
                success=False,
                error=f"Extraction failed: {str(e)}",
                model_used=self.model,
            )

    def detect_standard_package(
        self,
        image_bytes: bytes,
        media_type: str
    ) -> StandardPackageResponse:
        """
        Detect if the image shows a standard IPC package.

        This is a lightweight check that can be run before full extraction
        to potentially redirect users to Altium's IPC wizard.

        Args:
            image_bytes: Raw image bytes
            media_type: MIME type

        Returns:
            StandardPackageResponse with detection results
        """
        # Encode image
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Get detection prompt
        prompt = get_standard_package_prompt()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,  # Shorter response needed
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            response_text = response.content[0].text
            result = self._parse_json_response(response_text)

            if result is None:
                return StandardPackageResponse(
                    is_standard=False,
                    reason="Failed to parse detection response"
                )

            return StandardPackageResponse(
                is_standard=result.get("is_standard", False),
                package_code=result.get("package_code"),
                confidence=result.get("confidence", 0.0),
                ipc_parameters=result.get("ipc_parameters"),
                reason=result.get("reason"),
            )

        except Exception as e:
            return StandardPackageResponse(
                is_standard=False,
                reason=f"Detection failed: {str(e)}"
            )

    def extract_staged_from_bytes_multi(
        self,
        images: list[tuple[bytes, str]]
    ) -> ExtractionResponse:
        """
        Extract footprint using 2-stage pipeline for improved accuracy.

        Stage 1 (Haiku): Parse dimension table and identify package type
        Stage 2 (Sonnet): Extract geometry using parsed table context

        This approach improves accuracy by:
        - Separating table parsing from geometry extraction
        - Preventing pad dimension vs pitch confusion
        - Providing explicit dimension values to Stage 2

        Args:
            images: List of (image_bytes, media_type) tuples

        Returns:
            ExtractionResponse with extracted footprint or error
        """
        if not images:
            return ExtractionResponse(
                success=False,
                error="At least one image is required"
            )

        # Validate and encode all images
        content_parts = []
        for i, (image_bytes, media_type) in enumerate(images):
            if media_type not in SUPPORTED_MEDIA_TYPES:
                return ExtractionResponse(
                    success=False,
                    error=f"Image {i+1}: Unsupported media type: {media_type}"
                )

            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_base64,
                },
            })

        total_input_tokens = 0
        total_output_tokens = 0

        try:
            # =================================================================
            # Stage 1: Scene Analysis + Table Parsing (Haiku)
            # =================================================================
            stage1_prompt = get_stage1_prompt()
            stage1_content = content_parts.copy()
            stage1_content.append({"type": "text", "text": stage1_prompt})

            stage1_response = self.client.messages.create(
                model=MODELS["haiku"],
                max_tokens=2048,
                messages=[{"role": "user", "content": stage1_content}],
            )

            total_input_tokens += stage1_response.usage.input_tokens
            total_output_tokens += stage1_response.usage.output_tokens

            stage1_text = stage1_response.content[0].text
            stage1_result = self._parse_json_response(stage1_text)

            if stage1_result is None:
                return ExtractionResponse(
                    success=False,
                    error="Stage 1 failed: Could not parse table analysis",
                    model_used="staged (haiku+sonnet)",
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                )

            # =================================================================
            # Stage 2: Geometry Extraction with Table Context (Sonnet)
            # =================================================================
            stage2_prompt = get_stage2_prompt(stage1_result)
            stage2_content = content_parts.copy()
            stage2_content.append({"type": "text", "text": stage2_prompt})

            stage2_response = self.client.messages.create(
                model=MODELS["sonnet"],
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": stage2_content}],
            )

            total_input_tokens += stage2_response.usage.input_tokens
            total_output_tokens += stage2_response.usage.output_tokens

            stage2_text = stage2_response.content[0].text
            raw_response = self._parse_json_response(stage2_text)

            if raw_response is None:
                return ExtractionResponse(
                    success=False,
                    error="Stage 2 failed: Could not parse geometry extraction",
                    model_used="staged (haiku+sonnet)",
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                )

            # Add stage1 metadata to raw response for debugging
            raw_response["_stage1_analysis"] = stage1_result

            # Convert to Footprint model
            footprint, extraction_result = self._response_to_footprint(raw_response)

            return ExtractionResponse(
                success=True,
                footprint=footprint,
                extraction_result=extraction_result,
                raw_response=raw_response,
                model_used="staged (haiku+sonnet)",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        except anthropic.APIError as e:
            return ExtractionResponse(
                success=False,
                error=f"Claude API error: {str(e)}",
                model_used="staged (haiku+sonnet)",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )
        except Exception as e:
            return ExtractionResponse(
                success=False,
                error=f"Staged extraction failed: {str(e)}",
                model_used="staged (haiku+sonnet)",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _parse_json_response(self, response_text: str) -> Optional[dict]:
        """
        Parse JSON from Claude's response text.

        Handles cases where JSON is wrapped in markdown code blocks.

        Args:
            response_text: Raw response text from Claude

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        text = response_text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try extracting from generic code block
        if "```" in text:
            start = text.find("```") + 3
            # Skip language identifier if present
            newline = text.find("\n", start)
            if newline > start:
                start = newline + 1
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

        return None

    def _response_to_footprint(
        self,
        response: dict
    ) -> tuple[Footprint, ExtractionResult]:
        """
        Convert Claude's JSON response to Footprint and ExtractionResult models.

        Args:
            response: Parsed JSON response

        Returns:
            Tuple of (Footprint, ExtractionResult)
        """
        # Extract pads
        pads = []
        for pad_data in response.get("pads", []):
            # Determine pad shape
            shape_str = pad_data.get("shape", "rectangular").lower()
            shape_map = {
                "rectangular": PadShape.RECTANGULAR,
                "round": PadShape.ROUND,
                "oval": PadShape.OVAL,
                "rounded_rectangle": PadShape.ROUNDED_RECTANGLE,
            }
            shape = shape_map.get(shape_str, PadShape.RECTANGULAR)

            # Determine pad type
            pad_type_str = pad_data.get("pad_type", "smd").lower()
            pad_type = PadType.THROUGH_HOLE if pad_type_str == "th" else PadType.SMD

            # Create drill if through-hole
            drill = None
            if pad_type == PadType.THROUGH_HOLE:
                drill_diameter = pad_data.get("drill_diameter")
                slot_length = pad_data.get("drill_slot_length")

                if drill_diameter:
                    drill = Drill(
                        diameter=drill_diameter,
                        drill_type=DrillType.SLOT if slot_length else DrillType.ROUND,
                        slot_length=slot_length,
                    )

            pad = Pad(
                designator=str(pad_data.get("designator", "")),
                x=float(pad_data.get("x", 0)),
                y=float(pad_data.get("y", 0)),
                width=float(pad_data.get("width", 0)),
                height=float(pad_data.get("height", 0)),
                shape=shape,
                pad_type=pad_type,
                rotation=float(pad_data.get("rotation", 0)),
                drill=drill,
            )
            pads.append(pad)

        # Extract outline
        outline_data = response.get("outline", {})
        outline = Outline(
            width=float(outline_data.get("width", 0)),
            height=float(outline_data.get("height", 0)),
        )

        # Extract vias (thermal vias)
        vias = []
        for via_data in response.get("vias", []):
            via = Via(
                x=float(via_data.get("x", 0)),
                y=float(via_data.get("y", 0)),
                diameter=float(via_data.get("outer_diameter", 0.6)),
                drill_diameter=float(via_data.get("drill_diameter", 0.3)),
            )
            vias.append(via)

        # Create footprint
        footprint = Footprint(
            name=response.get("footprint_name", "EXTRACTED"),
            description=f"Extracted from datasheet image",
            pads=pads,
            vias=vias,
            outline=outline,
        )

        # Find pin1 index in pads list
        pin1_designator = response.get("pin1_location", {}).get("designator")
        pin1_index = None
        pin1_detected = False

        if pin1_designator:
            for i, pad in enumerate(pads):
                if pad.designator == str(pin1_designator):
                    pin1_index = i
                    pin1_detected = True
                    break

        # Create extraction result matching the ExtractionResult model schema
        extraction_result = ExtractionResult(
            package_type="custom",
            standard_detected=response.get("standard_package_detected"),
            units="mm",
            pads=pads,
            vias=vias,
            pin1_detected=pin1_detected,
            pin1_index=pin1_index,
            outline=outline,
            overall_confidence=response.get("overall_confidence", 0.5),
            warnings=response.get("warnings", []),
        )

        return footprint, extraction_result


# =============================================================================
# Convenience Functions
# =============================================================================

def extract_footprint(
    image_path: str | Path,
    model: str = "haiku"
) -> ExtractionResponse:
    """
    Extract footprint from an image file.

    Convenience function that creates an extractor and runs extraction.

    Args:
        image_path: Path to the image file
        model: Model to use ('haiku', 'sonnet', 'opus')

    Returns:
        ExtractionResponse with results
    """
    extractor = FootprintExtractor(model=model)
    return extractor.extract_from_image(image_path)


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "haiku") -> float:
    """
    Estimate the cost of an extraction based on token usage.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model used

    Returns:
        Estimated cost in USD
    """
    # Pricing per 1M tokens (as of 2025)
    pricing = {
        "haiku": {"input": 0.25, "output": 1.25},
        "sonnet": {"input": 3.00, "output": 15.00},
        "opus": {"input": 15.00, "output": 75.00},
    }

    # Normalize model name
    model_key = model.lower()
    for key in pricing:
        if key in model_key:
            model_key = key
            break
    else:
        model_key = "haiku"  # Default

    rates = pricing[model_key]
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    return cost
