#!/usr/bin/env python3
"""
Test script for staged extraction pipeline.

Usage:
    python run_staged_extraction_test.py <image_path> [--stage 1|2|all]

Examples:
    # Test Stage 1 only (table parsing)
    python run_staged_extraction_test.py ../example_datasheets/ATECC608A.png --stage 1

    # Run full pipeline
    python run_staged_extraction_test.py ../example_datasheets/ATECC608A.png --stage all
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import anthropic

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # dotenv not installed, rely on environment

from prompts_staged import get_stage1_prompt, get_stage2_prompt


def encode_image(image_path: Path) -> tuple[str, str]:
    """Encode image to base64 and determine media type."""
    suffix = image_path.suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "image/png")

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    return image_base64, media_type


def run_stage1(image_path: Path, client: anthropic.Anthropic) -> dict:
    """
    Run Stage 1: Scene analysis and table parsing.

    Uses Haiku for cost efficiency.
    """
    print("\n" + "=" * 60)
    print("STAGE 1: Scene Analysis + Table Parsing")
    print("=" * 60)

    image_base64, media_type = encode_image(image_path)
    prompt = get_stage1_prompt()

    print(f"Using model: claude-haiku-4-5-20251001")
    print(f"Image: {image_path.name}")
    print("-" * 60)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
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

    # Parse response
    response_text = response.content[0].text

    # Try to extract JSON
    try:
        # Direct parse
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # Try extracting from code block
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            result = json.loads(response_text[start:end].strip())
        elif "```" in response_text:
            start = response_text.find("```") + 3
            newline = response_text.find("\n", start)
            start = newline + 1
            end = response_text.find("```", start)
            result = json.loads(response_text[start:end].strip())
        else:
            print("ERROR: Could not parse JSON from response")
            print("Raw response:")
            print(response_text)
            return {}

    # Print results
    print("\nStage 1 Results:")
    print("-" * 60)
    print(f"Drawing format: {result.get('drawing_format')}")
    print(f"Package type: {result.get('package_type')}")
    print(f"Pad arrangement: {result.get('pad_arrangement')}")
    print(f"Estimated pad count: {result.get('estimated_pad_count')}")
    print(f"Has thermal pad: {result.get('has_thermal_pad')}")
    print(f"Has thermal vias: {result.get('has_thermal_vias')}")
    print(f"Units: {result.get('units_detected')}")

    print("\nDimension Table:")
    for label, value in result.get("dimension_table", {}).items():
        print(f"  {label}: {value} mm")

    if result.get("dimension_semantics"):
        print("\nDimension Semantics (what each label means):")
        for key, label in result.get("dimension_semantics", {}).items():
            if label:
                print(f"  {key}: {label}")

    if result.get("warnings"):
        print("\nWarnings:")
        for warning in result.get("warnings", []):
            print(f"  - {warning}")

    # Cost info
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * 0.80 + output_tokens * 4.00) / 1_000_000
    print(f"\nTokens: {input_tokens} in, {output_tokens} out")
    print(f"Estimated cost: ${cost:.4f}")

    return result


def run_stage2(image_path: Path, stage1_result: dict, client: anthropic.Anthropic) -> dict:
    """
    Run Stage 2: Geometry extraction with table context.

    Uses Sonnet for accuracy.
    """
    print("\n" + "=" * 60)
    print("STAGE 2: Geometry Extraction with Table Context")
    print("=" * 60)

    image_base64, media_type = encode_image(image_path)
    prompt = get_stage2_prompt(stage1_result)

    print(f"Using model: claude-sonnet-4-5-20250929")
    print(f"Using dimension table from Stage 1")
    print("-" * 60)

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
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

    # Parse response
    response_text = response.content[0].text

    # Try to extract JSON
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            result = json.loads(response_text[start:end].strip())
        elif "```" in response_text:
            start = response_text.find("```") + 3
            newline = response_text.find("\n", start)
            start = newline + 1
            end = response_text.find("```", start)
            result = json.loads(response_text[start:end].strip())
        else:
            print("ERROR: Could not parse JSON from response")
            print("Raw response:")
            print(response_text[:2000])
            return {}

    # Print results
    print("\nStage 2 Results:")
    print("-" * 60)
    print(f"Footprint name: {result.get('footprint_name')}")
    print(f"Overall confidence: {result.get('overall_confidence', 0):.2f}")

    print(f"\nPads ({len(result.get('pads', []))} total):")
    for pad in result.get("pads", []):
        pad_type = pad.get("pad_type", "smd")
        shape = pad.get("shape", "rectangular")
        print(f"  {pad.get('designator'):>3}: ({pad.get('x'):>6.3f}, {pad.get('y'):>6.3f}) "
              f"{pad.get('width'):.3f}x{pad.get('height'):.3f}mm {shape} {pad_type} "
              f"conf={pad.get('confidence', 0):.2f}")

    if result.get("vias"):
        print(f"\nVias ({len(result.get('vias', []))} total):")
        for i, via in enumerate(result.get("vias", []), 1):
            print(f"  Via {i}: ({via.get('x'):>6.3f}, {via.get('y'):>6.3f}) "
                  f"drill={via.get('drill_diameter'):.2f}mm outer={via.get('outer_diameter'):.2f}mm")

    outline = result.get("outline", {})
    if outline:
        print(f"\nOutline: {outline.get('width', 0)}mm x {outline.get('height', 0)}mm")

    pin1 = result.get("pin1_location", {})
    if pin1:
        print(f"\nPin 1: {pin1.get('designator')} ({pin1.get('indicator_type')}) "
              f"confidence={pin1.get('confidence', 0):.2f}")

    if result.get("warnings"):
        print("\nWarnings:")
        for warning in result.get("warnings", []):
            print(f"  - {warning}")

    # Cost info
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * 3.00 + output_tokens * 15.00) / 1_000_000
    print(f"\nTokens: {input_tokens} in, {output_tokens} out")
    print(f"Estimated cost: ${cost:.4f}")

    # Total cost
    return result


def main():
    parser = argparse.ArgumentParser(description="Test staged extraction pipeline")
    parser.add_argument("image_path", help="Path to datasheet image")
    parser.add_argument(
        "--stage",
        choices=["1", "2", "all"],
        default="1",
        help="Which stage to run (default: 1)",
    )
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

    # Create client
    client = anthropic.Anthropic(api_key=api_key)

    # Run stages
    if args.stage in ["1", "all"]:
        stage1_result = run_stage1(image_path, client)

        if args.stage == "all" and stage1_result:
            stage2_result = run_stage2(image_path, stage1_result, client)


if __name__ == "__main__":
    main()
