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

# RJ45 Connector ground truth (LPJG0926HENL)
# From documents/Raw Ground Truth Data - Altium Exports.pdf
# 22 total pads: pins 1-20 + Un1, Un2 (mounting)
RJ45_GROUND_TRUTH = {
    "name": "RJ45",
    "pad_count": 22,
    "expected_pads": [
        # Signal pins - 0.9mm drill, 1.5mm pad diameter
        {"designator": "1", "x": -5.715, "y": 8.89, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "rounded_rectangle"},
        {"designator": "2", "x": -4.445, "y": 6.35, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "3", "x": -3.175, "y": 8.89, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "4", "x": -1.905, "y": 6.35, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "5", "x": -0.635, "y": 8.89, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "6", "x": 0.635, "y": 6.35, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "7", "x": 1.905, "y": 8.89, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "8", "x": 3.175, "y": 6.35, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "9", "x": 4.445, "y": 8.89, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "10", "x": 5.715, "y": 6.35, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "11", "x": -5.715, "y": 3.83, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "12", "x": -3.175, "y": 2.56, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "13", "x": 3.175, "y": 2.56, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        {"designator": "14", "x": 5.715, "y": 3.83, "width": 1.5, "height": 1.5, "drill": 0.9, "shape": "round"},
        # Bottom row pins - 1.02mm drill
        {"designator": "15", "x": -6.63, "y": -4.06, "width": 1.5, "height": 1.5, "drill": 1.02, "shape": "round"},
        {"designator": "16", "x": -4.09, "y": -4.06, "width": 1.5, "height": 1.5, "drill": 1.02, "shape": "round"},
        {"designator": "17", "x": 4.09, "y": -4.06, "width": 1.5, "height": 1.5, "drill": 1.02, "shape": "round"},
        {"designator": "18", "x": 6.63, "y": -4.06, "width": 1.5, "height": 1.5, "drill": 1.02, "shape": "round"},
        # Larger pins - 1.7mm drill, 2.5mm pad
        {"designator": "19", "x": -7.875, "y": 3.05, "width": 2.5, "height": 2.5, "drill": 1.7, "shape": "round"},
        {"designator": "20", "x": 7.875, "y": 3.05, "width": 2.5, "height": 2.5, "drill": 1.7, "shape": "round"},
        # Mounting holes - 3.2mm drill, 3.2mm pad
        {"designator": "Un1", "x": -5.715, "y": 0, "width": 3.2, "height": 3.2, "drill": 3.2, "shape": "round"},
        {"designator": "Un2", "x": 5.715, "y": 0, "width": 3.2, "height": 3.2, "drill": 3.2, "shape": "round"},
    ],
    "notes": [
        "22 total: pins 1-20 + Un1/Un2 mounting holes",
        "Drill sizes: 0.9mm (1-14), 1.02mm (15-18), 1.7mm (19-20), 3.2mm (Un1-Un2)",
        "Pin 1 has rounded rectangle shape for identification",
    ]
}

# USB 3.0 Connector ground truth (GSB3115XXXXF1HR)
# From documents/Raw Ground Truth Data - Altium Exports.pdf
# Has slotted mounting holes (SH1-SH4)
USB3_GROUND_TRUTH = {
    "name": "USB3",
    "pad_count": None,  # Need to count from full PDF
    "expected_pads": [
        # Signal pin 1
        {"designator": "1", "x": -3.5, "y": -0.57, "width": 1.25, "height": 1.25, "drill": 0.75, "shape": "rectangular"},
        # Slotted mounting holes
        {"designator": "SH1", "x": -6.4, "y": 0, "width": 3.05, "height": 1.25, "drill": 0.65, "slot_length": 2.45, "shape": "round"},
        {"designator": "SH2", "x": 6.4, "y": 0, "width": 3.05, "height": 1.25, "drill": 0.65, "slot_length": 2.45, "shape": "round"},
        {"designator": "SH3", "x": -7.8, "y": -7.5, "width": 2.15, "height": 1.075, "drill": 0.65, "slot_length": 1.65, "shape": "round"},
        {"designator": "SH4", "x": 7.8, "y": -7.5, "width": 2.15, "height": 1.075, "drill": 0.65, "slot_length": 1.65, "shape": "round"},
    ],
    "notes": [
        "Has slotted mounting holes (SH1-SH4)",
        "SH1/SH2: 2.45mm slot length, 0.65mm drill width",
        "SH3/SH4: 1.65mm slot length, 0.65mm drill width",
        "Full pad list not available in ground truth PDF",
    ]
}

# M.2 Mini PCIe ground truth
# Note: Full ground truth not available in PDF - only partial dimensions visible
M2_GROUND_TRUTH = {
    "name": "M2_MINI_PCIE",
    "pad_count": 75,  # 75 signal pads + mounting holes
    "expected_pads": [
        # Only corner pads are typically dimensioned in datasheets
        # Full ground truth would need to be extracted from Altium
    ],
    "notes": [
        "SMD edge connector with 75 signal pads",
        "0.5mm pitch between pads",
        "Pad size approximately 0.35mm x 2.75mm",
        "Ground truth PDF does not include M.2 data",
        "Extraction challenge: datasheets often only dimension corner pads",
    ]
}

# Samtec HLE ground truth
# Note: Ground truth not in PDF (Examples 3 & 4 use mils, may be different format)
SAMTEC_GROUND_TRUTH = {
    "name": "SAMTEC_HLE",
    "pad_count": 42,  # From PRD
    "expected_pads": [],
    "notes": [
        "Mixed SMD + TH connector",
        "Ground truth PDF may have data in mils (need conversion)",
        "42 pads total per PRD",
    ]
}


def get_ground_truth_for_image(image_name: str) -> dict | None:
    """
    Get ground truth data for an image by matching filename patterns.

    Returns None if no ground truth is available.
    """
    name_lower = image_name.lower()

    if "so-8ep" in name_lower or "so8ep" in name_lower:
        return SO_8EP_GROUND_TRUTH
    elif "rj45" in name_lower or "lpjg" in name_lower:
        return RJ45_GROUND_TRUTH
    elif "usb3" in name_lower or "usb_3" in name_lower:
        return USB3_GROUND_TRUTH
    elif "m2" in name_lower or "mini_pcie" in name_lower or "minipcie" in name_lower:
        return M2_GROUND_TRUTH
    elif "samtec" in name_lower or "hle" in name_lower:
        return SAMTEC_GROUND_TRUTH

    return None


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
    print_separator("-", 100)
    print(f"{'#':<4} {'Desig':<6} {'X':>8} {'Y':>8} {'W':>7} {'H':>7} {'Drill':>6} {'Rot':>5} {'Shape':<12} {'Type':<5} {'Conf':>5}")
    print_separator("-", 100)

    for i, pad in enumerate(fp.pads):
        # Get confidence from raw response if available
        conf = ""
        if result.raw_response and "pads" in result.raw_response:
            if i < len(result.raw_response["pads"]):
                conf = f"{result.raw_response['pads'][i].get('confidence', 0):.2f}"

        # Get drill diameter if available
        drill_str = ""
        if pad.drill and pad.drill.diameter:
            drill_str = f"{pad.drill.diameter:.2f}"

        print(f"{i+1:<4} {pad.designator:<6} {pad.x:>8.3f} {pad.y:>8.3f} "
              f"{pad.width:>7.3f} {pad.height:>7.3f} {drill_str:>6} {pad.rotation:>5.0f} "
              f"{pad.shape.value:<12} {pad.pad_type.value:<5} {conf:>5}")

    print_separator("-", 100)
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
    ground_truth = get_ground_truth_for_image(image_path.name)
    if ground_truth:
        # Only compare if we have expected pads defined
        if ground_truth.get("expected_pads"):
            print_ground_truth_comparison(result, ground_truth, ground_truth["name"])
        else:
            # Show notes about what we know
            print_separator("=")
            print(f"GROUND TRUTH: {ground_truth['name']}")
            print_separator("=")
            if ground_truth.get("pad_count"):
                actual_count = len(result.footprint.pads) if result.success else 0
                expected = ground_truth["pad_count"]
                status = "✅" if actual_count == expected else "❌"
                print(f"{status} Pad count: {actual_count} (expected {expected})")
            if ground_truth.get("notes"):
                print("\nNotes:")
                for note in ground_truth["notes"]:
                    print(f"  - {note}")
            print("\n⚠️  Detailed pad comparison not available - ground truth needs values")
            print()

    return result


def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Test PCB footprint extraction")
    parser.add_argument("image", nargs="?", help="Path to image file (optional, tests all if omitted)")
    parser.add_argument("--model", "-m", choices=["haiku", "sonnet", "opus"], default="haiku",
                        help="Model to use (default: haiku)")
    args = parser.parse_args()

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
        extractor = FootprintExtractor(api_key=api_key, model=args.model)
        print(f"✅ Extractor initialized with model: {extractor.model}")
    except Exception as e:
        print(f"❌ Failed to create extractor: {e}")
        sys.exit(1)

    # Determine which images to test
    if args.image:
        # Test specific image
        image_path = Path(args.image)
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
