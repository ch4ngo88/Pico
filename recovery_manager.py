# recovery_manager.py
import time
from machine import reset, WDT
from log_utils import log_important

# --------------------------------------------------------------------
# Recovery State
# --------------------------------------------------------------------
_last_activity = 0
_recovery_active = False
_wdt = None
_WATCHDOG_TIMEOUT = 8000   # 8 Sekunden (Maximum für Pico - 8388ms Limit)


# --------------------------------------------------------------------
# Watchdog Management  
# --------------------------------------------------------------------
def init_recovery_system(log_path=None):
    """Initialisiert das Recovery-System mit Watchdog"""
    global _wdt, _last_activity
    try:
        _wdt = WDT(timeout=_WATCHDOG_TIMEOUT)
        _last_activity = time.time()
        log_important(log_path, "[Recovery] Watchdog initialisiert (8s - Pico Maximum)")
        return True
    except Exception as e:
        log_important(log_path, "[Recovery] Watchdog Fehler: " + str(e))
        return False


def feed_watchdog(log_path=None):
    """Füttert den Watchdog - zeigt dass das System läuft"""
    global _wdt, _last_activity
    try:
        if _wdt:
            _wdt.feed()
        _last_activity = time.time()
    except Exception as e:
        log_important(log_path, "[Recovery] Watchdog Feed Fehler: " + str(e))


def check_system_health(log_path=None):
    """
    Überprüft die Systemgesundheit.
    Führt sanften Reset durch wenn nötig.
    """
    global _last_activity, _recovery_active
    
    if _recovery_active:
        return True
        
    try:
        now = time.time()
        
        # Mehr als 5 Minuten keine Aktivität? 
        if now - _last_activity > 300:
            log_important(log_path, "[Recovery] System scheint zu hängen - sanfter Reset")
            _recovery_active = True
            
            # Kurze Pause dann Reset
            time.sleep(2)
            reset()
            
        return True
        
    except Exception as e:
        log_important(log_path, "[Recovery] Health Check Fehler: " + str(e))
        return False


def emergency_recovery(log_path=None):
    """Notfall-Recovery wenn alles andere fehlschlägt"""
    try:
        log_important(log_path, "[Recovery] NOTFALL-RECOVERY ausgeführt")
        time.sleep(1)
        reset()
    except Exception:
        # Wenn selbst das fehlschlägt, können wir nichts mehr tun
        pass


def activity_heartbeat():
    """Aktualisiert die letzte Aktivitätszeit"""
    global _last_activity
    _last_activity = time.time()