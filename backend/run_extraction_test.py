#!/usr/bin/env python3
"""
Extraction Test Script - Spike 2

Tests Claude Vision API extraction on example datasheet images.
Compares results to ground truth where available.

Usage:
    export ANTHROPIC_API_KEY="your-key-here"
    python run_extraction_test.py

Or run a single image:
    python run_extraction_test.py path/to/image.png
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from extraction import FootprintExtractor, estimate_cost
from models import PadShape, PadType


# =============================================================================
# Ground Truth Data for Comparison
# =============================================================================

# SO-8EP ground truth from documents/Raw Ground Truth Data - Altium Exports.pdf
SO_8EP_GROUND_TRUTH = {
    "name": "SO-8EP",
    "pad_count": 9,
    "via_count": 6,
    "expected_pads": [
        {"designator": "1", "x": -2.498, "y": 1.905, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "2", "x": -2.498, "y": 0.635, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "3", "x": -2.498, "y": -0.635, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "4", "x": -2.498, "y": -1.905, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "5", "x": 2.498, "y": -1.905, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "6", "x": 2.498, "y": -0.635, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "7", "x": 2.498, "y": 0.635, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "8", "x": 2.498, "y": 1.905, "width": 0.802, "height": 1.505, "rotation": 90},
        {"designator": "9", "x": 0, "y": 0, "width": 2.613, "height": 3.502, "rotation": 0},  # Thermal pad
    ]
}


def print_separator(char="-", length=70):
    """Print a separator line."""
    print(char * length)


def print_extraction_result(result, image_name: str):
    """Pretty-print extraction results."""
    print_separator("=")
    print(f"EXTRACTION RESULTS: {image_name}")
    print_separator("=")

    if not result.success:
        print(f"❌ EXTRACTION FAILED: {result.error}")
        return

    print(f"✅ Extraction successful!")
    print(f"   Model: {result.model_used}")
    print(f"   Tokens: {result.input_tokens} in, {result.output_tokens} out")
    print(f"   Est. cost: ${estimate_cost(result.input_tokens, result.output_tokens):.4f}")
    print()

    fp = result.footprint
    er = result.extraction_result

    print(f"Footprint Name: {fp.name}")
    print(f"Overall Confidence: {er.overall_confidence:.2f}")
    print(f"Pin 1 Detected: {er.pin1_detected}")
    if er.pin1_index is not None:
        print(f"Pin 1 Index: {er.pin1_index}")
    print(f"Outline: {fp.outline.width}mm x {fp.outline.height}mm")
    print()

    if er.warnings:
        print("⚠️  Warnings:")
        for warn in er.warnings:
            print(f"   - {warn}")
        print()

    print(f"Pads ({len(fp.pads)}):")
    print_separator("-", 90)
    print(f"{'#':<4} {'Desig':<6} {'X':>8} {'Y':>8} {'W':>7} {'H':>7} {'Rot':>5} {'Shape':<12} {'Type':<5} {'Conf':>5}")
    print_separator("-", 90)

    for i, pad in enumerate(fp.pads):
        # Get confidence from raw response if available
        conf = ""
        if result.raw_response and "pads" in result.raw_response:
            if i < len(result.raw_response["pads"]):
                conf = f"{result.raw_response['pads'][i].get('confidence', 0):.2f}"

        print(f"{i+1:<4} {pad.designator:<6} {pad.x:>8.3f} {pad.y:>8.3f} "
              f"{pad.width:>7.3f} {pad.height:>7.3f} {pad.rotation:>5.0f} "
              f"{pad.shape.value:<12} {pad.pad_type.value:<5} {conf:>5}")

    print_separator("-", 90)
    print()


def compare_to_ground_truth(result, ground_truth: dict) -> dict:
    """
    Compare extraction result to ground truth data.

    Handles:
    - Alternate designators (EP, 9, thermal for thermal pad)
    - 90° rotation differences between extraction and ground truth
    - Width/height swaps due to rotation
    """
    if not result.success:
        return {"error": "Extraction failed"}

    fp = result.footprint
    comparisons = {
        "pad_count_match": len(fp.pads) == ground_truth["pad_count"],
        "pad_count_expected": ground_truth["pad_count"],
        "pad_count_actual": len(fp.pads),
        "pad_errors": [],
        "dimension_errors": [],  # Separate category for W/H issues
        "rotation_detected": False,
    }

    # Alternate designator mappings (extraction -> ground truth)
    designator_aliases = {
        "EP": "9", "ep": "9", "THERMAL": "9", "thermal": "9", "GND": "9",
    }

    # Compare individual pads
    for expected in ground_truth["expected_pads"]:
        # Find matching pad by designator (with aliases)
        actual = None
        for pad in fp.pads:
            pad_desig = pad.designator
            # Check direct match or alias
            if pad_desig == expected["designator"]:
                actual = pad
                break
            if designator_aliases.get(pad_desig) == expected["designator"]:
                actual = pad
                break

        if actual is None:
            comparisons["pad_errors"].append({
                "designator": expected["designator"],
                "error": "Pad not found in extraction"
            })
            continue

        # Try both orientations for position comparison
        # Original orientation
        x_error_orig = abs(actual.x - expected["x"])
        y_error_orig = abs(actual.y - expected["y"])

        # 90° rotated (swap X and Y, may need sign flip)
        x_error_rot = abs(actual.y - expected["x"])  # actual.y matches expected.x
        y_error_rot = abs(actual.x - expected["y"])  # actual.x matches expected.y

        # Also try with sign flips for different rotation directions
        x_error_rot2 = abs(-actual.y - expected["x"])
        y_error_rot2 = abs(actual.x - expected["y"])

        # Find best position match
        pos_error_orig = max(x_error_orig, y_error_orig)
        pos_error_rot = max(x_error_rot, y_error_rot)
        pos_error_rot2 = max(x_error_rot2, y_error_rot2)

        best_pos_error = min(pos_error_orig, pos_error_rot, pos_error_rot2)
        if best_pos_error == pos_error_rot or best_pos_error == pos_error_rot2:
            comparisons["rotation_detected"] = True

        # Compare dimensions (width/height might be swapped due to rotation)
        w_error_orig = abs(actual.width - expected["width"])
        h_error_orig = abs(actual.height - expected["height"])

        # Swapped (rotation swaps width/height)
        w_error_swap = abs(actual.width - expected["height"])
        h_error_swap = abs(actual.height - expected["width"])

        dim_error_orig = max(w_error_orig, h_error_orig)
        dim_error_swap = max(w_error_swap, h_error_swap)

        best_dim_error = min(dim_error_orig, dim_error_swap)

        # Report errors
        tolerance = 0.1  # 0.1mm tolerance (relaxed for rotation handling)

        if best_pos_error > tolerance:
            comparisons["pad_errors"].append({
                "designator": expected["designator"],
                "position_error": best_pos_error,
                "note": "Position mismatch" + (" (rotation adjusted)" if comparisons["rotation_detected"] else "")
            })

        if best_dim_error > tolerance:
            comparisons["dimension_errors"].append({
                "designator": expected["designator"],
                "expected_w": expected["width"],
                "expected_h": expected["height"],
                "actual_w": actual.width,
                "actual_h": actual.height,
                "error": best_dim_error,
            })

    return comparisons


def print_ground_truth_comparison(result, ground_truth: dict, name: str):
    """Print ground truth comparison."""
    print_separator("=")
    print(f"GROUND TRUTH COMPARISON: {name}")
    print_separator("=")

    comp = compare_to_ground_truth(result, ground_truth)

    if "error" in comp:
        print(f"❌ {comp['error']}")
        return

    # Rotation detection
    if comp.get("rotation_detected"):
        print("ℹ️  90° rotation detected between extraction and ground truth")

    # Pad count
    if comp["pad_count_match"]:
        print(f"✅ Pad count: {comp['pad_count_actual']} (expected {comp['pad_count_expected']})")
    else:
        print(f"❌ Pad count: {comp['pad_count_actual']} (expected {comp['pad_count_expected']})")

    # Position errors
    if not comp["pad_errors"]:
        print("✅ All pad positions within tolerance (rotation-adjusted)")
    else:
        print(f"⚠️  {len(comp['pad_errors'])} pads with position errors:")
        for err in comp["pad_errors"]:
            if "error" in err:
                print(f"   - Pad {err['designator']}: {err['error']}")
            elif "position_error" in err:
                print(f"   - Pad {err['designator']}: {err['position_error']:.3f}mm {err.get('note', '')}")

    # Dimension errors (separate from position)
    dim_errors = comp.get("dimension_errors", [])
    if not dim_errors:
        print("✅ All pad dimensions within tolerance")
    else:
        print(f"⚠️  {len(dim_errors)} pads with dimension errors:")
        for err in dim_errors:
            print(f"   - Pad {err['designator']}: expected {err['expected_w']:.3f}x{err['expected_h']:.3f}mm, "
                  f"got {err['actual_w']:.3f}x{err['actual_h']:.3f}mm (error: {err['error']:.3f}mm)")

    print()


def run_extraction_test(image_path: Path, extractor: FootprintExtractor) -> dict:
    """Run extraction on a single image."""
    print(f"\n📷 Testing: {image_path.name}")
    print(f"   Path: {image_path}")

    result = extractor.extract_from_image(image_path)
    print_extraction_result(result, image_path.name)

    # Compare to ground truth if available
    if "so-8ep" in image_path.name.lower():
        print_ground_truth_comparison(result, SO_8EP_GROUND_TRUTH, "SO-8EP")

    return result


def main():
    """Main test runner."""
    print_separator("=")
    print("PCB FOOTPRINT EXTRACTION TEST - SPIKE 2")
    print_separator("=")

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        print()
        print("Please set your API key:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    print(f"✅ API key found (length: {len(api_key)})")

    # Create extractor
    try:
        extractor = FootprintExtractor(api_key=api_key, model="haiku")
        print(f"✅ Extractor initialized with model: {extractor.model}")
    except Exception as e:
        print(f"❌ Failed to create extractor: {e}")
        sys.exit(1)

    # Determine which images to test
    if len(sys.argv) > 1:
        # Test specific image
        image_path = Path(sys.argv[1])
        if not image_path.exists():
            print(f"❌ Image not found: {image_path}")
            sys.exit(1)
        images = [image_path]
    else:
        # Test all example images
        example_dir = Path(__file__).parent.parent / "example_datasheets"
        if not example_dir.exists():
            print(f"❌ Example directory not found: {example_dir}")
            sys.exit(1)

        images = sorted(example_dir.glob("*.png"))
        if not images:
            print(f"❌ No PNG images found in {example_dir}")
            sys.exit(1)

        print(f"📁 Found {len(images)} example images")

    # Run extraction on each image
    results = {}
    total_cost = 0.0

    for image_path in images:
        result = run_extraction_test(image_path, extractor)
        results[image_path.name] = result

        if result.success:
            cost = estimate_cost(result.input_tokens, result.output_tokens)
            total_cost += cost

    # Summary
    print_separator("=")
    print("SUMMARY")
    print_separator("=")

    success_count = sum(1 for r in results.values() if r.success)
    print(f"Successful extractions: {success_count}/{len(results)}")
    print(f"Total estimated cost: ${total_cost:.4f}")

    print()
    print("Results by image:")
    for name, result in results.items():
        status = "✅" if result.success else "❌"
        if result.success:
            conf = result.extraction_result.overall_confidence
            pads = len(result.footprint.pads)
            print(f"  {status} {name}: {pads} pads, confidence {conf:.2f}")
        else:
            print(f"  {status} {name}: {result.error}")


if __name__ == "__main__":
    main()
