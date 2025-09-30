"""
crash_guard.py
Kleiner Crash-Wächter: schreibt die letzte Programm-Phase auf SD,
damit nach einem Reset sichtbar ist, wo das System war.

Schreibt nur bei Zustandswechsel und rate-limitiert, um Verschleiß zu vermeiden.
"""
import os
import time
from log_utils import log_message

_PATH = "/sd/crash_guard.txt"
_last_stage = None
_last_write = 0.0
_min_interval = 2.0  # Sekunden


def _write_stage(stage, log_path=None):
    global _last_stage, _last_write
    now = time.time()
    if stage == _last_stage and (now - _last_write) < _min_interval:
        return
    try:
        with open(_PATH, "w") as f:
            f.write(stage)
        try:
            os.sync()
        except Exception:
            pass
        _last_stage = stage
        _last_write = now
    except Exception as e:
        # Nicht spammen – nur eine knappe Meldung erlauben
        try:
            log_message(log_path, "[CrashGuard] Schreibfehler: {}".format(str(e)))
        except Exception:
            pass


def set_stage(stage, log_path=None):
    """Setzt die aktuelle Phase (z. B. 'test:start', 'sysmon:page1')."""
    if not stage:
        return
    _write_stage(stage, log_path)


def clear_stage(log_path=None):
    """Markiert sauberen Zustand ('idle')."""
    _write_stage("idle", log_path)


def check_previous_crash(log_path=None):
    """Liest letzte Phase und loggt sie, sofern nicht 'idle'."""
    try:
        if not _file_exists(_PATH):
            return None
        with open(_PATH, "r") as f:
            last = (f.read() or "").strip()
        if last and last != "idle":
            log_message(log_path, "[CrashGuard] Letzte Phase vor Reset: {}".format(last), force=True)
        return last
    except Exception:
        return None


def _file_exists(p):
    try:
        os.stat(p)
        return True
    except OSError:
        return False
