"""
Verification pass for extraction results.

This module implements a lightweight verification step that runs after
single-shot extraction to catch common errors like:
- Pad width confused with pitch/spacing
- Missing thermal pads
- Incorrect pad counts

The verification pass sends the extraction results back to the model
along with the original image and asks it to verify specific values.
"""

import base64
import json
from dataclasses import dataclass
from typing import Optional

import anthropic

from models import ExtractionResult, Pad


# =============================================================================
# Verification Prompts
# =============================================================================

VERIFICATION_PROMPT = """You are verifying a PCB footprint extraction. I extracted dimensions from this datasheet image and need you to check if they are correct.

## Extracted Values to Verify

{values_to_verify}

## CRITICAL: Understanding Width vs Height

In the OUTPUT format:
- **width** = horizontal dimension (X axis) of the pad
- **height** = vertical dimension (Y axis) of the pad

For pads on the LEFT and RIGHT sides of a package (like UDFN, QFN, SOIC):
- The pads extend HORIZONTALLY toward the center
- So the LONGER dimension should be the WIDTH (horizontal)
- And the SHORTER dimension should be the HEIGHT (vertical)

## Verification Task

1. **Pad dimensions check**: I extracted width={pad_width}mm, height={pad_height}mm.

   VISUALLY look at ONE signal pad on the left or right side of the package:
   - Does the pad extend horizontally toward the center? (most common for UDFN/QFN/SOIC)
   - If yes: the LONGER dimension should be width, SHORTER should be height

   Current extraction: width={pad_width}mm, height={pad_height}mm
   - Is the longer dimension ({longer_dim}mm) correctly assigned to the horizontal extent?

   Also check: Is either dimension actually the PITCH (spacing between pads)?
   - Pitch is the distance between pad CENTERS, not pad size
   - If a dimension equals the pitch, it's probably wrong

2. **Pad count check**: I found {pad_count} pads total.
   - Count the pads in the drawing (including any thermal/exposed pad)

3. **Thermal pad check**: {thermal_status}

## Response Format

Return JSON:
```json
{{
  "pad_dimensions_correct": true/false,
  "corrected_pad_width": <number or null if correct>,
  "corrected_pad_height": <number or null if correct>,
  "dimension_issue": "<explanation if wrong, null if correct>",

  "pad_count_correct": true/false,
  "corrected_pad_count": <number or null if correct>,

  "thermal_pad_correct": true/false,
  "thermal_pad_issue": "<explanation if wrong, null if correct>",

  "overall_verified": true/false,
  "confidence": <0.0-1.0>
}}
```

Return ONLY valid JSON."""


@dataclass
class VerificationResult:
    """Result from verification pass."""
    verified: bool
    pad_dimensions_corrected: bool = False
    corrected_pad_width: Optional[float] = None
    corrected_pad_height: Optional[float] = None
    dimension_issue: Optional[str] = None
    pad_count_corrected: bool = False
    corrected_pad_count: Optional[int] = None
    thermal_pad_issue: Optional[str] = None
    confidence: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None


def detect_suspicious_values(extraction_result: ExtractionResult) -> dict:
    """
    Analyze extraction result to find values that should be verified.

    Returns dict with suspicious findings that warrant verification.
    """
    suspicious = {
        "needs_verification": False,
        "reasons": []
    }

    if not extraction_result.pads:
        return suspicious

    # Get signal pads (exclude thermal pad which is typically much larger)
    signal_pads = [p for p in extraction_result.pads
                   if p.designator not in ("EP", "9", "thermal")]

    if not signal_pads:
        return suspicious

    # Check for pad width ≈ pitch (common error)
    # Calculate pitch from pad positions
    if len(signal_pads) >= 2:
        # Sort by Y position to find adjacent pads
        sorted_pads = sorted(signal_pads, key=lambda p: (p.x, p.y))

        pitches = []
        for i in range(len(sorted_pads) - 1):
            p1, p2 = sorted_pads[i], sorted_pads[i + 1]
            # Only compare pads on same side (similar X)
            if abs(p1.x - p2.x) < 0.5:
                pitch = abs(p1.y - p2.y)
                if pitch > 0.1:  # Ignore tiny differences
                    pitches.append(pitch)

        if pitches:
            avg_pitch = sum(pitches) / len(pitches)
            pad_width = signal_pads[0].width
            pad_height = signal_pads[0].height

            # Check if pad dimension is suspiciously close to pitch (common error)
            # Pad width is typically 40-70% of pitch
            # If either dimension is within 10% of pitch, it's likely confused
            width_ratio = pad_width / avg_pitch if avg_pitch > 0 else 0
            height_ratio = pad_height / avg_pitch if avg_pitch > 0 else 0

            # Suspicious if ratio is 0.90-1.10 (pad dimension ≈ pitch)
            width_matches_pitch = 0.90 <= width_ratio <= 1.10
            height_matches_pitch = 0.90 <= height_ratio <= 1.10

            if width_matches_pitch or height_matches_pitch:
                suspicious["needs_verification"] = True
                suspicious["reasons"].append(
                    f"Pad dimension ({pad_width}mm or {pad_height}mm) matches "
                    f"calculated pitch ({avg_pitch:.2f}mm) - possible confusion"
                )
                suspicious["likely_pitch"] = avg_pitch

    # Check for missing thermal pad in packages that typically have one
    has_thermal = any(p.designator in ("EP", "9", "thermal")
                      for p in extraction_result.pads)

    # If there are signal pads arranged peripherally, might expect thermal pad
    if not has_thermal and len(signal_pads) >= 8:
        suspicious["needs_verification"] = True
        suspicious["reasons"].append(
            "No thermal pad detected but package has 8+ signal pads - verify if EP exists"
        )

    return suspicious


def verify_extraction(
    extraction_result: ExtractionResult,
    image_bytes: bytes,
    media_type: str,
    client: anthropic.Anthropic,
    model: str = "claude-haiku-4-5-20251001"
) -> VerificationResult:
    """
    Run verification pass on extraction results.

    Args:
        extraction_result: The extraction to verify
        image_bytes: Original image bytes
        media_type: Image MIME type
        client: Anthropic API client
        model: Model to use for verification (default: Haiku for cost)

    Returns:
        VerificationResult with any corrections
    """
    # First check if verification is even needed
    suspicious = detect_suspicious_values(extraction_result)

    if not suspicious["needs_verification"]:
        return VerificationResult(
            verified=True,
            confidence=extraction_result.overall_confidence
        )

    # Get representative pad dimensions
    signal_pads = [p for p in extraction_result.pads
                   if p.designator not in ("EP", "9", "thermal")]

    if not signal_pads:
        return VerificationResult(verified=True, confidence=0.5)

    pad_width = signal_pads[0].width
    pad_height = signal_pads[0].height
    pad_count = len(extraction_result.pads)
    longer_dim = max(pad_width, pad_height)

    # Check thermal status
    has_thermal = any(p.designator in ("EP", "9", "thermal")
                      for p in extraction_result.pads)
    thermal_status = "A thermal pad WAS detected." if has_thermal else "NO thermal pad was detected."

    # Build verification prompt
    values_to_verify = "\n".join(f"- {reason}" for reason in suspicious["reasons"])

    prompt = VERIFICATION_PROMPT.format(
        values_to_verify=values_to_verify,
        pad_width=pad_width,
        pad_height=pad_height,
        longer_dim=longer_dim,
        pad_count=pad_count,
        thermal_status=thermal_status
    )

    # Encode image
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
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

        # Parse JSON response
        result = _parse_json(response_text)

        if result is None:
            return VerificationResult(
                verified=False,
                error="Could not parse verification response",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

        return VerificationResult(
            verified=result.get("overall_verified", False),
            pad_dimensions_corrected=not result.get("pad_dimensions_correct", True),
            corrected_pad_width=result.get("corrected_pad_width"),
            corrected_pad_height=result.get("corrected_pad_height"),
            dimension_issue=result.get("dimension_issue"),
            pad_count_corrected=not result.get("pad_count_correct", True),
            corrected_pad_count=result.get("corrected_pad_count"),
            thermal_pad_issue=result.get("thermal_pad_issue"),
            confidence=result.get("confidence", 0.5),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

    except Exception as e:
        return VerificationResult(
            verified=False,
            error=f"Verification failed: {str(e)}"
        )


def apply_corrections(
    extraction_result: ExtractionResult,
    verification: VerificationResult
) -> ExtractionResult:
    """
    Apply verified corrections to extraction result.

    Args:
        extraction_result: Original extraction
        verification: Verification result with corrections

    Returns:
        Updated ExtractionResult with corrections applied
    """
    if verification.verified and not verification.pad_dimensions_corrected:
        return extraction_result

    # Create a copy of pads with corrections
    corrected_pads = []

    for pad in extraction_result.pads:
        # Skip thermal pad for dimension corrections
        if pad.designator in ("EP", "9", "thermal"):
            corrected_pads.append(pad)
            continue

        new_width = verification.corrected_pad_width or pad.width
        new_height = verification.corrected_pad_height or pad.height

        corrected_pad = Pad(
            designator=pad.designator,
            x=pad.x,
            y=pad.y,
            width=new_width,
            height=new_height,
            rotation=pad.rotation,
            shape=pad.shape,
            pad_type=pad.pad_type,
            drill=pad.drill,
            confidence=verification.confidence
        )
        corrected_pads.append(corrected_pad)

    # Build warnings list
    warnings = list(extraction_result.warnings)
    if verification.dimension_issue:
        warnings.append(f"Corrected: {verification.dimension_issue}")
    if verification.thermal_pad_issue:
        warnings.append(f"Thermal pad: {verification.thermal_pad_issue}")

    return ExtractionResult(
        package_type=extraction_result.package_type,
        standard_detected=extraction_result.standard_detected,
        units=extraction_result.units,
        pads=corrected_pads,
        vias=extraction_result.vias,
        pin1_detected=extraction_result.pin1_detected,
        pin1_index=extraction_result.pin1_index,
        outline=extraction_result.outline,
        overall_confidence=verification.confidence,
        warnings=warnings
    )


def _parse_json(text: str) -> Optional[dict]:
    """Parse JSON from response text."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    if "```" in text:
        start = text.find("```") + 3
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
