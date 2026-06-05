# CV-Card-Demo – BOOT-Step Spezifikation

**Projekt:** CV-Card-Demo  
**Zielplattform:** NVIDIA Jetson Orin NX  
**OS / Stack:** Ubuntu 22.04.5 LTS, JetPack 6.1, Jetson Linux R36.4.x  
**Dokumentstatus:** Draft für MVP-Boot-Architektur  
**Fokus:** Stabiler Start von UI, Backend, State Machine und OpenCV/CV-Pipeline  
**WLED:** Vorerst optional, später ergänzbar  

---

## 1. Ziel des BOOT-Steps

Der BOOT-Step beschreibt den kontrollierten Start der Demo-Anwendung nach dem Einschalten des Systems.

Ziel ist:

1. Das System startet automatisch nach Power-On.
2. Die Backend-Anwendung wird zuverlässig gestartet.
3. Die Web-UI wird bereitgestellt und im Kiosk-Modus angezeigt.
4. Die State Machine startet sauber im Zustand `BOOT`.
5. Die Anwendung wechselt nach erfolgreichem Basisstart in den Zustand `INIT_CAM`.
6. Die Kamera-/OpenCV-Anbindung wird anschließend in `INIT_CAM` initialisiert.
7. Fehler werden erkannt, geloggt und führen nicht zu einem unkontrollierten Absturz.
8. WLED/ESP32 ist im MVP nicht kritisch und wird vorerst nur als optionaler Pfad vorgesehen.

Der BOOT-Step soll bewusst einfach, robust und gut debugbar bleiben.

---

## 2. Abgrenzung: Linux-Boot vs. Application-BOOT

Es gibt zwei verschiedene Boot-Ebenen:

```text
Power On
  ↓
Linux / systemd Boot
  ↓
Start der CV-Card-Demo-Dienste
  ↓
Application BOOT-State
  ↓
INIT_CAM
```

### 2.1 Linux / systemd Boot

Diese Ebene liegt außerhalb der Python-Anwendung.

Aufgaben:

- Betriebssystem startet.
- Netzwerk, grafische Session und Benutzerumgebung werden initialisiert.
- systemd startet die benötigten Dienste.
- Backend-Service wird gestartet.
- Kiosk-Service wird gestartet.
- Dienste werden bei Crash automatisch neu gestartet.

### 2.2 Application BOOT-State

Diese Ebene liegt innerhalb der Python-Anwendung.

Aufgaben:

- Konfiguration laden und validieren.
- Logging initialisieren.
- App-Kontext erzeugen.
- Webserver / UI-Service bereitstellen.
- State Machine erzeugen.
- Health-Status initialisieren.
- WLED-Pfad optional vorbereiten, aber nicht blockierend behandeln.
- Übergang zu `INIT_CAM` auslösen.

---

## 3. MVP-Prioritäten

Für den ersten stabilen MVP gilt folgende Priorität:

| Priorität | Komponente | Muss im BOOT funktionieren? | Bemerkung |
|---:|---|---|---|
| 1 | Backend / Main-App | Ja | Kritisch |
| 2 | State Machine | Ja | Kritisch |
| 3 | Config + Logging | Ja | Kritisch |
| 4 | UI-Server | Ja | Kritisch |
| 5 | Browser / Kiosk | Ja, aber getrennt vom Backend | Sollte automatisch neu starten |
| 6 | Kamera / OpenCV | Wird in `INIT_CAM` initialisiert | Noch nicht in `BOOT` öffnen |
| 7 | WLED / ESP32 | Nein | Optionaler Erweiterungspfad |

Wichtig:

> WLED darf den BOOT im MVP nicht blockieren.

Das System soll auch ohne LED-Streifen vollständig mit UI und CV-Pipeline laufen.

---

## 4. Grobe Startsequenz

```text
Power On
  ↓
Jetson bootet Ubuntu
  ↓
systemd startet cv-card-demo-backend.service
  ↓
Backend startet Python main.py
  ↓
FastAPI / UI-Server wird bereitgestellt
  ↓
State Machine startet mit Zustand BOOT
  ↓
BOOT prüft Config, Logging, UI-Service, Context
  ↓
systemd startet cv-card-demo-kiosk.service
  ↓
Browser öffnet lokale UI im Vollbild
  ↓
BOOT setzt Systemstatus auf READY_FOR_INIT_CAM
  ↓
Transition zu INIT_CAM
  ↓
INIT_CAM öffnet Kamera und prüft cv2-Verbindung
```

---

## 5. Empfohlene Prozessarchitektur

Für den MVP werden zwei systemd-Dienste und ein systemd-Target empfohlen:

```text
systemd
├── cv-card-demo.target
├── cv-card-demo-backend.service
└── cv-card-demo-kiosk.service
```

### 5.1 Backend-Service

Der Backend-Service startet:

- Python-App
- State Machine
- FastAPI-Webserver
- WebSocket-Endpunkte
- Health-Endpunkte
- später CV-Pipeline
- später optional WLED-Client

### 5.2 Kiosk-Service

Der Kiosk-Service startet:

- lokalen Browser
- Vollbildmodus
- Anzeige der lokalen UI unter `http://localhost:8000`

Backend und Browser werden bewusst getrennt.

Vorteile:

- Wenn der Browser abstürzt, läuft das Backend weiter.
- Wenn das Backend neu startet, kann der Browser automatisch reconnecten.
- Debugging ist einfacher.
- systemd kann beide Komponenten getrennt überwachen.

---

## 6. Verzeichnisstruktur

Empfohlene Zielstruktur auf dem Jetson:

```text
/opt/cv-card-demo
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config_loader.py
│   ├── app_context.py
│   ├── state_machine.py
│   │
│   ├── states/
│   │   ├── __init__.py
│   │   ├── boot.py
│   │   ├── init_cam.py
│   │   ├── error_safe.py
│   │   └── recovery.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ui_service.py
│   │   ├── health_service.py
│   │   ├── camera_service.py
│   │   └── wled_client.py        # optional, später
│   │
│   ├── web/
│   │   ├── index.html
│   │   ├── app.js
│   │   └── styles.css
│   │
│   └── cv/
│       ├── __init__.py
│       # optional future camera abstraction package
│
├── config/
│   └── config.yaml
│
├── scripts/
│   ├── run_backend.sh
│   ├── run_kiosk.sh
│   ├── preflight.sh
│   └── install_services.sh
│
├── systemd/
│   ├── cv-card-demo.target
│   ├── cv-card-demo-backend.service
│   └── cv-card-demo-kiosk.service
│
├── logs/
│   └── app.log
│
└── venv/
```

---

## 7. systemd-Komponenten

### 7.1 Target: `cv-card-demo.target`

Pfad:

```text
/etc/systemd/system/cv-card-demo.target
```

Inhalt:

```ini
[Unit]
Description=CV Card Demo Application Stack
Wants=cv-card-demo-backend.service cv-card-demo-kiosk.service
After=network-online.target graphical.target

[Install]
WantedBy=multi-user.target
```

Aufgabe:

- Bündelt Backend und Kiosk.
- Erlaubt Start/Stop der gesamten Anwendung mit einem Kommando.

Beispiele:

```bash
sudo systemctl start cv-card-demo.target
sudo systemctl stop cv-card-demo.target
sudo systemctl restart cv-card-demo.target
```

---

### 7.2 Backend-Service: `cv-card-demo-backend.service`

Pfad:

```text
/etc/systemd/system/cv-card-demo-backend.service
```

Inhalt:

```ini
[Unit]
Description=CV Card Demo Backend and State Machine
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
Type=simple
User=demo
Group=demo
WorkingDirectory=/opt/cv-card-demo

Environment=PYTHONUNBUFFERED=1
Environment=CV_CARD_DEMO_CONFIG=/opt/cv-card-demo/config/config.yaml

ExecStart=/opt/cv-card-demo/scripts/run_backend.sh

Restart=always
RestartSec=2

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Bemerkungen

- `Restart=always` sorgt dafür, dass die App nach einem Crash neu gestartet wird.
- `RestartSec=2` verhindert hektische Neustart-Schleifen.
- `StartLimitBurst=10` begrenzt Crash-Loops.
- Logs landen zusätzlich im systemd-Journal.
- Ein eigener User `demo` ist empfohlen.

---

### 7.3 Kiosk-Service: `cv-card-demo-kiosk.service`

Pfad:

```text
/etc/systemd/system/cv-card-demo-kiosk.service
```

Inhalt:

```ini
[Unit]
Description=CV Card Demo Local Kiosk Browser
After=graphical.target cv-card-demo-backend.service
Wants=cv-card-demo-backend.service

[Service]
Type=simple
User=demo
Group=demo

Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/demo/.Xauthority

ExecStart=/opt/cv-card-demo/scripts/run_kiosk.sh

Restart=always
RestartSec=3

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
```

#### Bemerkungen

- Der Kiosk-Service hängt vom grafischen System ab.
- Der Browser wird getrennt vom Backend gestartet.
- Wenn der Browser abstürzt, wird er automatisch neu gestartet.
- Wenn die UI noch nicht erreichbar ist, soll der Browser trotzdem starten können und später reconnecten.

---

## 8. Start-Skripte

### 8.1 `run_backend.sh`

Pfad:

```text
/opt/cv-card-demo/scripts/run_backend.sh
```

Inhalt:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /opt/cv-card-demo

if [ ! -d "/opt/cv-card-demo/venv" ]; then
  echo "ERROR: Python virtual environment not found at /opt/cv-card-demo/venv"
  exit 1
fi

source /opt/cv-card-demo/venv/bin/activate

CONFIG_PATH="${CV_CARD_DEMO_CONFIG:-/opt/cv-card-demo/config/config.yaml}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: Config file not found: $CONFIG_PATH"
  exit 1
fi

exec python -m app.main \
  --config "$CONFIG_PATH" \
  --initial-state BOOT
```

#### Aufgaben

- Arbeitsverzeichnis setzen.
- Python-Virtualenv aktivieren.
- Config-Datei prüfen.
- Python-App starten.
- `exec` verwenden, damit systemd den eigentlichen Python-Prozess überwacht.

---

### 8.2 `run_kiosk.sh`

Pfad:

```text
/opt/cv-card-demo/scripts/run_kiosk.sh
```

Inhalt:

```bash
#!/usr/bin/env bash
set -euo pipefail

URL="http://localhost:8000"

# Kurz prüfen, ob Backend erreichbar ist.
# Nicht unendlich blockieren: Die UI darf selbst reconnecten.
for i in {1..20}; do
  if curl -fsS "$URL/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if command -v chromium-browser >/dev/null 2>&1; then
  BROWSER="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
  BROWSER="chromium"
elif command -v google-chrome >/dev/null 2>&1; then
  BROWSER="google-chrome"
else
  echo "ERROR: No supported browser found."
  exit 1
fi

exec "$BROWSER" \
  --kiosk "$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000
```

#### Aufgaben

- lokale UI öffnen
- Browser im Kiosk-Modus starten
- kurze Backend-Erreichbarkeit prüfen
- nicht dauerhaft blockieren
- Browserprozess durch systemd überwachen lassen

---

### 8.3 `preflight.sh`

Pfad:

```text
/opt/cv-card-demo/scripts/preflight.sh
```

Inhalt:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== CV Card Demo Preflight ==="

APP_DIR="/opt/cv-card-demo"
CONFIG_FILE="$APP_DIR/config/config.yaml"
VENV_DIR="$APP_DIR/venv"

echo "[1/8] Checking app directory..."
test -d "$APP_DIR" && echo "OK: $APP_DIR"

echo "[2/8] Checking config..."
test -f "$CONFIG_FILE" && echo "OK: $CONFIG_FILE"

echo "[3/8] Checking Python venv..."
test -d "$VENV_DIR" && echo "OK: $VENV_DIR"

echo "[4/8] Checking Python executable..."
test -x "$VENV_DIR/bin/python" && "$VENV_DIR/bin/python" --version

echo "[5/8] Checking OpenCV import..."
"$VENV_DIR/bin/python" - <<'PY'
import cv2
print("OK: cv2 version:", cv2.__version__)
PY

echo "[6/8] Checking port 8000..."
if ss -ltn | grep -q ':8000 '; then
  echo "WARN: Port 8000 already in use"
else
  echo "OK: Port 8000 free"
fi

echo "[7/8] Checking video devices..."
if ls /dev/video* >/dev/null 2>&1; then
  ls -l /dev/video*
else
  echo "WARN: No /dev/video* device found"
fi

echo "[8/8] Checking display..."
if [ -n "${DISPLAY:-}" ]; then
  echo "OK: DISPLAY=$DISPLAY"
else
  echo "WARN: DISPLAY is not set"
fi

echo "=== Preflight complete ==="
```

#### Aufgaben

- Installationszustand prüfen.
- OpenCV-Import testen.
- Kamera-Devices anzeigen.
- Port-Konflikte erkennen.
- Browser-/Display-Probleme früh sichtbar machen.

---

## 9. Application BOOT-State

Der BOOT-State ist der erste Zustand der internen State Machine.

### 9.1 Ziel

Der BOOT-State soll sicherstellen, dass die Basisdienste der Anwendung verfügbar sind.

Er prüft:

- Config geladen?
- Config semantisch gültig?
- Logging aktiv?
- App-Kontext erzeugt?
- UI-Service bereit?
- Health-Service bereit?
- State Machine vollständig?
- WLED optional deaktiviert oder nur vorbereitet?

Er öffnet noch nicht die Kamera.  
Die Kamera wird erst im nächsten State `INIT_CAM` initialisiert.

---

### 9.2 BOOT-State Eingangsbedingungen

Der BOOT-State wird betreten, wenn:

```text
main.py wurde erfolgreich gestartet
Config-Pfad wurde übergeben
initial_state == BOOT
```

---

### 9.3 BOOT-State Ausgangsbedingungen

Der BOOT-State darf nach `INIT_CAM` wechseln, wenn:

```text
Config OK
Logging OK
AppContext OK
UI-Service OK
Health-Service OK
State Machine OK
```

WLED ist keine Voraussetzung.

---

### 9.4 BOOT-State Fehlerbedingungen

Der BOOT-State wechselt nach `ERROR_SAFE`, wenn:

```text
Config fehlt
Config ungültig
Logging kann nicht initialisiert werden
UI-Service kann nicht starten
Port für Webserver nicht verfügbar
State Machine kann nicht erzeugt werden
kritischer Python-Import fehlt
```

---

## 10. BOOT-State interne Substates

Der BOOT-State kann intern in Substates gegliedert werden:

```text
BOOT_ENTER
  ↓
BOOT_LOAD_CONFIG
  ↓
BOOT_VALIDATE_CONFIG
  ↓
BOOT_INIT_LOGGING
  ↓
BOOT_CREATE_CONTEXT
  ↓
BOOT_START_UI_SERVICE
  ↓
BOOT_INIT_HEALTH_SERVICE
  ↓
BOOT_OPTIONAL_WLED_PREPARE
  ↓
BOOT_READY
  ↓
INIT_CAM
```

Diese Substates müssen nicht als globale State-Machine-Zustände modelliert werden.  
Sie sollten aber im Health-Status und im Log sichtbar sein.

---

## 11. BOOT-State Ablauf im Detail

### 11.1 `BOOT_ENTER`

Aufgaben:

- State setzen: `BOOT`
- Zeitstempel speichern
- Boot-Versuch zählen
- UI-Status vorbereiten

Log-Beispiel:

```text
[BOOT] Entering BOOT state
```

Health-Beispiel:

```json
{
  "state": "BOOT",
  "substate": "BOOT_ENTER",
  "message": "Application boot started"
}
```

---

### 11.2 `BOOT_LOAD_CONFIG`

Aufgaben:

- Config-Datei laden.
- Pflichtfelder prüfen.
- Defaultwerte ergänzen.

Pflichtbereiche im MVP:

```yaml
app:
server:
boot:
camera:
logging:
```

WLED darf optional fehlen oder deaktiviert sein.

---

### 11.3 `BOOT_VALIDATE_CONFIG`

Aufgaben:

- Portnummer prüfen.
- Kamera-Konfiguration formal prüfen.
- Pfade prüfen.
- Arbeitsverzeichnisse prüfen.
- Boolean-Flags prüfen.
- Boot-Policy prüfen.

Minimal validierbare Felder:

```yaml
app:
  name: "cv-card-demo"
  version: "0.1.0"
  initial_state: "BOOT"

server:
  host: "0.0.0.0"
  port: 8000
  ui_static_dir: "/opt/cv-card-demo/app/web"

boot:
  next_state: "INIT_CAM"
  allow_degraded_wled: true

camera:
  init_in_boot: false
  preferred_backend: "opencv"
  device_index: 0

logging:
  level: "INFO"
  file: "/opt/cv-card-demo/logs/app.log"
```

Wichtig:

```yaml
camera:
  init_in_boot: false
```

Die Kamera wird nicht im BOOT-State geöffnet.  
Der BOOT-State prüft nur, ob die spätere Kamera-Konfiguration vorhanden ist.

---

### 11.4 `BOOT_INIT_LOGGING`

Aufgaben:

- Console-Logging aktivieren.
- File-Logging aktivieren, falls möglich.
- Log-Level aus Config setzen.
- Boot-ID erzeugen.
- erste Statusmeldung schreiben.

Bei File-Logging-Fehler:

- Wenn Console-Logging funktioniert: weiterlaufen mit Warnung.
- Wenn gar kein Logging möglich: `ERROR_SAFE`.

---

### 11.5 `BOOT_CREATE_CONTEXT`

Der AppContext ist das zentrale Objekt, das Services und Runtime-Status enthält.

Beispielstruktur:

```text
AppContext
├── config
├── logger
├── runtime
│   ├── boot_id
│   ├── start_time
│   ├── current_state
│   └── degraded_flags
├── services
│   ├── ui_service
│   ├── health_service
│   ├── camera_service
│   └── wled_client_optional
└── state_data
    ├── last_error
    ├── last_score
    └── last_pose
```

Aufgaben:

- Runtime-Status erzeugen.
- Service-Instanzen erzeugen.
- Gemeinsames Statusmodell initialisieren.
- Queues / Event-Bus vorbereiten.

---

### 11.6 `BOOT_START_UI_SERVICE`

Der UI-Service ist im MVP kritisch.

Aufgaben:

- FastAPI-App erzeugen.
- statische UI-Dateien bereitstellen.
- Health-Endpunkt registrieren.
- WebSocket-Endpunkte registrieren.
- initialen UI-Status setzen.
- Webserver starten.

Empfohlene Endpunkte:

```text
GET  /
GET  /api/health
GET  /api/state
GET  /api/version
WS   /ws/status
WS   /ws/score
```

Der UI-Service stellt sowohl die HTML/JS/CSS-Dateien als auch die Live-Kommunikation bereit.

### UI-Status während BOOT

Die UI soll mindestens folgende Zustände anzeigen können:

```text
System startet...
Backend aktiv...
Kamera wird vorbereitet...
```

Da die Kamera erst in `INIT_CAM` geöffnet wird, lautet der finale BOOT-Status:

```text
Bereit für Kamerainitialisierung
```

---

### 11.7 `BOOT_INIT_HEALTH_SERVICE`

Der Health-Service liefert den aktuellen Systemzustand.

Minimaler Health-Status:

```json
{
  "app": "cv-card-demo",
  "version": "0.1.0",
  "state": "BOOT",
  "substate": "BOOT_START_UI_SERVICE",
  "uptime_s": 2.41,
  "services": {
    "ui": {
      "status": "OK"
    },
    "camera": {
      "status": "NOT_INITIALIZED"
    },
    "cv2": {
      "status": "NOT_CHECKED"
    },
    "wled": {
      "status": "OPTIONAL_DISABLED"
    }
  }
}
```

---

### 11.8 `BOOT_OPTIONAL_WLED_PREPARE`

WLED wird im MVP nicht aktiv benötigt.

Optionale Behandlung:

```text
if wled.enabled == false:
    wled_status = OPTIONAL_DISABLED
elif wled.enabled == true:
    create client object only
    do not block boot
    optional short probe may be executed later
```

Für den MVP empfohlen:

```yaml
wled:
  enabled: false
```

Die BOOT-Logik soll dann setzen:

```text
WLED status = OPTIONAL_DISABLED
```

Kein Netzwerkfehler, kein Timeout, kein Abbruch.

Später kann dieser Substate erweitert werden zu:

```text
BOOT_CHECK_WLED
  reachable → WLED_OK
  unreachable → WLED_DEGRADED
```

Aber im MVP bleibt WLED bewusst aus dem kritischen Pfad.

---

### 11.9 `BOOT_READY`

Der BOOT-State ist erfolgreich, wenn:

```text
Config OK
Logging OK
AppContext OK
UI-Service OK
Health-Service OK
StateMachine OK
```

Dann:

```text
Transition: BOOT → INIT_CAM
```

Vor der Transition wird der Status publiziert:

```json
{
  "type": "system_status",
  "state": "BOOT",
  "substate": "BOOT_READY",
  "message": "Boot complete. Transitioning to INIT_CAM."
}
```

---

## 12. Übergang zu INIT_CAM

Der Übergang geschieht automatisch.

```text
BOOT_READY
  ↓
INIT_CAM
```

`INIT_CAM` übernimmt danach:

- OpenCV-Import prüfen.
- Kamera-Backend auswählen.
- Kamera öffnen.
- erste Frames lesen.
- FPS prüfen.
- Auflösung prüfen.
- optional Kamera-Parameter setzen.
- bei Erfolg weiter zu `CALIBRATION` oder `IDLE_NO_CARD`.

BOOT selbst prüft nicht aktiv die Kamera-Verbindung.  
Es stellt nur sicher, dass `INIT_CAM` sauber gestartet werden kann.

---

## 13. CV2-/OpenCV-Verbindung: wo prüfen?

Für klare Verantwortlichkeiten:

| Prüfung | Ort |
|---|---|
| `import cv2` möglich? | optional in `preflight.sh`, final in `INIT_CAM` |
| Kamera-Device vorhanden? | optional in `preflight.sh`, final in `INIT_CAM` |
| Kamera öffnen möglich? | `INIT_CAM` |
| Frames lesbar? | `INIT_CAM` |
| FPS stabil? | `INIT_CAM` |
| Bildauflösung korrekt? | `INIT_CAM` |

Der BOOT-State prüft nur die Konfiguration und startet die UI.

Warum?

- BOOT bleibt schnell und robust.
- Kamera-Probleme werden eindeutig dem Zustand `INIT_CAM` zugeordnet.
- Fehlerbehandlung wird klarer.
- UI ist bereits sichtbar, wenn Kamera-Initialisierung fehlschlägt.

Das ist wichtig, weil ein Kamerafehler dann nicht als “schwarzer Bildschirm” endet, sondern als klare UI-Meldung.

---

## 14. Fehler- und Recovery-Strategie im BOOT

### 14.1 Kritische Fehler

Diese Fehler führen zu `ERROR_SAFE` oder Prozessabbruch mit systemd-Restart:

```text
Config-Datei fehlt
Config syntaktisch ungültig
Pflichtparameter fehlen
UI-Port blockiert
UI-Service kann nicht starten
AppContext kann nicht erzeugt werden
State Machine kann nicht initialisiert werden
```

### 14.2 Nicht-kritische Fehler

Diese Fehler blockieren den BOOT nicht:

```text
WLED deaktiviert
WLED nicht erreichbar
Browser noch nicht verbunden
Kamera noch nicht initialisiert
Kein Besucher / keine Karte
```

### 14.3 Browser-Fehler

Wenn der Browser nicht startet:

- Backend läuft weiter.
- Kiosk-Service wird durch systemd neu gestartet.
- Fehler wird im Journal geloggt.
- Backend darf nicht wegen Browser-Fehler beendet werden.

### 14.4 UI-Service-Fehler

Wenn der UI-Service nicht starten kann:

- BOOT schlägt fehl.
- Wechsel nach `ERROR_SAFE`, falls möglich.
- Wenn kein UI-Service möglich ist, Prozess mit Fehlercode beenden.
- systemd startet Backend neu.

---

## 15. Health-Statusmodell

### 15.1 Zustände

Empfohlene Service-Statuswerte:

```text
OK
WARN
ERROR
NOT_INITIALIZED
NOT_CHECKED
OPTIONAL_DISABLED
DEGRADED
```

### 15.2 `/api/health` im BOOT

Beispiel:

```json
{
  "app": "cv-card-demo",
  "version": "0.1.0",
  "boot_id": "2026-06-05T12:00:00Z",
  "state": "BOOT",
  "substate": "BOOT_READY",
  "uptime_s": 3.7,
  "services": {
    "ui": {
      "status": "OK",
      "host": "0.0.0.0",
      "port": 8000
    },
    "camera": {
      "status": "NOT_INITIALIZED",
      "next_state": "INIT_CAM"
    },
    "cv2": {
      "status": "NOT_CHECKED",
      "next_state": "INIT_CAM"
    },
    "wled": {
      "status": "OPTIONAL_DISABLED"
    }
  },
  "next_state": "INIT_CAM"
}
```

---

## 16. WebSocket-Statusmodell

Während BOOT sendet das Backend Statusmeldungen an die UI.

Beispiel:

```json
{
  "type": "system_status",
  "state": "BOOT",
  "substate": "BOOT_LOAD_CONFIG",
  "level": "info",
  "message": "Loading configuration"
}
```

Bei erfolgreichem BOOT:

```json
{
  "type": "system_status",
  "state": "BOOT",
  "substate": "BOOT_READY",
  "level": "info",
  "message": "Boot complete"
}
```

Bei Transition:

```json
{
  "type": "system_status",
  "state": "INIT_CAM",
  "substate": "INIT_CAM_ENTER",
  "level": "info",
  "message": "Initializing camera"
}
```

---

## 17. Konfigurationsdatei für MVP

Pfad:

```text
/opt/cv-card-demo/config/config.yaml
```

Beispiel:

```yaml
app:
  name: "cv-card-demo"
  version: "0.1.0"
  initial_state: "BOOT"

server:
  host: "0.0.0.0"
  port: 8000
  ui_static_dir: "/opt/cv-card-demo/app/web"

boot:
  next_state: "INIT_CAM"
  max_boot_duration_s: 10
  allow_degraded_wled: true

logging:
  level: "INFO"
  file: "/opt/cv-card-demo/logs/app.log"
  log_to_console: true
  log_to_file: true

camera:
  init_in_boot: false
  preferred_backend: "opencv"
  device_index: 0
  width: 1280
  height: 720
  fps: 30

wled:
  enabled: false
  host: ""
  timeout_ms: 300
  fail_mode: "optional"
```

---

## 18. Python-App: Semantischer Aufbau

### 18.1 `main.py`

```python
def main():
    args = parse_args()

    raw_config = load_config(args.config)
    logger = init_basic_logger(raw_config)

    ctx = create_app_context(
        config=raw_config,
        logger=logger,
    )

    state_machine = create_state_machine(ctx)
    ctx.state_machine = state_machine

    state_machine.start(initial_state=args.initial_state)
```

---

### 18.2 BootState

```python
class BootState:
    name = "BOOT"

    def enter(self, ctx):
        ctx.runtime.current_state = "BOOT"
        ctx.runtime.current_substate = "BOOT_ENTER"
        ctx.health.update_state("BOOT", "BOOT_ENTER")
        ctx.logger.info("[BOOT] Entering BOOT state")

    def run(self, ctx):
        self.load_and_validate_config(ctx)
        self.init_logging(ctx)
        self.create_runtime_context(ctx)
        self.start_ui_service(ctx)
        self.init_health_service(ctx)
        self.prepare_optional_wled(ctx)
        self.mark_boot_ready(ctx)

        return "INIT_CAM"

    def exit(self, ctx):
        ctx.logger.info("[BOOT] Leaving BOOT state -> INIT_CAM")
        ctx.ui.publish_status(
            state="INIT_CAM",
            substate="INIT_CAM_ENTER",
            message="Initializing camera"
        )
```

---

### 18.3 Service-Ergebnisobjekte

Jeder Service sollte beim Start ein Ergebnisobjekt liefern:

```python
@dataclass
class ServiceStatus:
    name: str
    status: str
    message: str = ""
    critical: bool = False
    error: str | None = None
```

Beispiel:

```python
ServiceStatus(
    name="ui",
    status="OK",
    message="UI service listening on port 8000",
    critical=True,
)
```

Für WLED im MVP:

```python
ServiceStatus(
    name="wled",
    status="OPTIONAL_DISABLED",
    message="WLED disabled in MVP config",
    critical=False,
)
```

---

## 19. UI-Anforderungen während BOOT

Die UI soll direkt anzeigen, dass das System lebt.

### 19.1 Minimalansicht

```text
CV Card Demo
System startet...
```

### 19.2 Nach BOOT

```text
Kamera wird initialisiert...
```

### 19.3 Bei Kamerafehler in INIT_CAM

```text
Kamera konnte nicht geöffnet werden.
Bitte Verbindung prüfen.
System versucht erneut zu verbinden...
```

Das ist ein wichtiger Punkt: Die UI muss vor der Kamera funktionieren.  
Sonst sieht man bei Kameraproblemen nur einen schwarzen Bildschirm. Das ist technisch gesehen minimalistisch, aber emotional eher ein Angriff.

---

## 20. Akzeptanzkriterien für den BOOT-Step

Der BOOT-Step gilt als erfolgreich, wenn:

1. Nach Systemstart wird der Backend-Service automatisch gestartet.
2. `/api/health` ist lokal erreichbar.
3. Die Browser-UI öffnet automatisch im Kiosk-Modus.
4. Die UI zeigt mindestens einen BOOT-Status.
5. Die State Machine startet mit `BOOT`.
6. Der BOOT-State wechselt automatisch zu `INIT_CAM`.
7. Kamera/OpenCV wird noch nicht im BOOT-State geöffnet.
8. WLED ist deaktiviert oder optional und blockiert den BOOT nicht.
9. Logs sind über `journalctl` einsehbar.
10. Bei Backend-Crash startet systemd den Dienst neu.

---

## 21. Testplan

### 21.1 Manuelle Tests

#### Backend direkt starten

```bash
cd /opt/cv-card-demo
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Erwartung:

```text
BOOT_ENTER
BOOT_LOAD_CONFIG
BOOT_START_UI_SERVICE
BOOT_READY
INIT_CAM_ENTER
```

---

#### Health prüfen

```bash
curl http://localhost:8000/api/health
```

Erwartung:

```json
{
  "state": "BOOT",
  "services": {
    "ui": {
      "status": "OK"
    }
  }
}
```

oder nach kurzer Zeit:

```json
{
  "state": "INIT_CAM"
}
```

---

#### systemd Backend testen

```bash
sudo systemctl start cv-card-demo-backend.service
systemctl status cv-card-demo-backend.service
journalctl -u cv-card-demo-backend.service -f
```

---

#### Kiosk testen

```bash
sudo systemctl start cv-card-demo-kiosk.service
systemctl status cv-card-demo-kiosk.service
journalctl -u cv-card-demo-kiosk.service -f
```

---

#### Gesamten Stack starten

```bash
sudo systemctl start cv-card-demo.target
```

---

### 21.2 Fehlerfall: Config fehlt

Test:

```bash
mv /opt/cv-card-demo/config/config.yaml /opt/cv-card-demo/config/config.yaml.bak
sudo systemctl restart cv-card-demo-backend.service
```

Erwartung:

- Backend startet nicht erfolgreich.
- systemd versucht Restart.
- Journal zeigt Config-Fehler.
- Kein stiller Fehler.

---

### 21.3 Fehlerfall: Port blockiert

Test:

```bash
python3 -m http.server 8000
```

Dann Backend starten.

Erwartung:

- UI-Service kann Port nicht binden.
- BOOT schlägt fehl.
- Fehler im Log.
- systemd Restart.

---

### 21.4 Fehlerfall: WLED deaktiviert

Config:

```yaml
wled:
  enabled: false
```

Erwartung:

- BOOT erfolgreich.
- Health zeigt `OPTIONAL_DISABLED`.
- Transition zu `INIT_CAM`.

---

## 22. Installationsskript: `install_services.sh`

Pfad:

```text
/opt/cv-card-demo/scripts/install_services.sh
```

Inhalt:

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/cv-card-demo"
SYSTEMD_DIR="/etc/systemd/system"

sudo cp "$APP_DIR/systemd/cv-card-demo.target" "$SYSTEMD_DIR/"
sudo cp "$APP_DIR/systemd/cv-card-demo-backend.service" "$SYSTEMD_DIR/"
sudo cp "$APP_DIR/systemd/cv-card-demo-kiosk.service" "$SYSTEMD_DIR/"

sudo systemctl daemon-reload

sudo systemctl enable cv-card-demo-backend.service
sudo systemctl enable cv-card-demo-kiosk.service
sudo systemctl enable cv-card-demo.target

echo "Services installed and enabled."
echo "Start with:"
echo "  sudo systemctl start cv-card-demo.target"
```

---

## 23. Bedienkommandos

### Start

```bash
sudo systemctl start cv-card-demo.target
```

### Stop

```bash
sudo systemctl stop cv-card-demo.target
```

### Restart

```bash
sudo systemctl restart cv-card-demo.target
```

### Backend-Logs

```bash
journalctl -u cv-card-demo-backend.service -f
```

### Kiosk-Logs

```bash
journalctl -u cv-card-demo-kiosk.service -f
```

### Status

```bash
systemctl status cv-card-demo-backend.service
systemctl status cv-card-demo-kiosk.service
systemctl status cv-card-demo.target
```

---

## 24. Späterer WLED-Erweiterungspfad

WLED wird bewusst als optionaler Pfad vorgesehen.

Spätere Erweiterung:

```text
BOOT_OPTIONAL_WLED_PREPARE
  ↓
BOOT_CHECK_WLED
  ↓
WLED_OK oder WLED_DEGRADED
```

Spätere Config:

```yaml
wled:
  enabled: true
  host: "http://192.168.4.50"
  timeout_ms: 300
  boot_probe_attempts: 3
  retry_interval_s: 2
  max_retry_interval_s: 30
  fail_mode: "degraded"
```

Wichtig bleibt:

> Auch bei aktiviertem WLED darf der BOOT nicht vollständig scheitern, solange UI und CV-Pipeline funktionieren.

WLED ist ein Ausgabekanal, nicht die Existenzberechtigung der Anwendung. Die LEDs dürfen hübsch sein, aber sie bekommen kein Vetorecht.

---

## 25. Zusammenfassung des BOOT-Steps

Der BOOT-Step ist erfolgreich, wenn:

```text
Backend läuft
UI-Service läuft
Health verfügbar
State Machine läuft
Transition zu INIT_CAM erfolgt
```

Der BOOT-Step macht noch nicht:

```text
Kamera öffnen
Frames lesen
OpenCV-Tracking starten
Karte erkennen
Score berechnen
LEDs ansteuern
```

Diese Aufgaben gehören in spätere States:

```text
INIT_CAM
CALIBRATION
IDLE_NO_CARD
TRACKING
OUTPUT_UPDATE
```

---

## 26. Empfohlene nächste Spezifikation

Nach diesem BOOT-Step sollte als nächstes der Zustand `INIT_CAM` definiert werden.

Dort werden konkret beschrieben:

- OpenCV-Import
- Kamera-Backend
- Kamera öffnen
- erste Frames lesen
- Reconnect-Strategie
- FPS-Prüfung
- Auflösung prüfen
- Fehlerpfad zu `RECOVERY` oder `ERROR_SAFE`
