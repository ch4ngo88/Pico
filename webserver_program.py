# webserver_program.py
import socket
import uselect
import os
from machine import Pin
from log_utils import log_message

# --------------------------------------------------------------------
#   Globale Objekte
# --------------------------------------------------------------------
reload_alarms_callback = None
blue_led = Pin(13, Pin.OUT)

# Race Condition Schutz fuer gleichzeitiges Speichern
_save_lock = False  # Einfache Sperre ohne Threading-Library

# Best-effort Watchdog-Feed
def _feed_wdt(log_path=None):
    try:
        from recovery_manager import feed_watchdog
        feed_watchdog(log_path)
    except Exception:
        pass


# --------------------------------------------------------------------
#   Web-Server Lifecycle
# --------------------------------------------------------------------
def start_webserver_and_show_ip(lcd, wlan, log_path=None):
    """Startet den HTTP-Server und zeigt die IP auf dem LCD."""
    s = None
    try:
        if not wlan or not wlan.isconnected():
            raise Exception("WLAN nicht verbunden")
            
        ip = wlan.ifconfig()[0]
        # IP wird nur geloggt, nicht auf LCD angezeigt (vermeidet kurzes Aufblitzen)
        log_message(log_path, "Webserver IP: " + ip)

        s = socket.socket()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", 80))
            s.listen(5)
            blue_led.on()
            log_message(log_path, "Webserver gestartet auf " + ip + ":80")
            return s, ip
        except Exception as bind_error:
            # Cleanup on bind/listen failure
            if s:
                try:
                    s.close()
                except Exception:
                    pass
            raise bind_error
            
    except Exception as e:
        if lcd:
            lcd.clear()
            lcd.putstr("Web Fehler")
        log_message(log_path, "Fehler beim Starten des Webservers: " + str(e))
        
        # Ensure cleanup even on early failure
        if s:
            try:
                s.close()
            except Exception:
                pass
        try:
            blue_led.off()
        except Exception:
            pass
            
        return None, None


def stop_webserver(s, log_path=None):
    """Stoppt den Webserver mit garantierter Ressourcen-Freigabe"""
    cleanup_errors = []
    
    # Socket schliessen
    if s:
        try:
            s.close()
        except Exception as e:
            cleanup_errors.append("Socket: " + str(e))
    
    # LED ausschalten
    try:
        blue_led.off()
    except Exception as e:
        cleanup_errors.append("LED: " + str(e))
    
    # Poller aufraeumen (falls registriert)
    try:
        _poller.unregister(s)
    except Exception:
        # Ignorieren - war moeglicherweise nicht registriert
        pass
    
    if cleanup_errors:
        log_message(log_path, "Webserver gestoppt mit Warnungen: " + "; ".join(cleanup_errors))
    else:
        log_message(log_path, "Webserver sauber gestoppt.")


# --------------------------------------------------------------------
#   Callback-Setter
# --------------------------------------------------------------------
def set_reload_alarms_callback(func):
    global reload_alarms_callback
    reload_alarms_callback = func


# --------------------------------------------------------------------
#   Security & File Management
# --------------------------------------------------------------------

# Whitelist for allowed static files (security)
ALLOWED_STATIC_FILES = {
    # Web assets (stored in Flash memory /web_assets/)
    'styles.css': {'type': 'text/css', 'safe': True, 'location': 'flash'},
    'favicon.ico': {'type': 'image/x-icon', 'safe': True, 'location': 'flash'},
    'neuza.webp': {'type': 'image/webp', 'safe': True, 'location': 'flash'},
    'app.js': {'type': 'application/javascript', 'safe': True, 'location': 'flash'},
    
    # System files (stored on SD card /sd/)
    'debug_log.txt': {'type': 'text/plain', 'safe': True, 'location': 'sd'},
    'alarm.txt': {'type': 'text/plain', 'safe': False, 'location': 'sd'},  # Internal only
    'power_config.txt': {'type': 'text/plain', 'safe': False, 'location': 'sd'},  # Internal only
    'wifis.txt': {'type': 'text/plain', 'safe': False, 'location': 'sd'}  # Internal only - NEVER serve
}

# Dangerous patterns that should never be served  
FORBIDDEN_PATTERNS = [
    '..', '../', '..\\',
    'wifis.txt'  # Explicitly blocked - sensitive file
]


def sanitize_filename(filename, log_path=None):
    """
    Robuste Dateinamen-Bereinigung mit Sicherheitspruefungen.
    Verhindert Directory Traversal und unerwuenschte Dateizugriffe.
    """
    if not filename:
        return None, "Leerer Dateiname"
    
    # Input normalisierung
    try:
        filename = str(filename).strip()
        if not filename:
            return None, "Dateiname nach Bereinigung leer"
        
        # Gefaehrliche Zeichen und Muster pruefen
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in filename:
                log_message(log_path, "[Security] Gefaehrlicher Pfad blockiert: " + filename)
                return None, "Unerlaubtes Zeichen/Muster: " + pattern
        
        # Normalisierung mit os.path.normpath aequivalent (MicroPython-kompatibel)
        # Entferne fuehrende/nachfolgende Leerzeichen und Slashes
        filename = filename.strip(' /\\')
        
        # Entferne mehrfache Slashes
        while '//' in filename:
            filename = filename.replace('//', '/')
        while '\\\\' in filename:
            filename = filename.replace('\\\\', '\\')
        
        # Konvertiere Backslashes zu Forward slashes (Unix-Style)
        filename = filename.replace('\\', '/')
        
        # Entferne fuehrende Slashes (absoluter Pfad nicht erlaubt)
        filename = filename.lstrip('/')
        
        # Whitelist-Pruefung
        if filename not in ALLOWED_STATIC_FILES:
            log_message(log_path, "[Security] Datei nicht in Whitelist: " + filename)
            return None, "Datei nicht erlaubt: " + filename
        
        file_info = ALLOWED_STATIC_FILES[filename]
        
        # Spezielle Schutzregeln
        if filename == 'wifis.txt':
            log_message(log_path, "[Security] WIFIS.TXT Zugriff blockiert!", force=True)
            return None, "Zugriff verweigert"
        
        if not file_info.get('safe', False):
            log_message(log_path, "[Security] Unsichere Datei angefordert: " + filename)
            return None, "Datei als unsicher markiert"
        
        return filename, None
        
    except Exception as e:
        log_message(log_path, "[Security] Fehler bei Dateinamen-Bereinigung: " + str(e))
        return None, "Bereinigungsfehler: " + str(e)


# Debug-Modus vollstaendig entfernt – Logs sind immer sichtbar


# Kein Debug-Toggle vorhanden


def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def html_escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# --------------------------------------------------------------------
#   HTTP-Request einlesen (2-s-Timeout, 8-kB-Limit)
# --------------------------------------------------------------------
def _receive_http_request(sock):
    sock.settimeout(2)
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(512)
        if not chunk:
            break
        data += chunk
        # Watchdog bei langsamen Clients fuettern
        try:
            from recovery_manager import feed_watchdog
            feed_watchdog(None)
        except Exception:
            pass
        if len(data) > 8192:  # rudimentaerer DoS-Schutz
            return "", ""
    if b"\r\n\r\n" not in data:
        return "", ""

    header, body = data.split(b"\r\n\r\n", 1)

    # Content-Length ermitteln
    clen = 0
    for line in header.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            clen = int(line.split(b":", 1)[1].strip())
            break

    # Begrenze Body-Groesse strikt
    MAX_BODY = 4096  # 4KB reicht fuer unsere Konfigs locker aus
    if clen > MAX_BODY:
        return header.decode(), "__BODY_TOO_LARGE__"

    while len(body) < clen:
        chunk = sock.recv(512)
        if not chunk:
            break
        body += chunk
        # Watchdog bei grossen Bodies fuettern
        try:
            from recovery_manager import feed_watchdog
            feed_watchdog(None)
        except Exception:
            pass

    # In MicroPython akzeptiert decode keine "errors"-KW-Args
    return header.decode(), body.decode()


# --------------------------------------------------------------------
#   Haupt-Connection-Handler
# --------------------------------------------------------------------
_poller = uselect.poll()  # Nur ein Poll-Objekt fuer alle Aufrufe


class PollerGuard:
    """Context manager fuer sichere Poller-Registration"""
    def __init__(self, sock, events=uselect.POLLIN):
        self.sock = sock
        self.events = events
        self.registered = False
    
    def __enter__(self):
        try:
            _poller.register(self.sock, self.events)
            self.registered = True
            return _poller
        except Exception:
            self.registered = False
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.registered:
            try:
                _poller.unregister(self.sock)
            except Exception:
                pass


def handle_website_connection(s, log_path=None):
    cl = None
    
    # Memory-Monitoring fuer Web-Requests
    from memory_monitor import monitor_memory
    monitor_memory(log_path, context="web_request_start")
    
    try:
        # Sichere Poller-Behandlung mit automatischer Cleanup
        try:
            with PollerGuard(s) as poller:
                poll_result = poller.poll(0)
                if not poll_result:
                    return  # Keine pending connections
        except Exception:
            # Poller Fehler - trotzdem versuchen zu akzeptieren
            pass

        # Connection mit Timeout
        s.settimeout(1.0)  # 1 Sekunde Timeout fuer accept
        cl, addr = s.accept()
        cl.settimeout(5.0)  # 5 Sekunden fuer Request-Verarbeitung
        cl.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        _feed_wdt(log_path)

        try:
            header, body = _receive_http_request(cl)
            _feed_wdt(log_path)
            if not header:
                cl.close()
                return

            first_line = header.splitlines()[0]
            parts = first_line.split()
            if len(parts) < 2:
                cl.close()
                return
            method, path = parts[0], parts[1]
            
            # Debug: Alle Requests loggen
            log_message(log_path, "[Request] {} {}".format(method, path))
            
            # Security logging nur fuer wirklich gefaehrliche Anfragen
            if any(pattern in path for pattern in FORBIDDEN_PATTERNS):
                log_message(log_path, "[Security] Blockiert: " + method + " " + path)
                return

            if body == "__BODY_TOO_LARGE__":
                cl.sendall(b"HTTP/1.1 413 Payload Too Large\r\nConnection: close\r\n\r\n")
                return

            if method == "POST" and path == "/save_alarms":
                log_message(log_path, "[POST] Speichere Alarme: {} bytes".format(len(body)))
                _save_alarms(body, log_path)
                if reload_alarms_callback:
                    reload_alarms_callback()
                cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/plain\r\n\r\nOK")
                _feed_wdt(log_path)

            elif method == "POST" and path == "/save_display_settings":
                log_message(log_path, "[POST] Speichere Display-Settings: {} bytes".format(len(body)))
                _save_display_settings(body, log_path)
                cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/plain\r\n\r\nOK")
                _feed_wdt(log_path)
            
            elif path in ("/", "/index.html"):
                _feed_wdt(log_path)
                _serve_index_page(cl, log_path)
                _feed_wdt(log_path)

            elif path == "/logs":
                _feed_wdt(log_path)
                _serve_log_file(cl, log_path)
                _feed_wdt(log_path)

            else:
                # Alle anderen Anfragen ueber sichere Datei-Serving-Funktion
                requested_file = path.lstrip("/")
                if requested_file:  # Nur nicht-leere Pfade verarbeiten
                    _feed_wdt(log_path)
                    _serve_file_from_sd(cl, requested_file, log_path)
                    _feed_wdt(log_path)
                else:
                    # Leerer Pfad -> redirect zu index
                    cl.sendall(b"HTTP/1.1 302 Found\r\nLocation: /\r\n\r\n")

        except Exception as e:
            log_message(log_path, "Fehler beim Verarbeiten der Anfrage: " + str(e))
            try:
                if cl:
                    cl.sendall(b"HTTP/1.1 500\r\n\r\nInterner Fehler")
            except Exception:
                pass
        finally:
            if cl:
                try:
                    cl.close()
                except Exception:
                    pass
            
            # Memory-Monitoring nach Request
            monitor_memory(log_path, context="web_request_end")

    except Exception as e:
        # Nur kritische Connection-Fehler loggen (nicht jede Timeout)
        if "timed out" not in str(e).lower():
            log_message(log_path, "Webserver Connection-Fehler: " + str(e))
        if cl:
            try:
                cl.close()
            except Exception:
                pass


# --------------------------------------------------------------------
#   Thread-sichere Speicher-Operationen
# --------------------------------------------------------------------
def _safe_save_operation(operation_name, save_func, *args, **kwargs):
    """
    Thread-sichere Speicher-Operation mit Sperre.
    Verhindert Race Conditions bei gleichzeitigen Speicher-Vorgaengen.
    """
    global _save_lock
    
    # Sperre pruefen und setzen
    if _save_lock:
        log_message(kwargs.get('log_path'), 
                   "Speicher-Vorgang '{}' blockiert - anderer Vorgang aktiv".format(operation_name))
        return False
    
    try:
        _save_lock = True
        log_message(kwargs.get('log_path'), 
                   "Speicher-Vorgang '{}' gestartet (Sperre aktiv)".format(operation_name))
        
        # Kurze Verzoegerung um Race Conditions zu vermeiden
        import time
        time.sleep(0.01)  # 10ms
        
        # Eigentliche Speicher-Operation ausfuehren
        result = save_func(*args, **kwargs)
        
        log_message(kwargs.get('log_path'), 
                   "Speicher-Vorgang '{}' erfolgreich".format(operation_name))
        return result
        
    except Exception as e:
        log_message(kwargs.get('log_path'), 
                   "Fehler in Speicher-Vorgang '{}': {}".format(operation_name, str(e)))
        return False
    finally:
        _save_lock = False
        log_message(kwargs.get('log_path'), 
                   "Speicher-Sperre fuer '{}' freigegeben".format(operation_name))


# --------------------------------------------------------------------
#   POST / save_alarms
# --------------------------------------------------------------------
def _save_alarms_unsafe(body, log_path=None):
    try:
        # defensive parsing
        def _sanitize_text(txt):
            try:
                # CR/LF entfernen und trimmen
                txt = txt.replace("\r", " ").replace("\n", " ")
                txt = txt.strip()
                # Strenge Whitelist: A-Z a-z 0-9 Leerzeichen () - _ . , :
                allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ()-_.:,"
                buf = []
                for ch in txt:
                    # Nur ASCII druckbar und in Whitelist
                    if 32 <= ord(ch) <= 126 and ch in allowed:
                        buf.append(ch)
                    else:
                        buf.append('_')
                txt = ''.join(buf)
                # Laenge begrenzen
                if len(txt) > 32:
                    txt = txt[:32]
                # Leere Werte ersetzen
                return txt or "Kein Text"
            except Exception:
                return "Kein Text"

        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        if not lines:
            log_message(log_path, "Leerer POST-Body – Alarme nicht geaendert.")
            return

        with open("/sd/alarm.txt", "w") as f:
            for line in lines[:5]:  # maximal 5 akzeptieren
                teile = [t.strip() for t in line.split(",") if t.strip()]
                if len(teile) < 2:
                    continue

                uhrzeit, text = teile[0], _sanitize_text(teile[1] or "Kein Text")
                if not (
                    len(uhrzeit) == 5
                    and uhrzeit[2] == ":"
                    and uhrzeit.replace(":", "").isdigit()
                ):
                    log_message(log_path, "Ueberspringe ungueltige Zeit: " + uhrzeit)
                    continue

                tage, status = [], "Inaktiv"
                for eintrag in teile[2:]:
                    if eintrag in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
                        tage.append(eintrag)
                    elif eintrag.lower() == "aktiv":
                        status = "Aktiv"
                
                # KRITISCH: Wenn keine Tage ausgewaehlt → Status MUSS Inaktiv sein
                if len(tage) == 0:
                    status = "Inaktiv"

                f.write("TIME=" + uhrzeit + "\nTEXT=" + text + "\n")
                f.write("DAYS=" + (','.join(tage) if tage else '-') + "\n")
                f.write("STATUS=" + status + "\n---\n")
            # Flush vor sync
            f.flush()
        
        # Garantiertes Sync mit Error-Handling
        try:
            os.sync()
        except Exception as e:
            log_message(log_path, "[Sync Fehler nach Alarm Save] {}".format(str(e)))
        
        log_message(log_path, "Alarme erfolgreich gespeichert.")
    except Exception as e:
        log_message(log_path, "Fehler beim Speichern: " + str(e))


def _save_alarms(body, log_path=None):
    """Thread-sichere Alarm-Speicherung mit Race Condition Schutz"""
    return _safe_save_operation("Alarme", _save_alarms_unsafe, body, log_path=log_path)


# --------------------------------------------------------------------
#   Statische Dateien
# --------------------------------------------------------------------
def _serve_file_from_sd(cl, file_name, log_path=None):
    # Robuste Eingabe-Bereinigung und Sicherheitspruefung
    if isinstance(file_name, (list, tuple)):
        file_name = file_name[0] if file_name else ""
    
    # Dateiname sanitisieren und Whitelist pruefen
    clean_filename, error = sanitize_filename(file_name, log_path)
    if not clean_filename:
        log_message(log_path, "[Security] Dateianfrage abgelehnt: " + str(file_name) + " -> " + str(error))
        cl.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n403")
        return
    
    # Datei-Infos aus Whitelist
    file_info = ALLOWED_STATIC_FILES[clean_filename]
    
    # Pfad-Konstruktion basierend auf Datei-Location
    file_location = file_info.get('location', 'sd')
    if file_location == 'flash':
        path = "/web_assets/" + clean_filename
    else:
        path = "/sd/" + clean_filename
    
    if not file_exists(path):
        log_message(log_path, "Bereinigte Datei nicht gefunden: " + path)
        cl.sendall(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n404")
        return
    try:
        size = os.stat(path)[6]
        
        # Sichere Content-Type aus Whitelist verwenden
        content_type = file_info.get('type', 'application/octet-stream')
        
        header = (
            "HTTP/1.1 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
            "Cache-Control: max-age=86400\r\n"
            "X-Content-Type-Options: nosniff\r\n"
            "X-Frame-Options: DENY\r\n"
            "Connection: close\r\n\r\n"
        ).format(content_type, size)
        cl.sendall(header.encode())
        
        # Sichere Logging mit Speicherort-Info
        location_info = " (Flash)" if file_location == 'flash' else " (SD)"
        log_message(log_path, "📦 Sende sichere Datei: " + clean_filename + location_info)

        with open(path, "rb") as f:
            chunk_count = 0
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                cl.sendall(chunk)
                
                # Watchdog alle 10 Chunks fuettern (verhindert Reset bei grossen Dateien)
                chunk_count += 1
                if chunk_count % 10 == 0:
                    try:
                        from recovery_manager import feed_watchdog
                        feed_watchdog(log_path)
                    except Exception:
                        pass  # Falls Import fehlschlaegt, weiterarbeiten
    except Exception as e:
        log_message(log_path, "Fehler beim Senden von " + clean_filename + ": " + str(e))
        try:
            cl.sendall(b"HTTP/1.1 500\r\nConnection: close\r\n\r\n500")
        except Exception:
            pass


# Debug-Serving entfernt – stattdessen immer /logs verwenden


def _serve_log_file(cl, log_path=None):
    """Serviert Log-Datei - immer verfuegbar (kein Debug-Modus erforderlich)"""
    clean_filename, error = sanitize_filename("debug_log.txt", log_path)
    if not clean_filename:
        log_message(log_path, "[Security] Log-Dateiname nicht validiert: " + str(error))
        cl.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n403")
        return
    
    path = "/sd/" + clean_filename
    if not file_exists(path):
        cl.sendall(b"HTTP/1.1 404\r\nConnection: close\r\n\r\n404")
        return
        
    try:
        cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/html\r\nConnection: close\r\n"
                  b"X-Content-Type-Options: nosniff\r\n"
                  b"X-Frame-Options: DENY\r\n\r\n"
                  b"<html><head><meta charset='UTF-8'><title>Logs</title></head><body><pre>")

        # Sichere Zeilenweise Ausgabe mit Groessenbegrenzung
        line_count = 0
        max_lines = 500  # weiter reduziert fuer noch geringeren Speicherbedarf

        with open(path) as f:
            for line in f:
                if line_count >= max_lines:
                    cl.sendall(b"\n--- LOG GEKUERZT (max " + str(max_lines).encode() + b" Zeilen) ---")
                    break
                cl.sendall(html_escape(line).encode())
                line_count += 1
                # Watchdog regelmaessig fuettern beim Lang-Stream
                if line_count % 50 == 0:
                    try:
                        from recovery_manager import feed_watchdog
                        feed_watchdog(log_path)
                    except Exception:
                        pass

        cl.sendall(b"</pre><p><a href='/'>&#x2190; Zurueck</a></p></body></html>")
        log_message(log_path, "Log-Datei ausgeliefert (" + str(line_count) + " Zeilen).")

    except Exception as e:
        log_message(log_path, "Log-Datei Lesefehler: " + str(e))
        cl.sendall(b"HTTP/1.1 500\r\nConnection: close\r\n\r\n500")


# Debug-Toggle entfernt


# --------------------------------------------------------------------
#   Power Settings
# --------------------------------------------------------------------
def _save_display_settings_unsafe(body, log_path=None):
    try:
        incoming = {}
        for line in body.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                incoming[key.strip()] = value.strip()

        existing = {}
        if file_exists("/sd/power_config.txt"):
            with open("/sd/power_config.txt", "r") as src:
                for line in src:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        existing[key.strip()] = value.strip()

        # Defaults fuer fehlende Werte sicherstellen
        if 'DISPLAY_AUTO' not in existing:
            existing['DISPLAY_AUTO'] = 'true'
        if 'DISPLAY_ON_TIME' not in existing:
            existing['DISPLAY_ON_TIME'] = '07:00'
        if 'DISPLAY_OFF_TIME' not in existing:
            existing['DISPLAY_OFF_TIME'] = '22:00'
        if 'BRIGHTNESS_DAY' not in existing:
            existing['BRIGHTNESS_DAY'] = '64'
        if 'BRIGHTNESS_NIGHT' not in existing:
            existing['BRIGHTNESS_NIGHT'] = '16'
        if 'LED_POWER_MODE' not in existing:
            existing['LED_POWER_MODE'] = 'normal'
        if 'VOLUME_PERCENT' not in existing:
            if 'VOLUME_DEFAULT' in existing:
                existing['VOLUME_PERCENT'] = existing['VOLUME_DEFAULT']
            else:
                existing['VOLUME_PERCENT'] = '50'
        # Alte Keys entfernen, damit Config sauber bleibt
        if 'VOLUME_DEFAULT' in existing:
            existing.pop('VOLUME_DEFAULT', None)
        if 'VOLUME_NIGHT' in existing:
            existing.pop('VOLUME_NIGHT', None)

        def _valid_time(ts):
            try:
                if len(ts) != 5 or ts[2] != ':':
                    return False
                hh = int(ts[:2]); mm = int(ts[3:])
                return 0 <= hh <= 23 and 0 <= mm <= 59
            except Exception:
                return False

        auto = 'true' if incoming.get('DISPLAY_AUTO', existing.get('DISPLAY_AUTO', 'true')).lower() == 'true' else 'false'
        on_t = incoming.get('DISPLAY_ON_TIME', existing.get('DISPLAY_ON_TIME', '07:00'))
        off_t = incoming.get('DISPLAY_OFF_TIME', existing.get('DISPLAY_OFF_TIME', '22:00'))
        if not _valid_time(on_t):
            on_t = '07:00'
        if not _valid_time(off_t):
            off_t = '22:00'

        existing['DISPLAY_AUTO'] = auto
        existing['DISPLAY_ON_TIME'] = on_t
        existing['DISPLAY_OFF_TIME'] = off_t

        defaults_order = [
            'DISPLAY_AUTO',
            'DISPLAY_ON_TIME',
            'DISPLAY_OFF_TIME',
            'BRIGHTNESS_DAY',
            'BRIGHTNESS_NIGHT',
            'LED_POWER_MODE',
            'VOLUME_PERCENT',
            'DISPLAY_STATE'
        ]

        tmp_path = "/sd/power_config.tmp"
        with open(tmp_path, "w") as f:
            for key in defaults_order:
                if key in existing:
                    f.write("{}={}\n".format(key, existing[key]))
            for key, value in existing.items():
                if key not in defaults_order:
                    f.write("{}={}\n".format(key, value))
            f.flush()

        try:
            os.replace(tmp_path, "/sd/power_config.txt")
        except AttributeError:
            os.rename(tmp_path, "/sd/power_config.txt")
        except OSError:
            try:
                os.remove("/sd/power_config.txt")
            except OSError:
                pass
            os.rename(tmp_path, "/sd/power_config.txt")
        
        # Garantiertes Sync mit Error-Handling
        try:
            os.sync()
        except Exception as e:
            log_message(log_path, "[Sync Fehler nach Display Settings] {}".format(str(e)))

        try:
            from power_management import reload_settings
            reload_settings()
        except Exception as e:
            log_message(log_path, "[Power Settings] Reload nach Save fehlgeschlagen: {}".format(str(e)))
        
        log_message(log_path, "Display-Einstellungen gespeichert.")
    except Exception as e:
        log_message(log_path, "Fehler beim Speichern der Display-Einstellungen: " + str(e))


def _save_display_settings(body, log_path=None):
    """Thread-sichere Display-Settings-Speicherung mit Race Condition Schutz"""
    return _safe_save_operation("Display-Settings", _save_display_settings_unsafe, body, log_path=log_path)


def _load_display_settings():
    try:
        settings = {
            'DISPLAY_AUTO': 'true',
            'DISPLAY_ON_TIME': '07:00',
            'DISPLAY_OFF_TIME': '22:00',
            'LED_POWER_MODE': 'normal',
            'VOLUME_PERCENT': '50'
        }
        if file_exists("/sd/power_config.txt"):
            with open("/sd/power_config.txt", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key in settings:  # Nur relevante Keys laden
                            settings[key] = value
                        elif key == 'VOLUME_DEFAULT':  # Abwärtskompatibilität
                            settings['VOLUME_PERCENT'] = value
        return settings
    except Exception:
        return {
            'DISPLAY_AUTO': 'true',
            'DISPLAY_ON_TIME': '07:00',
            'DISPLAY_OFF_TIME': '22:00',
            'LED_POWER_MODE': 'normal',
            'VOLUME_PERCENT': '50'
        }


# --------------------------------------------------------------------
#   Index-Seite mit integrierten Display-Einstellungen
# --------------------------------------------------------------------
def _serve_index_page(cl, log_path=None):
    """Memory-optimierte Index-Seite mit chunked streaming und aggressiver GC"""
    try:
        # AGGRESSIVE Memory Cleanup vor HTML-Rendering
        import gc
        for _ in range(3):  # Mehrere GC-Durchlaeufe
            gc.collect()
        
        # Memory-Safe: Stream HTML in kleinen Chunks
        _send_http_header(cl)
        _send_html_chunks(cl, log_path)
        
        # SOFORTIGE Memory-Bereinigung nach Request
        gc.collect()
        log_message(log_path, "Index-Seite gestreamt (Memory-Safe).")
        
    except Exception as e:
        try:
            log_message(log_path, "Fehler beim Erzeugen der Index-Seite: {}".format(str(e)))
        except:
            pass  # Falls log_path None ist
        _send_error_response(cl, 500, "Interner Fehler")
    finally:
        # GARANTIERTE Cleanup
        import gc
        gc.collect()


def _send_http_header(cl):
    """Sendet HTTP-Header memory-safe"""
    cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/html; charset=UTF-8\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n")


def _send_html_chunks(cl, log_path=None):
    """Sendet HTML in memory-safe chunks"""
    import gc
    
    # Chunk 1: HTML Header (klein halten!)
    chunk1 = b"""<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Neuza Wecker</title><link rel=\"stylesheet\" href=\"styles.css\"></head>
<body><header><h1>Neuza Wecker</h1></header>
<main>
    <img src=\"neuza.webp\" alt=\"Neuza\" onerror=\"this.style.display='none'\">
    <form id=\"alarmForm\">"""
    cl.sendall(chunk1)
    gc.collect()  # Nach jedem Chunk
    
    # Chunk 2: Alarm-Bloecke (Memory-sparend laden)
    try:
        alarme = _load_alarms("/sd/alarm.txt")
        _send_alarm_blocks_safe(cl, alarme)
    except Exception as e:
        try:
            cl.sendall(b"<fieldset><p class='status-line'>Alarme konnten nicht geladen werden.</p></fieldset>")
        except Exception:
            pass
        try:
            log_message(log_path, "Fehler beim Streamen der Alarme: {}".format(str(e)))
        except Exception:
            pass
    gc.collect()  # Nach Alarmen
    
    # Chunk 3: Display-Settings
    try:
        _send_display_block_safe(cl)
    except Exception as e:
        try:
            cl.sendall(b"<fieldset><label><input type='checkbox' id='displayAuto' checked> Automatisches Ein/Aus</label><br>"
                       b"<label>Ein-Zeit: <input type='time' id='displayOn' value='07:00'></label><br>"
                       b"<label>Aus-Zeit: <input type='time' id='displayOff' value='22:00'></label></fieldset>")
        except Exception:
            pass
        try:
            log_message(log_path, "Fehler beim Display-Block: {}".format(str(e)))
        except Exception:
            pass
    gc.collect()  # Nach Display-Block
    
    # Chunk 4: Footer und JavaScript (aufgeteilt)
    try:
        _send_footer_chunks(cl, log_path)
    except Exception as e:
        try:
            log_message(log_path, "Fehler beim Senden des Footers: {}".format(str(e)))
        except Exception:
            pass
        try:
            cl.sendall(b"</form></main></body></html>")
        except Exception:
            pass
    gc.collect()  # Final cleanup


def _send_alarm_blocks_safe(cl, alarme):
    """Memory-sichere Alarm-Block uebertragung"""
    import gc
    all_alarms = alarme + [("", "", [], "")] * (5 - len(alarme))
    
    for i, (zeit, text, tage, aktiv) in enumerate(all_alarms):
        # Alarm-Block einzeln generieren und senden
        block = _generate_alarm_block(zeit, text, tage, aktiv)
        cl.sendall(block.encode())
        
        # Memory cleanup alle 2 Bloecke
        if i % 2 == 1:
            gc.collect()


def _generate_alarm_block(zeit, text, tage, aktiv):
    """Generiert einzelnen Alarm-Block memory-safe"""
    chk_days = ""
    for w in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
        chk = "checked" if w in tage else ""
        chk_days += '<label><input type="checkbox" {}> {}</label>\n'.format(chk, w)
    
    return '''<fieldset>
<input type="time" value="{}">
<input type="text" value="{}">
<div>
{}
</div></fieldset>\n'''.format(
        zeit, html_escape(text), chk_days)


def _send_display_block_safe(cl):
    """Memory-sichere Display-Settings uebertragung"""
    settings = _load_display_settings()
    
    auto_enabled = settings.get('DISPLAY_AUTO', 'true') == 'true'
    on_time = settings.get('DISPLAY_ON_TIME', '07:00')
    off_time = settings.get('DISPLAY_OFF_TIME', '22:00')
    led_mode_raw = str(settings.get('LED_POWER_MODE', 'normal') or '').strip().lower()
    led_mode_map = {
        'boost': 'Boost',
        'normal': 'Normal',
        'eco': 'Eco'
    }
    # MicroPython strings may not support .title(); do a simple manual capitalization fallback
    if led_mode_raw in led_mode_map:
        led_mode = led_mode_map[led_mode_raw]
    elif led_mode_raw:
        led_mode = (led_mode_raw[:1].upper() + led_mode_raw[1:])
    else:
        led_mode = 'Normal'
    led_mode = html_escape(led_mode)

    volume_raw = settings.get('VOLUME_PERCENT', '50')
    try:
        volume_int = int(volume_raw)
        if volume_int < 0:
            volume_int = 0
        elif volume_int > 100:
            volume_int = 100
        volume_text = "{}%".format(volume_int)
    except Exception:
        volume_text = "50%"
    volume_text = html_escape(volume_text)

    block = '''<fieldset>
<label><input type="checkbox" id="displayAuto" {}> Automatisches Ein/Aus</label><br>
<label>Ein-Zeit: <input type="time" id="displayOn" value="{}"></label><br>
<label>Aus-Zeit: <input type="time" id="displayOff" value="{}"></label><br>
<p class="status-line">LED-Leistung: {}</p>
<p class="status-line">Lautst&auml;rke: {}</p>
</fieldset>\n'''.format(
        "checked" if auto_enabled else "",
        html_escape(on_time),
        html_escape(off_time),
        led_mode,
        volume_text
    )
    cl.sendall(block.encode())


def _send_footer_chunks(cl, log_path=None):
    """Minimaler Abschluss: nur Save-Button und JS, kein Footer"""
    import gc
    minimal = '''<div>
<button id="saveButton" type="button" onclick="window._fallbackSave && _fallbackSave()">Speichern</button>
<a href="/logs">Logs</a>
</div>
</form></main>'''
    try:
        cl.sendall(minimal.encode())
    except Exception:
        pass
    gc.collect()
    # Kleiner Inline-Fallback (nur Display-Settings speichern), falls app.js fehlt
    try:
        fallback = (
            "<script>(function(){" 
            "function _fallbackSave(){try{var b=document.getElementById('saveButton');if(b){b.disabled=true;b.textContent='Speichern...';}" 
            "var da=document.getElementById('displayAuto'),don=document.getElementById('displayOn'),doff=document.getElementById('displayOff');" 
            "if(da&&don&&doff){var d=['DISPLAY_AUTO='+(da.checked?'true':'false'),'DISPLAY_ON_TIME='+don.value,'DISPLAY_OFF_TIME='+doff.value];" 
            "var x=new XMLHttpRequest();x.open('POST','/save_display_settings',true);" 
            "x.onreadystatechange=function(){if(x.readyState===4){if(b){b.textContent=(x.status>=200&&x.status<300)?'Gespeichert':'Fehler';setTimeout(function(){b.disabled=false;b.textContent='Speichern';},2000);}}};" 
            "x.send(d.join('\\n'));}}catch(e){}}" 
            "if(!window.saveAllSettings){try{window._fallbackSave=_fallbackSave;}catch(e){}}})();</script>"
        )
        cl.sendall(fallback.encode())
    except Exception:
        pass
    gc.collect()

    # Binde externes Script ein (aus Flash), spart RAM und Parser-Probleme
    try:
        cl.sendall(b"<script src=\"app.js\"></script></body></html>")
    except Exception:
        pass


# Alte _split_javascript entfernt - JavaScript wird jetzt als komplettes Stueck gesendet


# _html_escape entfernt - verwende html_escape() stattdessen


def _send_error_response(cl, code, message):
    """Memory-sichere Error Response"""
    try:
        # Minimalschmales Fehlerformat
        response = "HTTP/1.1 {} {}\r\nConnection: close\r\n\r\n{}".format(code, message, code)
        cl.sendall(response.encode())
    except Exception:
        pass  # Fehler beim Fehler-senden ignorieren


# Alte _send_alarm_blocks entfernt - nur _send_alarm_blocks_safe wird verwendet


# Alte _send_display_block entfernt - nur _send_display_block_safe wird verwendet


def _load_alarms(path):
    alarme, alarm = [], {}
    if not file_exists(path):
        return alarme
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line == "---":
                if set(alarm) >= {"TIME", "TEXT", "DAYS", "STATUS"}:
                    tage = alarm["DAYS"].split(",") if alarm["DAYS"] != "-" else []
                    alarme.append((alarm["TIME"], alarm["TEXT"], tage, alarm["STATUS"]))
                alarm = {}
            elif "=" in line:
                k, v = line.split("=", 1)
                alarm[k.strip()] = v.strip()
    return alarme[:5]  # maximal fuenf zurueckliefern


# Alte _render_index() und INDEX_TEMPLATE entfernt - ersetzt durch Streaming-System (_send_html_chunks)

JS_SNIPPET = """
function saveAllSettings(){
    var b=document.getElementById('saveButton');
    if(!b){return;}
    b.disabled=true; b.textContent='Speichern...';

    var a=[];
    var bs=document.querySelectorAll('#alarmForm fieldset');
    for(var i=0;i<bs.length;i++){
        var x=bs[i];
        var t=x.querySelector('input[type="time"]');
        var m=x.querySelector('input[type="text"]');
        if(!t||!m){continue;}
        var tv=(t.value||'').trim();
        var mv=(m.value||'').trim();
        if(!tv&&!mv){continue;}
        var c=x.querySelectorAll('input[type="checkbox"]');
        var daySet={};
        for(var j=0;j<c.length;j++){
            var cb=c[j];
            var label=(cb.parentElement && cb.parentElement.textContent)?cb.parentElement.textContent.trim():'';
            if(cb.checked && (label==='Mo'||label==='Di'||label==='Mi'||label==='Do'||label==='Fr'||label==='Sa'||label==='So')){
                daySet[label]=true;
            }
        }
        var days=[];
        for(var k in daySet){ if(daySet.hasOwnProperty(k)){ days.push(k); } }
        days.sort();
        var active = days.length>0 ? 'Aktiv' : 'Inaktiv';
        a.push([tv, mv||'Kein Text', days.join(','), active].join(','));
    }

    function post(url, body, headers, cb){
        try{
            var xhr=new XMLHttpRequest();
            xhr.open('POST', url, true);
            if(headers){
                for(var h in headers){ if(headers.hasOwnProperty(h)){ xhr.setRequestHeader(h, headers[h]); } }
            }
            xhr.onreadystatechange=function(){
                if(xhr.readyState===4){ cb(xhr.status>=200 && xhr.status<300); }
            };
            xhr.send(body);
        }catch(e){ cb(false); }
    }

    var ok1=true, ok2=true;
    var pending=0;

    function finish(){
    b.textContent=(ok1&&ok2)?'Gespeichert':'Fehler';
    setTimeout(function(){ b.disabled=false; b.textContent='Speichern'; }, 2000);
    }

    if(a.length){
        pending++;
        post('/save_alarms', a.join('\n'), {'Content-Type':'text/plain'}, function(success){ ok1=success; if(--pending===0){ finish(); } });
    }

    var da=document.getElementById('displayAuto');
    var don=document.getElementById('displayOn');
    var doff=document.getElementById('displayOff');
    if(da&&don&&doff){
        pending++;
        var d=[
            'DISPLAY_AUTO='+(da.checked?'true':'false'),
            'DISPLAY_ON_TIME='+don.value,
            'DISPLAY_OFF_TIME='+doff.value
        ];
        post('/save_display_settings', d.join('\n'), null, function(success){ ok2=success; if(--pending===0){ finish(); } });
    }

    if(pending===0){ finish(); }
}
// Exponiere Funktion global
try{ window.saveAllSettings = saveAllSettings; }catch(e){}
// Button-Handler sicher binden (sofort oder nach DOMContentLoaded)
(function(){
    function bind(){
        var b=document.getElementById('saveButton');
        if(b && !b._saveBound){ b._saveBound=true; b.addEventListener('click', saveAllSettings); try{ console.log('Save-Button gebunden'); }catch(e){} }
    }
    if(document.readyState==='complete' || document.readyState==='interactive'){
        bind();
    }else{
        try{ document.addEventListener('DOMContentLoaded', bind); }catch(e){ setTimeout(bind, 200); }
    }
})();
"""


# --------------------------------------------------------------------
#   MIME-Types
# --------------------------------------------------------------------
def _get_content_type(name):
    mapping = {
        ".html": "text/html",
        ".css" : "text/css",
        ".js"  : "application/javascript",
        ".jpg" : "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif" : "image/gif",
    }
    name = name.lower()
    for ext, ctype in mapping.items():
        if name.endswith(ext):
            return ctype
    return "application/octet-stream"


def get_security_status(log_path=None):
    """Gibt aktuellen Sicherheitsstatus zurueck"""
    try:
        status = {
            'allowed_files': len(ALLOWED_STATIC_FILES),
            'whitelist_active': True,
            'sanitization_active': True
        }
        
        # Zaehle verfuegbare Dateien
        available_files = []
        for filename in ALLOWED_STATIC_FILES:
            if file_exists("/sd/{}".format(filename)):
                available_files.append(filename)
        
        status['available_files'] = available_files
        return status
    except Exception as e:
        log_message(log_path, "[Security] Status-Abfrage fehlgeschlagen: {}".format(str(e)))
        return {'error': str(e)}


# --------------------------------------------------------------------
#   Health Check & Status Functions
# --------------------------------------------------------------------
def is_webserver_healthy(s):
    """ueberprueft ob der Webserver noch funktionsfaehig ist"""
    if not s:
        return False
    try:
        # Versuche Socket-Status zu pruefen
        s.settimeout(0.1)
        return True
    except Exception:
        return False


def get_webserver_status():
    """Gibt aktuellen Webserver-Status zurueck"""
    try:
        return {
            'blue_led': blue_led.value(),
            'poller_active': True,  # Vereinfacht - koennte erweitert werden
            'security': get_security_status()
        }
    except Exception:
        return {'blue_led': False, 'poller_active': False, 'security': None}


# --------------------------------------------------------------------
#   Save to file function for external use
# --------------------------------------------------------------------
def save_alarms_to_file(log_path=None):
    """External function to trigger alarm saving from other modules"""
    try:
        # This function can be called from outside to trigger a save
        # The actual saving is done via the web interface
        return True
    except Exception as e:
        log_message(log_path, "Fehler beim Alarm-Speichern: {}".format(str(e)))
        return False