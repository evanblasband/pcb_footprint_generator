#!/usr/bin/env python3
"""
Test script for extraction with verification pass.

Usage:
    python run_verification_test.py <image_path>

This runs:
1. Original single-shot extraction
2. Verification pass to check for common errors
3. Applies corrections if needed
"""

import argparse
import os
import sys
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from extraction import FootprintExtractor
from verification import detect_suspicious_values, verify_extraction, apply_corrections


def main():
    parser = argparse.ArgumentParser(description="Test extraction with verification")
    parser.add_argument("image_path", help="Path to datasheet image")
    parser.add_argument("--model", default="sonnet", help="Model for extraction (default: sonnet)")
    args = parser.parse_args()

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Check image exists
    image_path = Path(args.image_path)
    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)

    # Read image
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    suffix = image_path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "image/png")

    print("=" * 60)
    print("STEP 1: Single-Shot Extraction")
    print("=" * 60)

    extractor = FootprintExtractor(model=args.model)
    result = extractor.extract_from_bytes(image_bytes, media_type)

    if not result.success:
        print(f"ERROR: Extraction failed: {result.error}")
        sys.exit(1)

    extraction = result.extraction_result
    print(f"Model: {result.model_used}")
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")

    # Show extraction results
    print(f"\nExtracted {len(extraction.pads)} pads:")
    for pad in extraction.pads[:5]:  # Show first 5
        print(f"  {pad.designator}: ({pad.x:.3f}, {pad.y:.3f}) {pad.width:.3f}x{pad.height:.3f}mm")
    if len(extraction.pads) > 5:
        print(f"  ... and {len(extraction.pads) - 5} more")

    print("\n" + "=" * 60)
    print("STEP 2: Check for Suspicious Values")
    print("=" * 60)

    suspicious = detect_suspicious_values(extraction)

    if not suspicious["needs_verification"]:
        print("No suspicious values detected - extraction looks good!")
        print(f"\nFinal confidence: {extraction.overall_confidence:.2f}")
        return

    print("Suspicious values found:")
    for reason in suspicious["reasons"]:
        print(f"  - {reason}")

    print("\n" + "=" * 60)
    print("STEP 3: Verification Pass")
    print("=" * 60)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    verification = verify_extraction(
        extraction,
        image_bytes,
        media_type,
        client,
        model="claude-haiku-4-5-20251001"  # Use Haiku for verification (cheap)
    )

    print(f"Verification tokens: {verification.input_tokens} in, {verification.output_tokens} out")

    if verification.error:
        print(f"ERROR: {verification.error}")
        return

    print(f"\nVerification result:")
    print(f"  Overall verified: {verification.verified}")
    print(f"  Confidence: {verification.confidence:.2f}")

    if verification.pad_dimensions_corrected:
        print(f"\n  Dimension correction needed:")
        print(f"    Issue: {verification.dimension_issue}")
        print(f"    Corrected width: {verification.corrected_pad_width}")
        print(f"    Corrected height: {verification.corrected_pad_height}")

    if verification.thermal_pad_issue:
        print(f"\n  Thermal pad issue: {verification.thermal_pad_issue}")

    print("\n" + "=" * 60)
    print("STEP 4: Apply Corrections")
    print("=" * 60)

    if verification.pad_dimensions_corrected:
        corrected = apply_corrections(extraction, verification)
        print("Corrected pads:")
        for pad in corrected.pads[:5]:
            print(f"  {pad.designator}: ({pad.x:.3f}, {pad.y:.3f}) {pad.width:.3f}x{pad.height:.3f}mm")
        if len(corrected.pads) > 5:
            print(f"  ... and {len(corrected.pads) - 5} more")

        if corrected.warnings:
            print("\nWarnings:")
            for w in corrected.warnings:
                print(f"  - {w}")
    else:
        print("No corrections needed.")

    # Cost summary
    print("\n" + "=" * 60)
    print("COST SUMMARY")
    print("=" * 60)
    extraction_cost = (result.input_tokens * 3.00 + result.output_tokens * 15.00) / 1_000_000
    verification_cost = (verification.input_tokens * 0.80 + verification.output_tokens * 4.00) / 1_000_000
    print(f"Extraction (Sonnet): ${extraction_cost:.4f}")
    print(f"Verification (Haiku): ${verification_cost:.4f}")
    print(f"Total: ${extraction_cost + verification_cost:.4f}")


if __name__ == "__main__":
    main()
