#!/usr/bin/env python3
"""Send a fixed score (or idle) to the configured WLED device.

Lets you verify ESP32/WLED hardware before enabling WLED in the app. It reuses
the real score->LED-count->color->payload mapping from WledOutputService and
posts synchronously (bypassing the rate-limited worker), so it works even while
``wled.enabled`` is still false.

Examples:
    python scripts/test_wled_score.py --score 0.1
    python scripts/test_wled_score.py --score 0.5
    python scripts/test_wled_score.py --score 1.0
    python scripts/test_wled_score.py --idle
    python scripts/test_wled_score.py --host http://4.3.2.1 --score 0.7
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config_loader import load_config
from app.services.wled_output_service import WledOutputService


class _Ctx:
    def __init__(self, config):
        self.config = config
        self.logger = None


def main() -> int:
    parser = argparse.ArgumentParser(description="WLED fixed-score test")
    default_config = os.environ.get("CV_CARD_DEMO_CONFIG", "config/config.yaml")
    parser.add_argument("--config", default=default_config)
    parser.add_argument("--score", type=float, default=None, help="0.0 .. 1.0")
    parser.add_argument("--idle", action="store_true", help="send idle/off payload")
    parser.add_argument("--host", default=None, help="override wled.host (e.g. http://4.3.2.1)")
    parser.add_argument("--retries", type=int, default=2, help="retry attempts on timeout")
    args = parser.parse_args()

    if args.score is None and not args.idle:
        parser.error("provide --score <0..1> or --idle")

    config = load_config(args.config)
    config.setdefault("wled", {})
    if args.host:
        config["wled"]["host"] = args.host

    service = WledOutputService(_Ctx(config))
    service.stop()  # halt the worker if it started; we post synchronously below.

    if not service.client.configured:
        print("ERROR: no wled.host configured. Pass --host or set wled.host in config.")
        return 2

    idle = args.idle or args.score is None
    score = None if idle else args.score
    payload = service.build_payload(score, idle)

    if idle:
        print(f"Sending IDLE (off) to {service.client.host}")
    else:
        active = service.score_to_led_count(score)
        color = service.score_to_color(score)
        print(f"Sending score={score} -> active_leds={active} color={color} to {service.client.host}")

    ok = False
    for attempt in range(args.retries):
        ok = service.client.post_state(payload)
        if ok:
            print("OK: WLED accepted the update")
            return 0
        if attempt < args.retries - 1:
            import time
            print(f"Retry {attempt + 1}/{args.retries - 1} (timeout: {service.client.last_error})")
            time.sleep(0.5)

    print(f"FAILED after {args.retries} attempts: {service.client.last_error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
