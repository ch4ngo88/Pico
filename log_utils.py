# log_utils.py
import os
import time

# --------------------------------------------------------------------
#   Parameter
# --------------------------------------------------------------------
_MAX_SIZE = 512 * 1024  # 512 kB pro Logfile
_LOG_NAME = "debug_log.txt"


# --------------------------------------------------------------------
#   Helfer
# --------------------------------------------------------------------
def _timestamp():
    try:
        t = time.localtime()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4])
    except Exception:
        return "0000-00-00 00:00"


def _rotate(log_path):
    """Benamst alte Datei zu .1, wenn sie zu gross wird."""
    try:
        if os.stat(log_path)[6] > _MAX_SIZE:
            old = log_path + ".1"
            if old in os.listdir("/sd"):
                os.remove(old)
            os.rename(log_path, old)
    except OSError:
        # stat/rename kann fehlschlagen, z. B. wenn SD nicht gemountet
        pass


# --------------------------------------------------------------------
#   Public API
# --------------------------------------------------------------------
def init_logfile(sd_path="/sd", log_filename=_LOG_NAME):
    """
    Erstellt Log-Verzeichnis und -Datei bei Bedarf.
    Gibt den vollstaendigen Pfad zurueck oder None, wenn Schreibfehler.
    """
    try:
        # SD-Ordner existiert evtl. noch nicht
        if sd_path not in ("/", "") and sd_path.strip("/") not in os.listdir("/"):
            os.mkdir(sd_path)
        log_path = "{}/{}".format(sd_path, log_filename)
        if log_filename not in os.listdir(sd_path):
            with open(log_path, "w") as f:
                f.write("")  # leere Datei
                f.flush()
                os.sync()
        return log_path
    except Exception as e:
        print("{} - Fehler beim Initialisieren des Logfiles: {}".format(_timestamp(), str(e)))
        return None


# Anti-Spam: Wiederholte Nachrichten unterdruecken
_last_messages = {}
_MAX_REPEAT_INTERVAL = 3600  # 1 Stunde zwischen gleichen Nachrichten

# Kategorien fuer intelligenteres Logging
LOG_CATEGORIES = {
    'STARTUP': True,    # System-Start, wichtige Initialisierung
    'ERROR': True,      # Alle Fehler
    'ALARM': True,      # Alarm-Events
    'CONFIG': True,     # Konfiguration geaendert
    'STATUS': False,    # Regelmaessige Status-Updates (meist spam)
    'DEBUG': False,     # Debug-Informationen
    'WEBSERVER': False, # Normale Web-Requests
    'SYSTEM': False     # Routine System-Checks
}


def log_message(log_path, message, force=False, category=None):
    """
    Schreibt Nachricht in Logfile oder (Fallback) auf die Konsole.
    Rotiert Datei automatisch, flush + sync nach jedem Write.
    Anti-Spam: Gleiche Nachrichten nur alle 60 Min.
    category: Optional fuer intelligente Filterung
    """
    global _last_messages
    
    # Kategorie-basierte Filterung
    if category and not force:
        if category in LOG_CATEGORIES and not LOG_CATEGORIES[category]:
            return  # Diese Kategorie ist deaktiviert
    
    # Anti-Spam Check (ausser bei force=True)
    if not force:
        now = time.time()
        if message in _last_messages:
            if now - _last_messages[message] < _MAX_REPEAT_INTERVAL:
                return  # Nachricht unterdrueckt
        _last_messages[message] = now
        
        # Cache begrenzen mit LRU-Logik (älteste 5 Einträge entfernen bei Überlauf)
        if len(_last_messages) > 20:
            # Sortiere nach Timestamp und entferne älteste 5
            try:
                sorted_items = sorted(_last_messages.items(), key=lambda x: x[1])
                for msg, _ in sorted_items[:5]:
                    del _last_messages[msg]
            except Exception:
                # Fallback: Einfach Cache clearen
                _last_messages.clear()
        
        # Original Code folgt:
        if False:  # Deaktiviert, da LRU-Logik oben
            oldest_key = min(_last_messages.keys(), key=lambda k: _last_messages[k])
            del _last_messages[oldest_key]
    
    time_str = _timestamp()
    full = "{} - {}".format(time_str, message)

    # --- Logfile vorhanden? ---
    if log_path:
        try:
            _rotate(log_path)  # ggf. Archiv
            with open(log_path, "a") as f:
                f.write(full + "\n")
                f.flush()
                os.sync()
            return
        except Exception as e:
            print("⚠️  Schreiben in Logdatei fehlgeschlagen:", e)

    # --- Fallback Konsole ---
    print(full)


# --------------------------------------------------------------------
#   Convenience-Wrapper
# --------------------------------------------------------------------
def error(log_path, context, err):
    """Einheitliche Fehler-Zeile in except-Bloecken."""
    log_message(log_path, "[{}] {}".format(context, str(err)))


def debug(log_path, message, enabled=True):
    """Gefilterte Debug-Ausgabe."""
    if enabled:
        log_message(log_path, "[DEBUG] {}".format(message))


def log_important(log_path, message):
    """Wichtige Logs die nicht gefiltert werden (force=True)"""
    log_message(log_path, message, force=True)


def log_once_per_day(log_path, message, day):
    """Loggt eine Nachricht nur einmal pro Tag"""
    key = "daily_{}_{}".format(day, hash(message) % 1000)
    global _last_messages
    if key not in _last_messages:
        _last_messages[key] = time.time()
        log_message(log_path, message, force=True)


def log_startup(log_path, message):
    """Fuer System-Start relevante Logs"""
    log_message(log_path, "[STARTUP] {}".format(message), force=True, category='STARTUP')


def log_config_change(log_path, message):
    """Fuer Konfigurationsaenderungen"""
    log_message(log_path, "[CONFIG] {}".format(message), force=True, category='CONFIG')


def log_system_status(log_path, message):
    """Fuer regelmaessige System-Status (gefiltert)"""
    log_message(log_path, "[STATUS] {}".format(message), category='STATUS')


def log_alarm_event(log_path, message):
    """Fuer Alarm-relevante Events (immer loggen)"""
    log_message(log_path, "[ALARM] {}".format(message), force=True, category='ALARM')
