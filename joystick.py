# joystick.py
from machine import ADC, Pin
import utime

# -------------------------------------------------------------------
#   Hardware-Pins
# -------------------------------------------------------------------
_VRX_PIN = 26  # GP26  ADC0
_VRY_PIN = 27  # GP27  ADC1
_SW_PIN = 22  # Joystick-Button

_vrx = ADC(_VRX_PIN)
_vry = ADC(_VRY_PIN)
_sw = Pin(_SW_PIN, Pin.IN, Pin.PULL_UP)


# -------------------------------------------------------------------
#   Einmalige Mittelwert-Kalibrierung
# -------------------------------------------------------------------
def _measure_center(samples=100):
    s_x = s_y = 0
    for _ in range(samples):
        s_x += _vrx.read_u16()
        s_y += _vry.read_u16()
        utime.sleep_us(200)  # ≈5 kHz – nicht blockierend
    return s_x // samples, s_y // samples


_CENTER_X, _CENTER_Y = _measure_center()

# adaptiver Schwellenwert (mind. 6000 ≈ 9.2 %)
_THRESHOLD = max(6000, int(0.05 * 65535))


# -------------------------------------------------------------------
#   Debounce-State
# -------------------------------------------------------------------
_last_sw_state = 1  # Pull-up → Ruhe = High
_last_sw_change = utime.ticks_ms()
_DEBOUNCE_MS = 10


# -------------------------------------------------------------------
#   Public API
# -------------------------------------------------------------------
def get_joystick_direction():
    """
    Gibt 'left', 'right', 'up', 'down', 'press' oder None zurück.
    Robuste Version mit Fehlerbehandlung und Plausibilitätsprüfung.
    """
    global _last_sw_state, _last_sw_change

    try:
        # ---------- Taster zuerst (sonst Prellen + Kipp-Fehler) ----------
        sw_now = _sw.value()
        if sw_now != _last_sw_state:
            _last_sw_change = utime.ticks_ms()
            _last_sw_state = sw_now
        else:
            if (
                sw_now == 0
                and utime.ticks_diff(utime.ticks_ms(), _last_sw_change) > _DEBOUNCE_MS
            ):
                return "press"

        # ---------- Achsen mit Robustheit ----------
        try:
            x = _vrx.read_u16()
            y = _vry.read_u16()
            
            # Plausibilitätsprüfung (ADC sollte 0-65535 sein)
            if not (0 <= x <= 65535 and 0 <= y <= 65535):
                return None
                
        except Exception:
            # ADC-Lesefehler - ignorieren
            return None

        dx = x - _CENTER_X
        dy = y - _CENTER_Y

        # Priorität: größere Abweichung gewinnt
        if abs(dx) > _THRESHOLD and abs(dx) > abs(dy):
            return "left" if dx < 0 else "right"
        if abs(dy) > _THRESHOLD:
            return "up" if dy < 0 else "down"

        return None
        
    except Exception:
        # Kompletter Joystick-Ausfall - nicht crashen
        return None
