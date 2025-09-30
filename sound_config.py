# sound_config.py
from machine import PWM, Pin
import utime
from joystick import get_joystick_direction
from log_utils import log_message
from recovery_manager import feed_watchdog

# --------------------------------------------------------------------
#   Hardware-Setup
# --------------------------------------------------------------------
_speaker = PWM(Pin(16, Pin.OUT))
_speaker.duty_u16(0)  # vermeiden von Einschalt-Knack

alarm_flag = True  # globales Flag (extern steuerbar)
_last_freq = 0  # Merkt aktuellen PWM-Frequenz

# --------------------------------------------------------------------
#   interne Helfer
# --------------------------------------------------------------------
_MIN_FREQ = 100
_MAX_FREQ = 5000


def _set_freq(freq):
    """Frequenz nur updaten, wenn sie sich aendert."""
    global _last_freq
    if freq != _last_freq:
        _speaker.freq(freq)
        _last_freq = freq


def _ramp_duty(target, step=512):
    """Sanfte Rampe, damit es nicht knackt."""
    cur = _speaker.duty_u16()
    if target > cur:
        rng = range(cur, target + 1, step)
    else:
        rng = range(cur, target - 1, -step)
    for d in rng:
        _speaker.duty_u16(d)
        utime.sleep_us(200)
def _feed(log_path=None):
    try:
        feed_watchdog(log_path)
    except Exception:
        pass

def _sleep_with_feed(duration_ms, log_path=None):
    # Schlaf in kleinen Stuecken mit WDT-Fuetterung
    remaining = int(duration_ms)
    while remaining > 0:
        chunk = 100 if remaining > 100 else remaining
        utime.sleep_ms(chunk)
        _feed(log_path)
        remaining -= chunk



# --------------------------------------------------------------------
#   Public API
# --------------------------------------------------------------------
def play_note(freq, duration_ms, volume_percent, log_path=None):
    """Sinus-aehnlicher Einzelton mit Ein/Aus-Rampe + Bruch-Abbruch."""
    global alarm_flag
    if freq == 0 or not alarm_flag:
        _speaker.duty_u16(0)
        _sleep_with_feed(duration_ms, log_path)
        return

    try:
        freq = max(_MIN_FREQ, min(freq, _MAX_FREQ))
        _set_freq(freq)
        duty = int(volume_percent * 65535 // 100)

        _ramp_duty(duty)  # fade-in

        t_end = utime.ticks_add(utime.ticks_ms(), duration_ms)
        last_feed = utime.ticks_ms()
        while alarm_flag and utime.ticks_diff(t_end, utime.ticks_ms()) > 0:
            if get_joystick_direction():  # Sofort-Abbruch
                alarm_flag = False
                break
            utime.sleep_ms(4)
            # Alle ~50ms Watchdog fuettern
            now = utime.ticks_ms()
            if utime.ticks_diff(now, last_feed) >= 50:
                _feed(log_path)
                last_feed = now

        _ramp_duty(0)  # fade-out
    except Exception as e:
        log_message(log_path, "[Sound Fehler] play_note(): {}".format(str(e)))
        _speaker.duty_u16(0)


def buzz(freq, duration_ms, volume_percent, log_path=None):
    """Konstanter Ton oder Pause."""
    try:
        if freq == 0:
            _speaker.duty_u16(0)
            _sleep_with_feed(duration_ms, log_path)
            return

        freq = max(_MIN_FREQ, min(freq, _MAX_FREQ))
        _set_freq(freq)
        duty = int(volume_percent * 65535 // 100)
        _speaker.duty_u16(duty)
        _sleep_with_feed(duration_ms, log_path)
    except Exception as e:
        log_message(log_path, "[Sound Fehler] buzz(): {}".format(str(e)))
    finally:
        _speaker.duty_u16(0)


# --------------------------------------------------------------------
#   Kurze Helfer-Melodien
# --------------------------------------------------------------------
def fuer_elise(volume_percent, log_path=None):
    for _ in range(3):
        buzz(1000, 200, volume_percent, log_path)


def paus(volume_percent, log_path=None):
    melody = [
        (330, 1000),
        (415, 1000),
        (370, 1000),
        (247, 1000),
        (0, 500),
        (330, 1000),
        (370, 1000),
        (415, 1000),
        (330, 1000),
    ]
    for note, dur in melody:
        buzz(note, dur, volume_percent, log_path)


def end(volume_percent, log_path=None):
    melody = [
        (330, 1000),
        (415, 1000),
        (370, 1000),
        (247, 1000),
        (0, 500),
        (330, 1000),
        (370, 1000),
        (415, 1000),
        (330, 1000),
        (0, 500),
        (415, 1000),
        (330, 1000),
        (370, 1000),
        (247, 1000),
        (0, 500),
        (247, 1000),
        (370, 1000),
        (415, 1000),
        (330, 1000),
    ]
    for note, dur in melody:
        buzz(note, dur, volume_percent, log_path)


def xp_start_sound(volume_percent, log_path=None):
    for note, dur in [(330, 1000), (415, 1000), (370, 1000), (247, 1000)]:
        buzz(note, dur, volume_percent, log_path)


def tempr(volume_percent, log_path=None):
    # umfangreiches Noten-Array – unveraendert uebernommen

    # Verwendet:
    NOTE_G4, NOTE_C4, NOTE_DS4, NOTE_F4 = 392, 261, 311, 349
    NOTE_E4, NOTE_D4, NOTE_AS3 = 329, 294, 233

    # Nicht verwendet – auskommentiert fuer Ruff:
    # NOTE_C5 = 523
    # NOTE_AS4 = 466
    # NOTE_G5 = 784
    # NOTE_GS4 = 415
    # NOTE_GS5 = 830
    # NOTE_AS5 = 932
    # NOTE_C6 = 1047

    melody = [
        NOTE_G4,
        NOTE_C4,
        NOTE_DS4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_DS4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_DS4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_DS4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_E4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_E4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_E4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_E4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_DS4,
        NOTE_F4,
        NOTE_G4,
        NOTE_C4,
        NOTE_DS4,
        NOTE_F4,
        NOTE_D4,
        NOTE_F4,
        NOTE_AS3,
        NOTE_DS4,
        NOTE_D4,
        NOTE_F4,
        NOTE_AS3,
        NOTE_DS4,
        NOTE_D4,
        NOTE_C4,
    ]

    durations = [
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        8,
        8,
        16,
        16,
        4,
        4,
        16,
        16,
        4,
        4,
        16,
        16,
        1,
        4,
        4,
        16,
        16,
        4,
        4,
        16,
        16,
        1,
    ]

    for note, div in zip(melody, durations):
        buzz(note, int(3000 / div), volume_percent, log_path)


# --------------------------------------------------------------------
#   Volume-Utility
# --------------------------------------------------------------------
def adjust_volume(direction, current_volume, log_path=None):
    new_volume = current_volume
    if direction == "up":
        new_volume = min(current_volume + 10, 100)
    elif direction == "down":
        new_volume = max(current_volume - 10, 0)

    if log_path and new_volume != current_volume:
        log_message(log_path, "Lautstaerke geaendert: {}% → {}%".format(current_volume, new_volume))

    return new_volume

