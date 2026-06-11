# Changes according to new Hardware and Software Status:
The current WLED powered by the esp32 controller is divided into 2 segments:

```text
Segment 0: Score-Segment
Start LED: 0
Stop LED: 15
→ currently 15 LEDs, LED 0-14

Segment 1: static Segment
Start LED: 15
Stop LED: 18
→ 3 LEDs, LED 15–17
```


### score related changes
```text
score = 0.0 / no card
→ Score-Segment off

score = 0.1
→ ca. 1–2 LEDs active, starting at LED 14, red

score = 0.5
→ ca. 7–8 LEDs active, starting from LED 14 towards LED 0, blue

score = 1.0
→ LEDs 14 till 0 active, cyan-green
```

### proposed yaml structure if we keep adjusting the controller just by the LED count
```yaml
wled:
  enabled: true
  host: "http://4.3.2.1"
  endpoint: "/json/state"
  led_count: 15
  brightness: 160
  timeout_ms: 300
  update_hz: 20
  force_refresh_s: 2.0
  min_leds_when_visible: 1
  fail_mode: "optional"

  segment_id: 0
  start_led: 0
  stop_led: 15
  fill_direction: "high_to_low"
  preserve_segments: [1]

  idle:
    brightness: 80
    mode: "score_segment_off"

  colors:
    low_rgb: [255, 20, 20]
    mid_rgb: [0, 80, 255]
    high_rgb: [0, 255, 170]
```
