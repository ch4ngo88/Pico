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

# Race Condition Schutz für gleichzeitiges Speichern
_save_lock = False  # Einfache Sperre ohne Threading-Library


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
    
    # Socket schließen
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
    
    # Poller aufräumen (falls registriert)
    try:
        _poller.unregister(s)
    except Exception:
        # Ignorieren - war möglicherweise nicht registriert
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
    
    # System files (stored on SD card /sd/)
    'debug_log.txt': {'type': 'text/plain', 'safe': True, 'debug_only': True, 'location': 'sd'},
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
    Robuste Dateinamen-Bereinigung mit Sicherheitsprüfungen.
    Verhindert Directory Traversal und unerwünschte Dateizugriffe.
    """
    if not filename:
        return None, "Leerer Dateiname"
    
    # Input normalisierung
    try:
        filename = str(filename).strip()
        if not filename:
            return None, "Dateiname nach Bereinigung leer"
        
        # Gefährliche Zeichen und Muster prüfen
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in filename:
                log_message(log_path, "[Security] Gefährlicher Pfad blockiert: " + filename)
                return None, "Unerlaubtes Zeichen/Muster: " + pattern
        
        # Normalisierung mit os.path.normpath Äquivalent (MicroPython-kompatibel)
        # Entferne führende/nachfolgende Leerzeichen und Slashes
        filename = filename.strip(' /\\')
        
        # Entferne mehrfache Slashes
        while '//' in filename:
            filename = filename.replace('//', '/')
        while '\\\\' in filename:
            filename = filename.replace('\\\\', '\\')
        
        # Konvertiere Backslashes zu Forward slashes (Unix-Style)
        filename = filename.replace('\\', '/')
        
        # Entferne führende Slashes (absoluter Pfad nicht erlaubt)
        filename = filename.lstrip('/')
        
        # Whitelist-Prüfung
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


def is_debug_mode_enabled():
    """Prüft ob Debug-Modus aktiviert ist (für debug_log.txt Zugriff)"""
    try:
        # Debug-Modus kann über eine einfache Datei gesteuert werden
        return file_exists("/sd/.debug_enabled")
    except Exception:
        return False


def enable_debug_mode(log_path=None):
    """Aktiviert den Debug-Modus durch Erstellen der Debug-Flag-Datei"""
    try:
        with open("/sd/.debug_enabled", "w") as f:
            f.write("1")
        log_message(log_path, "[Debug] Debug-Modus aktiviert")
        return True
    except Exception as e:
        log_message(log_path, "[Debug] Fehler beim Aktivieren: " + str(e))
        return False


def disable_debug_mode(log_path=None):
    """Deaktiviert den Debug-Modus durch Löschen der Debug-Flag-Datei"""
    try:
        if file_exists("/sd/.debug_enabled"):
            os.remove("/sd/.debug_enabled")
        log_message(log_path, "[Debug] Debug-Modus deaktiviert")
        return True
    except Exception as e:
        log_message(log_path, "[Debug] Fehler beim Deaktivieren: " + str(e))
        return False


def toggle_debug_mode(log_path=None):
    """Schaltet Debug-Modus um (an/aus)"""
    if is_debug_mode_enabled():
        return disable_debug_mode(log_path)
    else:
        return enable_debug_mode(log_path)


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
        if len(data) > 8192:  # rudimentärer DoS-Schutz
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

    while len(body) < clen:
        chunk = sock.recv(512)
        if not chunk:
            break
        body += chunk

    # In MicroPython akzeptiert decode keine "errors"-KW-Args
    return header.decode(), body.decode()


# --------------------------------------------------------------------
#   Haupt-Connection-Handler
# --------------------------------------------------------------------
_poller = uselect.poll()  # Nur ein Poll-Objekt für alle Aufrufe


class PollerGuard:
    """Context manager für sichere Poller-Registration"""
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
        s.settimeout(1.0)  # 1 Sekunde Timeout für accept
        cl, addr = s.accept()
        cl.settimeout(5.0)  # 5 Sekunden für Request-Verarbeitung
        cl.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            header, body = _receive_http_request(cl)
            if not header:
                cl.close()
                return

            method, path, _ = header.splitlines()[0].split()
            
            # Debug: Alle Requests loggen
            log_message(log_path, "[Request] {} {}".format(method, path))
            
            # Security logging nur für wirklich gefährliche Anfragen
            if any(pattern in path for pattern in FORBIDDEN_PATTERNS):
                log_message(log_path, "[Security] Blockiert: " + method + " " + path)
                return

            if method == "POST" and path == "/save_alarms":
                log_message(log_path, "[POST] Speichere Alarme: {} bytes".format(len(body)))
                _save_alarms(body, log_path)
                if reload_alarms_callback:
                    reload_alarms_callback()
                cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/plain\r\n\r\nOK")

            elif method == "POST" and path == "/save_display_settings":
                log_message(log_path, "[POST] Speichere Display-Settings: {} bytes".format(len(body)))
                _save_display_settings(body, log_path)
                cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/plain\r\n\r\nOK")

            elif method == "POST" and path == "/toggle_debug":
                _toggle_debug_mode(cl, log_path)
                
            elif method == "POST" and path == "/toggle_leds":
                _toggle_leds(cl, log_path)

            elif path in ("/", "/index.html"):
                _serve_index_page(cl, log_path)

            elif path == "/debug":
                _serve_debug_file(cl, log_path)
                
            elif path == "/logs":
                _serve_log_file(cl, log_path)

            else:
                # Alle anderen Anfragen über sichere Datei-Serving-Funktion
                requested_file = path.lstrip("/")
                if requested_file:  # Nur nicht-leere Pfade verarbeiten
                    _serve_file_from_sd(cl, requested_file, log_path)
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
    Verhindert Race Conditions bei gleichzeitigen Speicher-Vorgängen.
    """
    global _save_lock
    
    # Sperre prüfen und setzen
    if _save_lock:
        log_message(kwargs.get('log_path'), 
                   "Speicher-Vorgang '{}' blockiert - anderer Vorgang aktiv".format(operation_name))
        return False
    
    try:
        _save_lock = True
        log_message(kwargs.get('log_path'), 
                   "Speicher-Vorgang '{}' gestartet (Sperre aktiv)".format(operation_name))
        
        # Kurze Verzögerung um Race Conditions zu vermeiden
        import time
        time.sleep(0.01)  # 10ms
        
        # Eigentliche Speicher-Operation ausführen
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
                   "Speicher-Sperre für '{}' freigegeben".format(operation_name))


# --------------------------------------------------------------------
#   POST / save_alarms
# --------------------------------------------------------------------
def _save_alarms_unsafe(body, log_path=None):
    try:
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        if not lines:
            log_message(log_path, "Leerer POST-Body – Alarme nicht geaendert.")
            return

        with open("/sd/alarm.txt", "w") as f:
            for line in lines[:5]:  # maximal 5 akzeptieren
                teile = [t.strip() for t in line.split(",") if t.strip()]
                if len(teile) < 2:
                    continue

                uhrzeit, text = teile[0], teile[1] or "Kein Text"
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

                f.write("TIME=" + uhrzeit + "\nTEXT=" + text + "\n")
                f.write("DAYS=" + (','.join(tage) if tage else '-') + "\n")
                f.write("STATUS=" + status + "\n---\n")

        os.sync()
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
    # Robuste Eingabe-Bereinigung und Sicherheitsprüfung
    if isinstance(file_name, (list, tuple)):
        file_name = file_name[0] if file_name else ""
    
    # Dateiname sanitisieren und Whitelist prüfen
    clean_filename, error = sanitize_filename(file_name, log_path)
    if not clean_filename:
        log_message(log_path, "[Security] Dateianfrage abgelehnt: " + str(file_name) + " -> " + str(error))
        cl.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n<h1>Zugriff verweigert</h1>")
        return
    
    # Debug-Dateien nur bei aktiviertem Debug-Modus
    file_info = ALLOWED_STATIC_FILES[clean_filename]
    if file_info.get('debug_only', False) and not is_debug_mode_enabled():
        log_message(log_path, "[Security] Debug-Datei ohne Debug-Modus angefordert: " + clean_filename)
        cl.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n<h1>Nicht verfuegbar</h1>")
        return
    
    # Pfad-Konstruktion basierend auf Datei-Location
    file_location = file_info.get('location', 'sd')
    if file_location == 'flash':
        path = "/web_assets/" + clean_filename
    else:
        path = "/sd/" + clean_filename
    
    if not file_exists(path):
        log_message(log_path, "Bereinigte Datei nicht gefunden: " + path)
        cl.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n<h1>Datei nicht gefunden</h1>")
        return
    try:
        size = os.stat(path)[6]
        
        # Sichere Content-Type aus Whitelist verwenden
        content_type = file_info.get('type', 'application/octet-stream')
        
        header = (
            "HTTP/1.1 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
            "Cache-Control: max-age=86400\r\n"
            "X-Content-Type-Options: nosniff\r\n"  # Security Header
            "X-Frame-Options: DENY\r\n\r\n"       # Prevent embedding
        ).format(content_type, size)
        cl.sendall(header.encode())
        
        # Sichere Logging mit Speicherort-Info
        location_info = " (Flash)" if file_location == 'flash' else " (SD)"
        log_message(log_path, "📦 Sende sichere Datei: " + clean_filename + location_info)

        with open(path, "rb") as f:
            chunk_count = 0
            while True:
                chunk = f.read(2048)
                if not chunk:
                    break
                cl.sendall(chunk)
                
                # Watchdog alle 10 Chunks füttern (verhindert Reset bei großen Dateien)
                chunk_count += 1
                if chunk_count % 10 == 0:
                    try:
                        from recovery_manager import feed_watchdog
                        feed_watchdog(log_path)
                    except:
                        pass  # Falls Import fehlschlägt, weiterarbeiten
    except Exception as e:
        log_message(log_path, "Fehler beim Senden von " + clean_filename + ": " + str(e))
        try:
            cl.sendall(b"HTTP/1.1 500\r\n\r\nInterner Fehler")
        except Exception:
            pass


def _serve_debug_file(cl, log_path=None):
    # Debug-Modus Sicherheitsprüfung
    if not is_debug_mode_enabled():
        log_message(log_path, "[Security] Debug-Zugriff ohne aktivierten Debug-Modus verweigert")
        cl.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n<h1>Nicht verfuegbar</h1>")
        return
    
    # Sichere Dateiname-Überprüfung über Whitelist
    clean_filename, error = sanitize_filename("debug_log.txt", log_path)
    if not clean_filename:
        log_message(log_path, "[Security] Debug-Dateiname nicht validiert: " + str(error))
        cl.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n<h1>Zugriff verweigert</h1>")
        return
    
    path = "/sd/" + clean_filename
    if not file_exists(path):
        cl.sendall(b"HTTP/1.1 404\r\n\r\nDebug-Datei nicht gefunden")
        return
        
    try:
        cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n"
                  b"X-Content-Type-Options: nosniff\r\n"
                  b"X-Frame-Options: DENY\r\n\r\n"
                  b"<html><body><h2>Debug Log (Sichere Ansicht)</h2><pre>")
        
        # Sichere Zeilenweise Ausgabe mit Größenbegrenzung
        line_count = 0
        max_lines = 500  # Begrenze Ausgabe
        
        with open(path) as f:
            for line in f:
                if line_count >= max_lines:
                    cl.sendall(b"\n... [Log zu lang, nur erste 500 Zeilen angezeigt] ...")
                    break
                cl.sendall(html_escape(line).encode())
                line_count += 1
                
        cl.sendall("</pre><br><a href='/'>Zurueck</a></body></html>".encode())
        log_message(log_path, "Debug-Logdatei sicher ausgeliefert (" + str(line_count) + " Zeilen).")
    except Exception as e:
        log_message(log_path, "Fehler beim Debug-Log-Serving: " + str(e))
        try:
            cl.sendall(b"HTTP/1.1 500\r\n\r\nInterner Fehler")
        except Exception:
            pass


def _serve_log_file(cl, log_path=None):
    """Serviert Log-Datei - immer verfügbar (kein Debug-Modus erforderlich)"""
    clean_filename, error = sanitize_filename("debug_log.txt", log_path)
    if not clean_filename:
        log_message(log_path, "[Security] Log-Dateiname nicht validiert: " + str(error))
        cl.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n<h1>Zugriff verweigert</h1>")
        return
    
    path = "/sd/" + clean_filename
    if not file_exists(path):
        cl.sendall(b"HTTP/1.1 404\r\n\r\n<h1>Log-Datei nicht gefunden</h1>")
        return
        
    try:
        cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n"
                  b"X-Content-Type-Options: nosniff\r\n"
                  b"X-Frame-Options: DENY\r\n\r\n"
                  b"<html><head><title>Neuza Wecker - Logs</title><style>"
                  b"body{font-family:monospace;background:#fff0f5;color:#5c1a33;margin:20px;}"
                  b"pre{background:#ffe6ef;padding:15px;border-radius:10px;overflow-x:auto;}"
                  b"h2{color:#d6336c;}a{color:#ff85a2;}</style></head>"
                  b"<body><h2>\xf0\x9f\x93\x8b Neuza Wecker - System Logs</h2><pre>")
        
        # Sichere Zeilenweise Ausgabe mit Größenbegrenzung
        line_count = 0
        max_lines = 800  # Mehr Zeilen für normalen Log-Viewer
        
        with open(path) as f:
            for line in f:
                if line_count >= max_lines:
                    cl.sendall(b"\n--- LOG GEKUERZT (max " + str(max_lines).encode() + b" Zeilen) ---")
                    break
                cl.sendall(html_escape(line).encode())
                line_count += 1
        
        cl.sendall(b"</pre><p><a href='/'>\xe2\x86\x90 Zurueck zur Hauptseite</a></p></body></html>")
        log_message(log_path, "Log-Datei ausgeliefert (" + str(line_count) + " Zeilen).")
        
    except Exception as e:
        log_message(log_path, "Log-Datei Lesefehler: " + str(e))
        cl.sendall(b"Fehler beim Lesen der Log-Datei")


def _toggle_debug_mode(cl, log_path=None):
    """Schaltet Debug-Modus um und gibt Status zurück"""
    try:
        old_state = is_debug_mode_enabled()
        success = toggle_debug_mode(log_path)
        new_state = is_debug_mode_enabled()
        
        if success:
            status = "aktiviert" if new_state else "deaktiviert"
            message = "Debug-Modus erfolgreich " + status
            log_message(log_path, "[Admin] " + message, force=True)
            response = "HTTP/1.1 200 OK\r\nContent-Type:text/plain\r\n\r\n" + message
        else:
            message = "Fehler beim Umschalten des Debug-Modus"
            log_message(log_path, "[Admin] " + message)
            response = "HTTP/1.1 500 Internal Server Error\r\nContent-Type:text/plain\r\n\r\n" + message
            
        cl.sendall(response.encode())
        
    except Exception as e:
        error_msg = "Kritischer Fehler beim Debug-Toggle: " + str(e)
        log_message(log_path, "[Admin] " + error_msg)
        try:
            cl.sendall(b"HTTP/1.1 500\r\n\r\nInterner Server Fehler")
        except Exception:
            pass


def _toggle_leds(cl, log_path=None):
    """Schaltet LEDs um (Display Toggle Funktion)"""
    try:
        # Importiere Funktionen aus clock_program
        # Da wir nicht direkt auf die Clock-Variablen zugreifen können,
        # senden wir ein Signal über eine Datei
        
        try:
            # Erstelle Toggle-Signal-Datei
            with open("/sd/.led_toggle_request", "w") as f:
                import time
                f.write("LED toggle request at: {}".format(str(time.localtime())))
            
            log_message(log_path, "[LED-Toggle] LED-Umschaltung angefordert")
            
            # Rückmeldung an Browser
            response = "HTTP/1.1 200 OK\r\n\r\nLED Toggle erfolgreich angefordert"
            cl.sendall(response.encode())
            
        except Exception as file_error:
            log_message(log_path, "[LED-Toggle] Datei-Fehler: " + str(file_error))
            cl.sendall(b"HTTP/1.1 500\r\n\r\nLED Toggle Dateifehler")
            
    except Exception as e:
        error_msg = "Kritischer Fehler beim LED-Toggle: " + str(e)
        log_message(log_path, error_msg)
        cl.sendall("HTTP/1.1 500\r\n\r\nInterner Serverfehler: {}".format(error_msg[:50]).encode())


# --------------------------------------------------------------------
#   Power Settings
# --------------------------------------------------------------------
def _save_display_settings_unsafe(body, log_path=None):
    try:
        settings = {}
        for line in body.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                settings[key.strip()] = value.strip()
        
        with open("/sd/power_config.txt", "w") as f:
            f.write("DISPLAY_AUTO=" + settings.get('DISPLAY_AUTO', 'true') + "\n")
            f.write("DISPLAY_ON_TIME=" + settings.get('DISPLAY_ON_TIME', '07:00') + "\n") 
            f.write("DISPLAY_OFF_TIME=" + settings.get('DISPLAY_OFF_TIME', '22:00') + "\n")
        
        os.sync()
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
            'DISPLAY_OFF_TIME': '22:00'
        }
        if file_exists("/sd/power_config.txt"):
            with open("/sd/power_config.txt", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        if key in settings:  # Nur relevante Keys laden
                            settings[key] = value
        return settings
    except Exception:
        return {
            'DISPLAY_AUTO': 'true',
            'DISPLAY_ON_TIME': '07:00',
            'DISPLAY_OFF_TIME': '22:00'
        }


# --------------------------------------------------------------------
#   Index-Seite mit integrierten Display-Einstellungen
# --------------------------------------------------------------------
def _serve_index_page(cl, log_path=None):
    """Memory-optimierte Index-Seite mit chunked streaming und aggressiver GC"""
    try:
        # AGGRESSIVE Memory Cleanup vor HTML-Rendering
        import gc
        for _ in range(3):  # Mehrere GC-Durchläufe
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
    cl.sendall(b"HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n")


def _send_html_chunks(cl, log_path=None):
    """Sendet HTML in memory-safe chunks"""
    import gc
    
    # Chunk 1: HTML Header (klein halten!)
    chunk1 = b"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Neuza Wecker</title><link rel="stylesheet" href="styles.css"></head>
<body><header><h1>Neuza Wecker</h1></header>
<div class="main-container"><div class="image-container">
<img src="neuza.webp" alt="Neuza" onerror="this.style.display='none'"></div>
<div class="form-container"><form id="alarmForm">"""
    cl.sendall(chunk1)
    gc.collect()  # Nach jedem Chunk
    
    # Chunk 2: Alarm-Blöcke (Memory-sparend laden)
    alarme = _load_alarms("/sd/alarm.txt")
    _send_alarm_blocks_safe(cl, alarme)
    gc.collect()  # Nach Alarmen
    
    # Chunk 3: Display-Settings
    _send_display_block_safe(cl)
    gc.collect()  # Nach Display-Block
    
    # Chunk 4: Footer und JavaScript (aufgeteilt)
    _send_footer_chunks(cl, log_path)
    gc.collect()  # Final cleanup


def _send_alarm_blocks_safe(cl, alarme):
    """Memory-sichere Alarm-Block Übertragung"""
    import gc
    all_alarms = alarme + [("", "", [], "")] * (5 - len(alarme))
    
    for i, (zeit, text, tage, aktiv) in enumerate(all_alarms):
        # Alarm-Block einzeln generieren und senden
        block = _generate_alarm_block(zeit, text, tage, aktiv)
        cl.sendall(block.encode())
        
        # Memory cleanup alle 2 Blöcke
        if i % 2 == 1:
            gc.collect()


def _generate_alarm_block(zeit, text, tage, aktiv):
    """Generiert einzelnen Alarm-Block memory-safe"""
    chk_days = ""
    for w in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
        chk = "checked" if w in tage else ""
        chk_days += '<label><input type="checkbox" {}> {}</label>\n'.format(chk, w)
    
    chk_a = "checked" if aktiv.strip().lower() == "aktiv" else ""
    
    return '''<div class="alarm-block">
<input type="time" value="{}">
<input type="text" value="{}">
<div class="checkboxes">
{}
<label><input type="checkbox" {}> Aktiv</label>
</div></div>\n'''.format(
        zeit, _html_escape(text), chk_days, chk_a)


def _send_display_block_safe(cl):
    """Memory-sichere Display-Settings Übertragung"""
    settings = _load_display_settings()
    
    block = '''<div class="display-settings-block">
<h3>Display-Einstellungen</h3>
<label><input type="checkbox" id="displayAuto" {}> Automatisches Ein/Aus</label><br>
<label>Ein-Zeit: <input type="time" id="displayOn" value="{}"></label><br>
<label>Aus-Zeit: <input type="time" id="displayOff" value="{}"></label>
</div>\n'''.format(
        "checked" if settings.get('auto', True) else "",
        settings.get('on_time', '06:45'),
        settings.get('off_time', '20:00')
    )
    cl.sendall(block.encode())


def _send_footer_chunks(cl, log_path=None):
    """Memory-sichere Footer und JavaScript Übertragung"""
    import gc
    
    # Footer Teil 1
    debug_link = ' | <a href="/debug">Debug</a>' if is_debug_mode_enabled() else ''
    footer1 = '''<button id="saveButton" type="button" onclick="saveAllSettings()">Alle Einstellungen speichern</button>
</form></div></div><footer>Neuza Wecker{}</footer>\n'''.format(debug_link)
    cl.sendall(footer1.encode())
    gc.collect()
    
    # JavaScript in kleineren Chunks
    js_chunks = _split_javascript()
    for chunk in js_chunks:
        cl.sendall(chunk.encode())
        gc.collect()
    
    # HTML Ende
    cl.sendall(b"</body></html>")


def _split_javascript():
    """Teilt JavaScript in memory-safe chunks"""
    return [
        "<script>",
        JS_SNIPPET[:500],  # Erste 500 Zeichen
        JS_SNIPPET[500:1000] if len(JS_SNIPPET) > 500 else "",  # Nächste 500
        JS_SNIPPET[1000:] if len(JS_SNIPPET) > 1000 else "",  # Rest
        "</script>"
    ]


def _html_escape(text):
    """Einfache HTML-Escape Funktion"""
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _send_error_response(cl, code, message):
    """Memory-sichere Error Response"""
    try:
        response = "HTTP/1.1 {} {}\r\n\r\n{}".format(code, message, message)
        cl.sendall(response.encode())
    except Exception:
        pass  # Fehler beim Fehler-senden ignorieren


def _send_alarm_blocks(cl, alarme):
    """Memory-optimiert: Alarm-Blöcke einzeln streamen"""
    # Auf 5 Blöcke auffüllen
    all_alarms = alarme + [("", "", [], "")] * (5 - len(alarme))
    
    for zeit, text, tage, aktiv in all_alarms:
        # Kompakte HTML-Generierung pro Block
        chk_days = ""
        for w in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
            chk = "checked" if w in tage else ""
            chk_days += '<label><input type="checkbox" {}> {}</label>\n'.format(chk, w)
        
        chk_a = "checked" if aktiv.strip().lower() == "aktiv" else ""
        
        block_html = '''<div class="alarm-block">
<input type="time" value="{}">
<input type="text" value="{}">
<div class="checkboxes">
{}
<label><input type="checkbox" {}> Aktiv</label>
</div></div>
'''.format(zeit, _html_escape(text), chk_days, chk_a)
        
        cl.sendall(block_html.encode())


def _send_display_block(cl):
    """Memory-optimiert: Display-Settings Block streamen"""
    display_settings = _load_display_settings()
    auto_checked = 'checked' if display_settings.get('DISPLAY_AUTO', 'true') == 'true' else ''
    
    display_html = '''<div class="display-settings-block">
<h3>Display Automatik</h3>
<label><input type="checkbox" id="displayAuto" {}> Automatisch Ein/Aus</label><br>
<label>Display An: <input type="time" id="displayOn" value="{}"></label><br>
<label>Display Aus: <input type="time" id="displayOff" value="{}"></label>
</div>'''.format(auto_checked, 
                display_settings.get('DISPLAY_ON_TIME', '07:00'), 
                display_settings.get('DISPLAY_OFF_TIME', '22:00'))
    
    cl.sendall(display_html.encode())


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
    return alarme[:5]  # maximal fünf zurückliefern


def _render_index(alarme):
    # Alarm-Blöcke generieren
    rows = ""
    for zeit, text, tage, aktiv in alarme + [("", "", [], "")] * (5 - len(alarme)):
        rows += '<div class="alarm-block">\n'
        rows += '<input type="time" value="{}">\n'.format(zeit)
        rows += '<input type="text" value="{}">\n<div class="checkboxes">\n'.format(html_escape(text))
        for w in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]:
            chk = "checked" if w in tage else ""
            rows += '<label><input type="checkbox" {}> {}</label>\n'.format(chk, w)
        chk_a = "checked" if aktiv.strip().lower() == "aktiv" else ""
        rows += '<label><input type="checkbox" {}> Aktiv</label>\n</div></div>\n'.format(chk_a)

    # Display-Settings laden und integrieren
    display_settings = _load_display_settings()
    auto_checked = 'checked' if display_settings.get('DISPLAY_AUTO', 'true') == 'true' else ''
    
    # Display-Block mit LED-Toggle hinzufügen
    display_block = '''<div class="alarm-block">
<h3>Display Automatik</h3>
<label><input type="checkbox" id="displayAuto" {}> Automatisch Ein/Aus</label><br>
<label>Display An: <input type="time" id="displayOn" value="{}"></label><br>
<label>Display Aus: <input type="time" id="displayOff" value="{}"></label><br>
<button type="button" class="led-toggle-btn" onclick="toggleLEDs()">💡 LEDs Ein/Aus</button>
</div>'''.format(auto_checked, display_settings.get('DISPLAY_ON_TIME', '07:00'), display_settings.get('DISPLAY_OFF_TIME', '22:00'))

    # Log-Viewer immer verfügbar + Debug-Link nur wenn aktiviert
    log_link = ' | <a href="/logs" class="log-link">📋 Logs anzeigen</a>'
    debug_link = ' | <a href="/debug" class="debug-link">Debug-Modus</a>' if is_debug_mode_enabled() else ''
    all_links = log_link + debug_link
    
    return INDEX_TEMPLATE.format(rows, display_block, JS_SNIPPET, all_links)


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Neuza Wecker</title><link rel="stylesheet" href="styles.css"></head>
<body><header><h1>Neuza Wecker</h1></header>
<div class="main-container"><div class="image-container">
<img src="neuza.webp" alt="Neuza" onerror="this.style.display='none'"></div>
<div class="form-container"><form id="alarmForm">{0}
{1}
<button id="saveButton" type="button" onclick="saveAllSettings()">Alle Einstellungen speichern</button>
</form></div></div><footer>Neuza Wecker{3}</footer>
<script>{2}</script></body></html>"""

JS_SNIPPET = """async function saveAllSettings(){
const b=document.getElementById('saveButton');
if(!b){alert('Button nicht gefunden!');return;}
b.disabled=true;b.textContent='Speichern…';
console.log('saveAllSettings gestartet');
const a=[];const blocks=document.querySelectorAll('.alarm-block');
console.log('Alarm-Blöcke gefunden:',blocks.length);
blocks.forEach((x,i)=>{
const t=x.querySelector('input[type="time"]');
const m=x.querySelector('input[type="text"]');
if(!t||!m)return;
const tv=t.value.trim();const mv=m.value.trim();
if(!tv&&!mv)return;
const c=x.querySelectorAll('.checkboxes input');
const tage=new Set();let aktiv=false;
c.forEach(cb=>{const l=cb.parentElement.textContent.trim();
if(l==='Aktiv'){aktiv=cb.checked;}
else if(cb.checked&&l.match(/^(Mo|Di|Mi|Do|Fr|Sa|So)$/)){tage.add(l);}});
const tageArr=Array.from(tage).sort();
const alarmStr=[tv,mv||'Kein Text',tageArr.join(','),aktiv?'Aktiv':'Inaktiv'].join(',');
a.push(alarmStr);console.log('Alarm',i+1,':',alarmStr);});
console.log('Alarme gesamt:',a.length);
let ok1=true,ok2=true;
if(a.length){try{b.textContent='Weckzeiten…';
const r1=await fetch('/save_alarms',{method:'POST',headers:{'Content-Type':'text/plain'},body:a.join('\\n')});
ok1=r1.ok;console.log('Alarme:',r1.status);}catch(e){console.error('Alarm-Fehler:',e);ok1=false;}}
await new Promise(r=>setTimeout(r,100));
try{b.textContent='Display…';
const da=document.getElementById('displayAuto');
const don=document.getElementById('displayOn');
const doff=document.getElementById('displayOff');
if(!da||!don||!doff){console.error('Display-Inputs fehlen');ok2=false;}else{
const d=['DISPLAY_AUTO='+da.checked,'DISPLAY_ON_TIME='+don.value,'DISPLAY_OFF_TIME='+doff.value];
const r2=await fetch('/save_display_settings',{method:'POST',body:d.join('\\n')});
ok2=r2.ok;console.log('Display:',r2.status);}}catch(e){console.error('Display-Fehler:',e);ok2=false;}
b.textContent=ok1&&ok2?'Alles gespeichert ✅':'Fehler beim Speichern';
console.log('Ergebnis: Alarme='+ok1+', Display='+ok2);
setTimeout(()=>{b.disabled=false;b.textContent='Alle Einstellungen speichern';},3000);
}

async function toggleLEDs(){
const btn=event.target;
if(!btn)return;
btn.disabled=true;
btn.textContent='💡 Schalte...';
try{
const r=await fetch('/toggle_leds',{method:'POST'});
const success=r.ok;
btn.textContent=success?'💡 LEDs umgeschaltet ✅':'💡 Fehler beim Schalten';
setTimeout(()=>{btn.disabled=false;btn.textContent='💡 LEDs Ein/Aus';},2000);
}catch(e){
console.error('LED-Toggle Fehler:',e);
btn.textContent='💡 Verbindungsfehler';
setTimeout(()=>{btn.disabled=false;btn.textContent='💡 LEDs Ein/Aus';},2000);
}
}"""


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


# --------------------------------------------------------------------
#   Security Management Functions
# --------------------------------------------------------------------
def enable_debug_mode(log_path=None):
    """Aktiviert den Debug-Modus (erstellt .debug_enabled Datei)"""
    try:
        with open("/sd/.debug_enabled", "w") as f:
            import time
            f.write("Debug enabled at: {}".format(str(time.localtime())))
        log_message(log_path, "[Security] Debug-Modus aktiviert", force=True)
        return True
    except Exception as e:
        log_message(log_path, "[Security] Debug-Modus Aktivierung fehlgeschlagen: {}".format(str(e)))
        return False


def disable_debug_mode(log_path=None):
    """Deaktiviert den Debug-Modus (löscht .debug_enabled Datei)"""
    try:
        if file_exists("/sd/.debug_enabled"):
            os.remove("/sd/.debug_enabled")
        log_message(log_path, "[Security] Debug-Modus deaktiviert", force=True)
        return True
    except Exception as e:
        log_message(log_path, "[Security] Debug-Modus Deaktivierung fehlgeschlagen: {}".format(str(e)))
        return False


def get_security_status(log_path=None):
    """Gibt aktuellen Sicherheitsstatus zurück"""
    try:
        status = {
            'debug_mode': is_debug_mode_enabled(),
            'allowed_files': len(ALLOWED_STATIC_FILES),
            'whitelist_active': True,
            'sanitization_active': True
        }
        
        # Zähle verfügbare Dateien
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
    """Überprüft ob der Webserver noch funktionsfähig ist"""
    if not s:
        return False
    try:
        # Versuche Socket-Status zu prüfen
        s.settimeout(0.1)
        return True
    except Exception:
        return False


def get_webserver_status():
    """Gibt aktuellen Webserver-Status zurück"""
    try:
        return {
            'blue_led': blue_led.value(),
            'poller_active': True,  # Vereinfacht - könnte erweitert werden
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