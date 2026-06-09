# Configuration — `config/`

*Applies to YAML config under `config/`. Loaded automatically here.*

Configuration is explicit and validated at BOOT. Preserve existing config keys
when refactoring; rename only with a documented reason.

## Top-Level Config Sections

```yaml
app:         # name, version, initial_state
server:      # host, port, UI static dir, live stream settings
boot:        # next_state, max_boot_duration_s, allow_degraded_wled
workspace:   # ROI rect, perspective correction, output_size_px
detector:    # type (classical|yolo), loop_hz, thresholds, yolo model path
tracking:    # hand tracking params, card tracking params, fusion, smoothing
questionnaire: # Q&A definitions (list of question/answer entries)
identity:    # hashing algorithm, match threshold, dedup window
snapshot:    # output directory, filename pattern
persistence: # db_path (SQLite)
ocr:         # backend (paddleocr), language
vector:      # qdrant_path, text model, image model, collection name
logging:     # level, format, file path
camera:      # device index/path, resolution, fps, exposure settings
wled:        # enabled, host, port, segment mapping
```

## Detector Config

```yaml
detector:
  type: "classical"   # or "yolo"
  loop_hz: 20
  classical:
    threshold_mode: "adaptive"
    # ... contour filter params
  yolo:
    model_path: "models/yolov8n.pt"
    confidence: 0.5
```

## WLED (optional)

```yaml
wled:
  enabled: false
```

WLED must never become a critical dependency. If enabled and unreachable: log
warning, set health to `DEGRADED`, keep running.

## General Rules

- prefer explicit configuration over hard-coded values
- keep keys stable; don't rename without reason
- validate config at BOOT and fail clearly on missing/invalid keys
- do not hard-code Jetson-specific paths unless they are documented defaults
- `config.yaml.example` mirrors `config.yaml` structure with safe defaults
