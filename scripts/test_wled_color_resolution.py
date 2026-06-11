#!/usr/bin/env python3
"""Detailed test of WLED color and LED resolution across full score range.

Shows exactly which LEDs and colors are active at each score level
to verify granularity and color progression.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config_loader import load_config
from app.services.wled_output_service import WledOutputService


class _Ctx:
    def __init__(self, config):
        self.config = config
        self.logger = None


def color_to_hex(rgb):
    """Convert RGB tuple to hex string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def test_full_range():
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"

    service = WledOutputService(_Ctx(config))

    print("=" * 80)
    print("WLED Color & LED Resolution Test (Full Score Range)")
    print("=" * 80)
    print(f"LED Range: {service.start_led}-{service.stop_led} ({service.led_count} total)")
    print(f"Fill Direction: {service.fill_direction}")
    print(f"Low Color (0.0):  RGB{service.low_color}  {color_to_hex(service.low_color)}")
    print(f"Mid Color (0.5):  RGB{service.mid_color}  {color_to_hex(service.mid_color)}")
    print(f"High Color (1.0): RGB{service.high_color}  {color_to_hex(service.high_color)}")
    print("=" * 80)

    # Test at regular intervals to show full progression
    test_scores = []
    for i in range(21):  # 0, 0.05, 0.10, ..., 1.00
        test_scores.append(i * 0.05)

    print("\nScore → LED Count + Color Progression:")
    print("-" * 80)
    print(f"{'Score':<8} {'LED Count':<12} {'Active Range':<20} {'Color (RGB)':<20} {'Hex':<8}")
    print("-" * 80)

    for score in test_scores:
        leds = service.score_to_led_count(score)
        color = service.score_to_color(score)

        if service.fill_direction == "high_to_low":
            if leds == 0:
                active_range = "off"
            elif leds >= service.led_count:
                active_range = f"all ({service.start_led}-{service.stop_led-1})"
            else:
                start = service.stop_led - leds
                active_range = f"LED {start}-{service.stop_led-1}"
        else:
            if leds == 0:
                active_range = "off"
            elif leds >= service.led_count:
                active_range = f"all ({service.start_led}-{service.stop_led-1})"
            else:
                stop = service.start_led + leds
                active_range = f"LED {service.start_led}-{stop-1}"

        color_str = f"RGB{color}"
        print(f"{score:<8.2f} {leds:<12d} {active_range:<20} {color_str:<20} {color_to_hex(color):<8}")

    print("\n" + "=" * 80)
    print("Analysis:")
    print("-" * 80)

    # Check for distinct colors
    unique_colors = set()
    for i in range(21):
        score = i * 0.05
        color = service.score_to_color(score)
        unique_colors.add(color)

    print(f"Unique colors across 21 score steps: {len(unique_colors)}")
    print(f"Expected: 21 (ideally all unique)")

    # Check for LED granularity
    unique_leds = set()
    for i in range(101):  # 0.0 to 1.0 in 0.01 steps
        score = i * 0.01
        leds = service.score_to_led_count(score)
        unique_leds.add(leds)

    print(f"Unique LED counts across 101 score steps (0.01 granularity): {len(unique_leds)}")
    print(f"Expected: at least 15 (ideally all 0-15)")

    print("\n" + "=" * 80)
    print("Payload examples with corrected inactive segment handling:")
    print("-" * 80)

    for score in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
        payload = service.build_payload(score, False)
        leds = service.score_to_led_count(score)
        segs = payload.get("seg", [])
        print(f"\nScore {score:.1f} → {leds} LEDs:")
        print(f"  Brightness: {payload['bri']}")
        for i, seg in enumerate(segs):
            seg_id = seg.get("id")
            start = seg.get("start")
            stop = seg.get("stop")
            col = seg.get("col", [None])[0]
            col_desc = f"RGB{tuple(col)}" if col else "off"
            if col == [0, 0, 0]:
                col_desc = "BLACK (off)"
            elif col and col != [0, 0, 0]:
                col_desc = color_to_hex(tuple(col))
            print(f"    Seg[{i}] id={seg_id}: LEDs {start}-{stop-1} = {col_desc}")


if __name__ == "__main__":
    test_full_range()
