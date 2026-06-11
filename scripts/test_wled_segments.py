#!/usr/bin/env python3
"""Test WLED segment payload generation for high_to_low fill direction.

Validates that the payload correctly maps scores to LED ranges
with high_to_low fill (filling from LED 14 downward to LED 0).

Examples:
    python scripts/test_wled_segments.py
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


def test_segment_payloads():
    config = load_config("config/config.yaml")
    config.setdefault("wled", {})
    config["wled"]["enabled"] = True
    config["wled"]["host"] = "http://test"
    config["wled"]["led_count"] = 15
    config["wled"]["segment_id"] = 0
    config["wled"]["start_led"] = 0
    config["wled"]["stop_led"] = 15
    config["wled"]["fill_direction"] = "high_to_low"

    service = WledOutputService(_Ctx(config))

    test_cases = [
        ("idle", None, True),
        ("score 0.0", 0.0, False),
        ("score 0.1", 0.1, False),
        ("score 0.5", 0.5, False),
        ("score 1.0", 1.0, False),
    ]

    print("=" * 70)
    print("WLED Segment Payload Tests (high_to_low fill)")
    print("=" * 70)

    for label, score, idle in test_cases:
        payload = service.build_payload(score, idle)
        print(f"\n{label}:")
        if idle or score is None:
            print(f"  → Idle/Off")
        else:
            active = service.score_to_led_count(score)
            color = service.score_to_color(score)
            print(f"  → active_leds={active}, color={color}")

        print(f"  Payload segments:")
        for seg in payload.get("seg", []):
            seg_id = seg.get("id")
            start = seg.get("start")
            stop = seg.get("stop")
            col = seg.get("col")
            print(f"    - id={seg_id}: LEDs {start}-{stop}, color={col}")

        # Validate segment ranges
        segs = payload.get("seg", [])
        for i, seg in enumerate(segs):
            start = seg.get("start")
            stop = seg.get("stop")
            if start >= stop:
                print(f"    ⚠️  ERROR: segment {i} has invalid range [{start}, {stop})")

    print("\n" + "=" * 70)
    print("Expected behavior for high_to_low fill:")
    print("  - score 0.1: ~1-2 LEDs from top (14-13 or 14)")
    print("  - score 0.5: ~7-8 LEDs from top (14-7 or 14-8)")
    print("  - score 1.0: all 15 LEDs (14-0)")
    print("=" * 70)


if __name__ == "__main__":
    test_segment_payloads()
