# Shell Scripts — `scripts/`

*Applies to `scripts/`. Loaded automatically here.*

## Shell Scripts

```text
run_backend.sh      — resolve repo root from script path, activate venv, export
                      CUDA LD_LIBRARY_PATH, exec python -m app.main
run_kiosk.sh        — launch browser in kiosk/fullscreen at localhost:8000
install_services.sh — render systemd unit templates for this checkout
                      (path/user/display auto-detected), install + enable
preflight.sh        — sanity checks before deployment (venv, config, CUDA, camera)
```

All scripts are location-independent: they derive the repo root from their own
path (`$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)`), so no script hard-codes
`/opt/cv-card-demo`. Env overrides: `CV_CARD_DEMO_CONFIG`, `CV_CARD_DEMO_VENV`,
`CV_CARD_DEMO_URL`; for install: `CVD_USER`, `CVD_GROUP`, `CVD_DISPLAY`,
`CVD_XAUTHORITY`.

Every shell script starts with:

```bash
set -euo pipefail
```

Use `exec` for the final long-running process so systemd supervises the correct PID.

## Debug / Test Python Scripts

Not part of the deployed application. Run manually on the Jetson for diagnostics.

```text
debug_camera_info.py             — print camera capabilities and format info
debug_detector_detailed.py       — run detector on live feed, show overlay + logs
debug_preprocessing_pipeline.py  — visualize each preprocessing step
analyze_detector_rejection.py    — analyse why detections were rejected
analyze_hand_interference.py     — measure hand occlusion false-positive rate
compare_threshold_modes.py       — side-by-side adaptive vs fixed threshold
test_detector_batch.py           — batch test detector on saved images
test_detector_cv.py              — unit-style test for classical detector logic
test_hand_occlusion_synthetic.py — synthetic hand occlusion test cases
test_tracking_continuity.py      — verify tracker continuity across lost frames
```

## Avoid

- complex boot scripts that launch many background processes
- unmanaged daemons or hidden `nohup` processes
- manual startup steps required for normal operation

## Principle

Scripts should be boring, reproducible, and easy to read. Prefer a few clear
scripts over one large clever one. See `systemd/CLAUDE.md` for supervision.
