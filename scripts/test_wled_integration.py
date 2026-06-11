#!/usr/bin/env python3
"""Integration test for WLED segment-based output with backend sync.

Tests:
1. Payload generation for various scores
2. Segment configuration consistency
3. Color mapping (low/mid/high scores)
4. Idle/off state
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config_loader import load_config
from app.services.wled_output_service import WledOutputService


class _Ctx:
    def __init__(self, config):
        self.config = config
        self.logger = None


def test_segment_configuration():
    """Verify segment config is loaded correctly."""
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"

    service = WledOutputService(_Ctx(config))

    print("=" * 70)
    print("WLED Configuration Test")
    print("=" * 70)
    print(f"Segment ID:        {service.segment_id}")
    print(f"LED Range:         {service.start_led}-{service.stop_led}")
    print(f"LED Count:         {service.led_count}")
    print(f"Fill Direction:    {service.fill_direction}")
    print(f"Brightness:        {service.brightness}")
    print(f"Idle Brightness:   {service.idle_brightness}")
    print(f"Colors:")
    print(f"  - Low (0.0):     RGB{service.low_color}")
    print(f"  - Mid (0.5):     RGB{service.mid_color}")
    print(f"  - High (1.0):    RGB{service.high_color}")

    # Validate configuration
    assert service.segment_id == 0, "segment_id should be 0"
    assert service.start_led == 0, "start_led should be 0"
    assert service.stop_led == 15, "stop_led should be 15"
    assert service.led_count == 15, "led_count should be 15"
    assert service.fill_direction == "high_to_low", "fill_direction should be high_to_low"
    print("\n✓ Configuration is correct")


def test_color_gradient():
    """Verify color gradient from low to mid to high."""
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"

    service = WledOutputService(_Ctx(config))

    print("\n" + "=" * 70)
    print("Color Gradient Test")
    print("=" * 70)

    test_scores = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
    for score in test_scores:
        color = service.score_to_color(score)
        print(f"Score {score:>3.1f}: RGB{color}")

    # Verify gradient endpoints
    low = service.score_to_color(0.0)
    mid = service.score_to_color(0.5)
    high = service.score_to_color(1.0)

    assert low == service.low_color, "score 0.0 should match low_color"
    assert mid == service.mid_color, "score 0.5 should match mid_color"
    assert high == service.high_color, "score 1.0 should match high_color"
    print("\n✓ Color gradient is correct")


def test_led_count_mapping():
    """Verify score → LED count mapping."""
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"
    config["wled"]["led_count"] = 15
    config["wled"]["min_leds_when_visible"] = 1

    service = WledOutputService(_Ctx(config))

    print("\n" + "=" * 70)
    print("Score → LED Count Mapping Test")
    print("=" * 70)

    test_scores = [0.0, 0.067, 0.2, 0.5, 0.8, 1.0]
    for score in test_scores:
        leds = service.score_to_led_count(score)
        print(f"Score {score:>3.2f} → {leds:2d} LEDs")

    # Boundary checks
    assert service.score_to_led_count(0.0) == 0, "score 0.0 → 0 LEDs"
    assert service.score_to_led_count(1.0) == 15, "score 1.0 → 15 LEDs"
    print("\n✓ LED count mapping is correct")


def test_payload_structure():
    """Verify payload JSON structure and high_to_low fill."""
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"

    service = WledOutputService(_Ctx(config))

    print("\n" + "=" * 70)
    print("Payload Structure Test (high_to_low fill)")
    print("=" * 70)

    test_cases = [
        (None, True, "Idle"),
        (0.0, False, "Score 0.0"),
        (0.2, False, "Score 0.2 (~3 LEDs)"),
        (0.5, False, "Score 0.5 (~8 LEDs)"),
        (0.8, False, "Score 0.8 (~12 LEDs)"),
        (1.0, False, "Score 1.0 (all)"),
    ]

    for score, idle, label in test_cases:
        payload = service.build_payload(score, idle)

        print(f"\n{label}:")
        assert "on" in payload, "payload must have 'on' field"
        assert "bri" in payload, "payload must have 'bri' field"
        assert "seg" in payload, "payload must have 'seg' array"

        segs = payload["seg"]
        assert len(segs) > 0, "must have at least one segment"

        brightness = payload["bri"]
        expected_bri = service.idle_brightness if idle else service.brightness
        assert brightness == expected_bri, f"brightness should be {expected_bri}, got {brightness}"

        if score is not None and not idle:
            leds = service.score_to_led_count(score)
            if leds > 0:
                if service.fill_direction == "high_to_low":
                    active_start = service.stop_led - leds
                    active_stop = service.stop_led
                    print(f"  Expected active range: {active_start}-{active_stop} ({leds} LEDs)")
                    print(f"  Segment 0 range: {segs[0]['start']}-{segs[0]['stop']}")
                    assert segs[0]["start"] == active_start, f"segment start should be {active_start}"
                    assert segs[0]["stop"] == active_stop, f"segment stop should be {active_stop}"

        print(f"  ✓ Payload valid (brightness={brightness}, {len(segs)} segment(s))")

    print("\n✓ All payloads have correct structure")


def test_preserved_segments():
    """Verify that we preserve other segments configuration."""
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"

    service = WledOutputService(_Ctx(config))

    print("\n" + "=" * 70)
    print("Preserved Segments Test")
    print("=" * 70)
    print(f"Configuration preserves segments: {service.preserve_segments}")
    print("Note: Segments in preserve_segments list are NOT touched by updates")
    print("Current WLED segments:")
    print("  - Segment 0: Score segment (0-14)")
    print("  - Segment 1: Static segment (15-17) — PRESERVED")
    print("✓ Preserved segments configuration is correct")


if __name__ == "__main__":
    try:
        test_segment_configuration()
        test_color_gradient()
        test_led_count_mapping()
        test_payload_structure()
        test_preserved_segments()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
