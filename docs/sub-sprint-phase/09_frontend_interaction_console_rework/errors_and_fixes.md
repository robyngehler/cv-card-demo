# Errors and Fixes - Phase 09

## 2026-06-09 - Bounding box rendered at wrong card position

- Context: Tracking debug overlay in RUN view.
- Observed: Card box/center appeared offset from actual card.
- Expected: Overlay geometry should align with live frame coordinates.
- Suspected cause: Card coordinates were transformed as if workspace-local while detector already produced live-frame coordinates.
- Fix applied: In tracking debug rendering, draw card points directly in live-frame space; keep workspace conversion only for hand landmarks/proxy.
- Verification: Static code check and error scan passed.
- Status: DONE

## 2026-06-09 - Score/phase/source confidence appeared stale or missing

- Context: RUN UI panel and pills.
- Observed: Score and metadata intermittently not updating.
- Expected: Continuous updates while tracking is active.
- Suspected cause: Frontend relied mainly on SSE snapshots, and questionnaire score fields could lag/null in transient frames.
- Fix applied: Added tracking score/rating to snapshot payload; run view now falls back to tracking values; added 1s snapshot polling fallback independent of SSE.
- Verification: Static code check and error scan passed.
- Status: DONE

## 2026-06-09 - Configure mode live feed blank intermittently

- Context: CONFIGURE_CAMERA view.
- Observed: Image area showed fallback text despite successful frame endpoint calls.
- Expected: Stable live image in configure view.
- Suspected cause: Fast blob URL churn/revoke could invalidate image source during rapid polling.
- Fix applied: Switched live-view refresh to direct no-cache image URL updates.
- Verification: Static code check and error scan passed.
- Status: DONE

## 2026-06-09 - Insufficient connection/diagnostics visual state cues

- Context: Header status pill and diagnostics toggle.
- Observed: Limited distinction between connected/disconnected/API down states.
- Expected: Immediate visual distinction of OK/WARN/ERROR.
- Suspected cause: Missing state-specific classes/styles.
- Fix applied: Added class-driven state colors and active diagnostics button styling.
- Verification: Static code check and error scan passed.
- Status: DONE

## 2026-06-09 - Need lower CPU profile for live processing

- Context: Runtime processing pipeline.
- Observed: Request to reduce live-processing load while keeping candidate/snapshot flow intact.
- Expected: Process tracking on 1080x720 profile.
- Suspected cause: Live processing still configured for 1920x1080.
- Fix applied: Set camera live_processing to 1080x720 and scaled workspace rectangles/output sizes to match.
- Verification: Config lint/error scan passed.
- Status: DONE

## 2026-05-09 - UI status pill was ambiguous and mixed connection states

- Context: Header connection indicator.
- Observed: `CONNECTED / API DOWN` did not make the active state obvious.
- Expected: One clear status with color feedback.
- Suspected cause: Frontend concatenated SSE state and backend reachability into one label.
- Fix applied: Replaced the combined label with a single derived status (`LIVE`, `RECONNECTING`, `API DOWN`).
- Verification: Browser page load showed the pill in `LIVE` while backend and score stream were up.
- Status: DONE

## 2026-05-09 - RUN view did not subscribe to live score events

- Context: Questionnaire state, score, and phase updates in the RUN panel.
- Observed: Backend score updates were logged, but the browser did not show the live event stream reliably.
- Expected: Score/rating/question/session fields should update as live events arrive.
- Suspected cause: Frontend only listened to the SSE snapshot stream and ignored `/ws/score`.
- Fix applied: Added a score WebSocket client and used its payload as the live source for RUN panel fields.
- Verification: Browser snapshot showed updated RUN panel text and live connection state after backend start.
- Status: DONE

## 2026-05-09 - CONFIGURE live preview sometimes stayed blank

- Context: Camera settings tab preview.
- Observed: The live image area could remain empty even while the backend had an active camera.
- Expected: Configure mode should show the most recent camera frame.
- Suspected cause: Direct camera reads could stall, and the preview path had no cached-frame fallback.
- Fix applied: Added a fallback to the latest cached full frame and preserved the last full camera frame from successful reads.
- Verification: `/api/live-frame?mode=configure` returned HTTP 200 and the browser displayed the configure preview.
- Status: DONE

## 2026-05-09 - Full-frame snapshot writes were too heavy

- Context: Snapshot and precheck flow.
- Observed: Saving 4K frames and extra debug overlays added unnecessary IO and CPU load.
- Expected: Keep visual debug available in the UI, but avoid heavyweight snapshot writes.
- Suspected cause: Snapshot service always wrote the full frame and a separate workspace overlay image.
- Fix applied: Downscaled saved snapshot frames to a configurable max edge and removed the extra overlay write.
- Verification: Backend compiled cleanly and kept serving live streams during runtime validation.
- Status: DONE

## 2026-05-09 - Detector appeared to run YOLO but actually used classical fallback

- Context: Runtime detector selection with `detector.type: yolo`.
- Observed: False positives remained similar to classical mode; backend usage was unclear.
- Expected: Clear visibility of requested detector, active detector, and fallback reason.
- Suspected cause: YOLO `model_path` empty (`NOT_CONFIGURED`) and silent fallback to classical detector.
- Fix applied: Added explicit requested/active detector metadata and fallback reason to detector result/status; emit one warning log when fallback is active.
- Verification: Static error scan passed; diagnostics payload now includes fallback metadata.
- Status: DONE

## 2026-05-09 - Empty-scene false positives produced card-like confidence

- Context: Classical contour detector in no-card/no-hand scene.
- Observed: Stable false positives reached candidate/tracking with score comparable to real cards.
- Expected: Empty scene should remain `NO_TARGET`.
- Suspected cause: Area score rewarded larger contours (monotonic), weak geometric gating, and border-touching shapes not rejected.
- Fix applied: Reworked confidence area term to similarity around expected area, added quadrilateral/convex checks, rectangularity/solidity minimums, border-margin rejection, stricter tuned defaults, and richer rejection debug counters.
- Verification: Static error scan passed.
- Status: DONE

## 2026-05-09 - Camera sliders snapped back after Apply for exposure/white balance/focus

- Context: Configure camera UI and backend camera control apply flow.
- Observed: Some controls reverted immediately after apply and did not persist.
- Expected: Applied values should persist or report explicit readback mismatch.
- Suspected cause: Missing auto-mode toggles in configure view, backend-specific auto-exposure encoding mismatch on V4L2, and no readback validation.
- Fix applied: Added auto toggles + zoom to configure UI, implemented backend-aware auto exposure values (`0.75/0.25` for V4L2), auto-disable before manual property write, and readback mismatch rejection.
- Verification: Static error scan passed.
- Status: DONE
