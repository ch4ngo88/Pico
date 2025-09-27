# power_management.py
import time
import os
from log_utils import log_message

# --------------------------------------------------------------------
# Power Management State
# --------------------------------------------------------------------
_power_settings = {}
_last_settings_load = 0
_SETTINGS_CACHE_TIME = 300  # 5 Minuten Cache


# --------------------------------------------------------------------
# Settings laden
# --------------------------------------------------------------------
def _load_settings(force_reload=False):
    global _power_settings, _last_settings_load
    
    now = time.time()
    if not force_reload and now - _last_settings_load < _SETTINGS_CACHE_TIME:
        return _power_settings
    
    try:
        try:
            os.stat("/sd/power_config.txt")
            power_config_exists = True
        except OSError:
            power_config_exists = False
        
        if power_config_exists:
            settings = {}
            with open("/sd/power_config.txt", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        settings[key] = value.lower()
            _power_settings = settings
            _last_settings_load = now
        else:
            # Default Settings
            _power_settings = {
                'DISPLAY_AUTO': 'true',
                'DISPLAY_ON_TIME': '07:00',
                'DISPLAY_OFF_TIME': '22:00',
                'BRIGHTNESS_DAY': '64',
                'BRIGHTNESS_NIGHT': '16'
            }
    except Exception as e:
        log_message(None, "[Power Settings] Fehler beim Laden: {}".format(str(e)))
        _power_settings = {}
    
    return _power_settings


# --------------------------------------------------------------------
# Zeit-String zu Minuten
# --------------------------------------------------------------------
def _time_to_minutes(time_str):
    """Konvertiert 'HH:MM' zu Minuten seit Mitternacht"""
    try:
        hour, minute = map(int, time_str.split(':'))
        return hour * 60 + minute
    except Exception:
        return 0


# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------
def should_display_be_on(current_hour, current_minute, log_path=None):
    """
    Überprüft basierend auf den Einstellungen, ob das Display an sein soll.
    Gibt (should_be_on: bool, brightness: int) zurück.
    """
    try:
        settings = _load_settings()
        
        # Wenn Auto-Mode deaktiviert, immer an
        if settings.get('DISPLAY_AUTO', 'true') != 'true':
            return True, int(settings.get('BRIGHTNESS_DAY', '64'))
        
        current_minutes = current_hour * 60 + current_minute
        on_minutes = _time_to_minutes(settings.get('DISPLAY_ON_TIME', '07:00'))
        off_minutes = _time_to_minutes(settings.get('DISPLAY_OFF_TIME', '22:00'))
        
        # Normale Zeit (on < off)
        if on_minutes < off_minutes:
            is_on_time = on_minutes <= current_minutes < off_minutes
        # Über Mitternacht (on > off, z.B. 22:00 bis 07:00)
        else:
            is_on_time = current_minutes >= on_minutes or current_minutes < off_minutes
        
        if is_on_time:
            brightness = int(settings.get('BRIGHTNESS_DAY', '64'))
        else:
            brightness = int(settings.get('BRIGHTNESS_NIGHT', '16'))
            
        return is_on_time, brightness
        
    except Exception as e:
        log_message(log_path, "[Power Management] Fehler: {}".format(str(e)))
        return True, 64  # Fallback: immer an


def is_display_manually_toggled():
    """Prüft ob Display manuell umgeschaltet wurde (für Menü-Toggle)"""
    return True  # Für jetzt immer erlauben


def reload_settings():
    """Erzwingt Neuladen der Einstellungen"""
    _load_settings(force_reload=True)