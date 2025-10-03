# power_management.py
import time
import os
from log_utils import log_message


_DEFAULT_SETTINGS = {
    'DISPLAY_AUTO': 'true',
    'DISPLAY_ON_TIME': '07:00',
    'DISPLAY_OFF_TIME': '22:00',
    'BRIGHTNESS_DAY': '64',
    'BRIGHTNESS_NIGHT': '16',
    'LED_POWER_MODE': 'normal',
    'VOLUME_PERCENT': '50',
    'DISPLAY_STATE': 'on',  # zentraler Schalter: 'on'|'off'
}

_VALID_LED_POWER_MODES = ('normal', 'boost')


def _clamp_volume(value, fallback=None):
    if fallback is None:
        fallback = int(_DEFAULT_SETTINGS['VOLUME_PERCENT'])
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return fallback

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
            for key, default_value in _DEFAULT_SETTINGS.items():
                settings.setdefault(key, default_value)
            _power_settings = settings
            _last_settings_load = now
        else:
            # Default Settings
            _power_settings = dict(_DEFAULT_SETTINGS)
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
    ueberprueft basierend auf den Einstellungen, ob das Display an sein soll.
    Gibt (should_be_on: bool, brightness: int) zurueck.
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
        # ueber Mitternacht (on > off, z.B. 22:00 bis 07:00)
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


def get_brightness_for_state(display_on, log_path=None):
    """Gibt die konfigurierte Helligkeit fuer den angegebenen Display-Zustand zurueck."""
    try:
        settings = _load_settings()
        if display_on:
            return int(settings.get('BRIGHTNESS_DAY', '64'))
        return int(settings.get('BRIGHTNESS_NIGHT', '16'))
    except Exception as e:
        log_message(log_path, "[Power Management] Helligkeit Fallback: {}".format(str(e)))
        return 64 if display_on else 16


def is_display_manually_toggled():
    """Prueft ob Display manuell umgeschaltet wurde (fuer Menue-Toggle)"""
    return True  # Fuer jetzt immer erlauben


def get_led_power_mode(log_path=None):
    """Gibt den aktuellen LED Power Modus ('normal' oder 'boost') zurueck."""
    try:
        settings = _load_settings()
        mode = settings.get('LED_POWER_MODE', _DEFAULT_SETTINGS['LED_POWER_MODE'])
        if mode not in _VALID_LED_POWER_MODES:
            return _DEFAULT_SETTINGS['LED_POWER_MODE']
        return mode
    except Exception as e:
        log_message(log_path, "[Power Settings] LED Mode Fallback: {}".format(str(e)))
        return _DEFAULT_SETTINGS['LED_POWER_MODE']


def set_led_power_mode(mode, log_path=None):
    """Setzt den LED Power Modus in der power_config.txt. Erlaubte Werte: 'normal', 'boost'."""
    try:
        normalized = (mode or '').strip().lower()
        if normalized not in _VALID_LED_POWER_MODES:
            raise ValueError("Ungueltiger LED Power Modus: {}".format(mode))

        settings = {}
        try:
            with open("/sd/power_config.txt", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        settings[key] = value.strip()
        except OSError:
            settings = {}

        for key, default_value in _DEFAULT_SETTINGS.items():
            settings.setdefault(key, default_value)

        settings.pop('VOLUME_DEFAULT', None)
        settings.pop('VOLUME_NIGHT', None)

        settings['LED_POWER_MODE'] = normalized

        order = [
            'DISPLAY_AUTO',
            'DISPLAY_ON_TIME',
            'DISPLAY_OFF_TIME',
            'BRIGHTNESS_DAY',
            'BRIGHTNESS_NIGHT',
            'LED_POWER_MODE',
            'VOLUME_PERCENT',
            'DISPLAY_STATE',
        ]

        tmp_path = "/sd/power_config.tmp"
        with open(tmp_path, "w") as f:
            for key in order:
                if key in settings:
                    f.write("{}={}\n".format(key, settings[key]))
            for key, value in settings.items():
                if key not in order:
                    f.write("{}={}\n".format(key, value))

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

        try:
            os.sync()
        except Exception:
            pass

        reload_settings()
        return True
    except Exception as e:
        log_message(log_path, "[Power Settings] LED Mode Schreiben Fehler: {}".format(str(e)))
        return False


def get_volume(log_path=None):
    """Gibt die konfigurierte Lautstaerke in Prozent zurueck."""
    try:
        settings = _load_settings()
        if 'VOLUME_PERCENT' not in settings and 'VOLUME_DEFAULT' in settings:
            # Abwärtskompatibilität: alte Configs mit VOLUME_DEFAULT übernehmen
            settings['VOLUME_PERCENT'] = settings['VOLUME_DEFAULT']
        volume = _clamp_volume(settings.get('VOLUME_PERCENT', _DEFAULT_SETTINGS['VOLUME_PERCENT']))
        return volume
    except Exception as e:
        log_message(log_path, "[Power Settings] Volume Fallback: {}".format(str(e)))
        return int(_DEFAULT_SETTINGS['VOLUME_PERCENT'])


def set_volume(volume, log_path=None):
    """Speichert die Lautstaerke in power_config.txt."""
    try:
        clamped = str(_clamp_volume(volume))

        settings = {}
        try:
            with open("/sd/power_config.txt", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        settings[key] = value.strip()
        except OSError:
            settings = {}

        for key, default_value in _DEFAULT_SETTINGS.items():
            settings.setdefault(key, default_value)

        # Altes Feld aufraeumen, falls vorhanden
        if 'VOLUME_DEFAULT' in settings:
            settings.pop('VOLUME_DEFAULT', None)
        if 'VOLUME_NIGHT' in settings:
            settings.pop('VOLUME_NIGHT', None)

        if settings.get('VOLUME_PERCENT') == clamped:
            return True

        settings['VOLUME_PERCENT'] = clamped

        order = [
            'DISPLAY_AUTO',
            'DISPLAY_ON_TIME',
            'DISPLAY_OFF_TIME',
            'BRIGHTNESS_DAY',
            'BRIGHTNESS_NIGHT',
            'LED_POWER_MODE',
            'VOLUME_PERCENT',
            'DISPLAY_STATE',
        ]

        tmp_path = "/sd/power_config.tmp"
        with open(tmp_path, "w") as f:
            for key in order:
                if key in settings:
                    f.write("{}={}\n".format(key, settings[key]))
            for key, value in settings.items():
                if key not in order:
                    f.write("{}={}\n".format(key, value))

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

        try:
            os.sync()
        except Exception:
            pass

        reload_settings()
        log_message(log_path, "[Power Settings] Volume gespeichert: {}%.".format(clamped))
        return True
    except Exception as e:
        log_message(log_path, "[Power Settings] Volume Schreiben Fehler: {}".format(str(e)))
        return False


def reload_settings():
    """Erzwingt Neuladen der Einstellungen"""
    _load_settings(force_reload=True)


def get_display_schedule(log_path=None):
    """Liest den Display-Zeitplan (Auto, Ein-/Aus-Zeit) aus der power_config.txt.
    Rueckgabe: { 'auto': bool, 'on_time': 'HH:MM', 'off_time': 'HH:MM' }
    """
    try:
        settings = _load_settings()
        return {
            'auto': settings.get('DISPLAY_AUTO', 'true') == 'true',
            'on_time': settings.get('DISPLAY_ON_TIME', _DEFAULT_SETTINGS['DISPLAY_ON_TIME']),
            'off_time': settings.get('DISPLAY_OFF_TIME', _DEFAULT_SETTINGS['DISPLAY_OFF_TIME']),
        }
    except Exception as e:
        log_message(log_path, "[Power Settings] Schedule Fallback: {}".format(str(e)))
        return {
            'auto': True,
            'on_time': _DEFAULT_SETTINGS['DISPLAY_ON_TIME'],
            'off_time': _DEFAULT_SETTINGS['DISPLAY_OFF_TIME'],
        }


def get_display_state(log_path=None):
    """Liest den zentralen Display-Status 'on'|'off' aus power_config.txt."""
    try:
        settings = _load_settings()
        state = (settings.get('DISPLAY_STATE', _DEFAULT_SETTINGS['DISPLAY_STATE']) or 'on').strip().lower()
        return 'on' if state == 'on' else 'off'
    except Exception as e:
        log_message(log_path, "[Power Settings] Display-State Fallback: {}".format(str(e)))
        return _DEFAULT_SETTINGS['DISPLAY_STATE']


def set_display_state(state, log_path=None):
    """Schreibt den zentralen Display-Status in power_config.txt. state: 'on'|'off'"""
    try:
        normalized = 'on' if str(state).strip().lower() == 'on' else 'off'

        settings = {}
        try:
            with open("/sd/power_config.txt", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        settings[key] = value.strip()
        except OSError:
            settings = {}

        for key, default_value in _DEFAULT_SETTINGS.items():
            settings.setdefault(key, default_value)

        settings['DISPLAY_STATE'] = normalized

        order = [
            'DISPLAY_AUTO',
            'DISPLAY_ON_TIME',
            'DISPLAY_OFF_TIME',
            'BRIGHTNESS_DAY',
            'BRIGHTNESS_NIGHT',
            'LED_POWER_MODE',
            'VOLUME_PERCENT',
            'DISPLAY_STATE',
        ]

        tmp_path = "/sd/power_config.tmp"
        with open(tmp_path, "w") as f:
            for key in order:
                if key in settings:
                    f.write("{}={}\n".format(key, settings[key]))
            for key, value in settings.items():
                if key not in order:
                    f.write("{}={}\n".format(key, value))

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

        try:
            os.sync()
        except Exception:
            pass

        reload_settings()
        log_message(log_path, "[Power Settings] Display-State gespeichert: {}".format(normalized))
        return True
    except Exception as e:
        log_message(log_path, "[Power Settings] Display-State Schreiben Fehler: {}".format(str(e)))
        return False