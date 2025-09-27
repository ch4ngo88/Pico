# led.py
import time
from log_utils import log_message, log_important
from sound_config import paus

try:
    from neopixel import myNeopixel

    NUM_LEDS = 8
    _PIN = 28
    led_kranz: myNeopixel | None = myNeopixel(NUM_LEDS, _PIN)
    leds_ok = True

except Exception as e:
    log_message(None, "[LED Init Fehler] {}".format(str(e)))
    leds_ok = False
    led_kranz = None


# --------------------------------------------------------------------
#   Hilfsfunktionen
# --------------------------------------------------------------------
def _safe_fill(np_obj, r, g, b):
    """Kompatibel zu fill(r,g,b) UND fill((r,g,b))."""
    try:  # eigener Wrapper
        np_obj.fill(r, g, b)
    except TypeError:
        np_obj.fill((r, g, b))


def _safe_set(np_obj, idx, r, g, b):
    try:
        np_obj.set_pixel(idx, r, g, b)
    except AttributeError:
        np_obj[idx] = (r, g, b)


def _is_ready(np_obj, log_path=None):
    if not leds_ok or not np_obj:
        log_message(log_path, "[LED] Aktion uebersprungen – LEDs nicht verfuegbar.")
        return False
    return True


def wheel(pos):
    """0-255 → RGB Regenbogen-Rad."""
    pos &= 255
    if pos < 85:
        return 255 - pos * 3, pos * 3, 0
    if pos < 170:
        pos -= 85
        return 0, 255 - pos * 3, pos * 3
    pos -= 170
    return pos * 3, 0, 255 - pos * 3


# Fallback für Wrapper ohne rotate_right
def _rotate_right(np_obj, steps=1):
    try:
        np_obj.rotate_right(steps)
    except AttributeError:
        buf = [np_obj[i] for i in range(NUM_LEDS)]
        for i in range(NUM_LEDS):
            np_obj[i] = buf[(i - steps) % NUM_LEDS]


# --------------------------------------------------------------------
#   Animationen
# --------------------------------------------------------------------
def led_kranz_animation(np=led_kranz, log_path=None):
    if not _is_ready(np, log_path):
        return
    try:
        # --- Rainbow Wipe ---
        for cycle in range(50):
            for i in range(NUM_LEDS):
                c = wheel((i * 256 // NUM_LEDS + cycle * 5))
                _safe_set(np, i, *c)
            np.show()
            time.sleep(0.02)
            _rotate_right(np)

        # --- Chase Pulse ---
        for cycle in range(3):
            for i in range(NUM_LEDS):
                _safe_fill(np, 0, 0, 0)
                _safe_set(np, i, *wheel((i * 256 // NUM_LEDS + cycle * 20)))
                np.show()
                time.sleep(0.05)
            time.sleep(0.1)

        # --- Fading Tail ---
        for cycle in range(50):
            for i in range(NUM_LEDS):
                r, g, b = wheel((i * 256 // NUM_LEDS + cycle * 10))
                brightness = 1 - (i / NUM_LEDS)
                _safe_set(
                    np, i, int(r * brightness), int(g * brightness), int(b * brightness)
                )
            np.show()
            time.sleep(0.01)
            _rotate_right(np)

        # --- Flashing Green/Red ---
        for _ in range(3):
            _safe_fill(np, 255, 0, 0)
            np.show()
            time.sleep(0.05)
            _safe_fill(np, 0, 255, 0)
            np.show()
            time.sleep(0.05)

        # --- Red Alert Blink ---
        for _ in range(10):
            _safe_fill(np, 255, 0, 0)
            np.show()
            time.sleep(0.03)
            _safe_fill(np, 0, 0, 0)
            np.show()
            time.sleep(0.03)

    except Exception as e:
        log_message(log_path, "[LED] Fehler bei Animation: {}".format(str(e)))


# --------------------------------------------------------------------
#   Status-Funktionen
# --------------------------------------------------------------------
def led_kranz_einschalten(np=led_kranz, log_path=None):
    if not _is_ready(np, log_path):
        return
    _safe_fill(np, 0, 255, 0)
    np.show()
    if log_path:
        log_message(log_path, "[LED] Alle LEDs gruen eingeschaltet.")

def led_bleibt_rot(np=led_kranz, log_path=None):
    if not _is_ready(np, log_path):
        return
    _safe_fill(np, 255, 0, 0)
    np.show()


def led_rosa(np=led_kranz, log_path=None):
    if not _is_ready(np, log_path):
        return
    _safe_fill(np, 255, 20, 147)
    np.show()


# --------------------------------------------------------------------
#   Blink- & Countdown-Funktionen
# --------------------------------------------------------------------
def led_und_buzzer_blinken_rot(np=led_kranz, volume_percent=50, log_path=None):
    if not _is_ready(np, log_path):
        return
    for _ in range(3):
        _safe_fill(np, 255, 0, 0)
        np.show()
        time.sleep(0.5)
        _safe_fill(np, 0, 0, 0)
        np.show()
        time.sleep(0.5)
    paus(volume_percent)


def led_und_buzzer_blinken_und_aus(
    np=led_kranz, volume_percent=50, nur_aus=True, log_path=None
):
    if not _is_ready(np, log_path):
        return
    for _ in range(3):
        if not nur_aus:
            _safe_fill(np, 255, 0, 0)
            np.show()
            time.sleep(0.5)
        _safe_fill(np, 0, 0, 0)
        np.show()
        time.sleep(0.5)
    if not nur_aus:
        paus(volume_percent)


def set_yellow_leds(np=led_kranz, count=0, log_path=None):
    if not _is_ready(np, log_path):
        return
    count = min(max(0, count), NUM_LEDS)
    _safe_fill(np, 0, 0, 0)
    for i in range(count):
        _safe_set(np, i, 255, 255, 0)
    np.show()


# --------------------------------------------------------------------
#   Dispatcher
# --------------------------------------------------------------------
def set_leds_based_on_mode(np, mode, first_red, volume_percent, log_path=None):
    if not _is_ready(np, log_path):
        return first_red

    # Nur wichtige Modus-Änderungen loggen
    if log_path and mode in ["red_blinking", "alarm_mode"]:
        log_important(log_path, "[LED] Wichtiger Modus: {}".format(mode))

    if mode == "green":
        led_kranz_einschalten(np)
    elif mode == "red_blinking":
        first_red = led_und_buzzer_blinken_rot(np, volume_percent)
    elif mode == "red_solid":
        led_bleibt_rot(np)
    elif mode == "off":
        led_und_buzzer_blinken_und_aus(np, volume_percent)

    return first_red
