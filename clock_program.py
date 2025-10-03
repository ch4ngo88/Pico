import os
import time
import utime
from machine import ADC, Pin

from time_config import aktualisiere_zeit, synchronisiere_zeit
from log_utils import log_message, log_important, log_once_per_day, log_alarm_event, log_config_change, log_startup
import sound_config as sc
from sound_config import adjust_volume, fuer_elise
from joystick import get_joystick_direction
from power_management import (
    should_display_be_on,
    get_brightness_for_state,
    get_led_power_mode,
    set_led_power_mode,
    get_volume_settings,
    set_volume_settings,
)
from recovery_manager import init_recovery_system, feed_watchdog, check_system_health, activity_heartbeat
from memory_monitor import monitor_memory, emergency_cleanup, check_and_cleanup_low_memory
from webserver_program import (
    start_webserver_and_show_ip,
    stop_webserver,
    handle_website_connection,
)
from recovery_manager import feed_watchdog
from crash_guard import set_stage

#-----------------------------------------------------------------
# Globale Variablen / Defaults
# --------------------------------------------------------------------
vrx = ADC(26)
vry = ADC(27)
sensor = ADC(4)

# Alarm-System
weckzeiten = []
weckstatus = []

reset_threshold = 2  # Sekunden
last_minute = None
last_sync_day = None
rtc_status_logged = False

# Display-Toggle Steuerung
display_toggle_enabled = True  # Global aktiviert/deaktiviert Display-Toggle
last_menu_exit_time = 0  # Zeitpunkt des letzten Menue-Verlassens

# wird im run_clock_program() gesetzt, damit Helper auch ohne Param. loggen
log_path_global = None

# Joystick-Button auf Pin 22
try:
    joy_pin = Pin(22, Pin.IN, Pin.PULL_UP)
    sw = joy_pin
    joy_pin.irq(
        trigger=Pin.IRQ_FALLING,
        handler=lambda pin: setattr(sc, "alarm_flag", False),
    )
except Exception as e:
    log_message(None, "[Joystick Setup Fehler] {}".format(str(e)))


# --------------------------------------------------------------------
# Funktionen
# --------------------------------------------------------------------
def lade_alarme_von_datei_new_format(pfad="/sd/alarm.txt", log_path=None):
    """Parst Alarm-Datei; DAYS = '-' → jeden Tag."""
    alarme = []
    try:
        if "sd" not in os.listdir("/"):
            log_message(log_path, "[Alarme Laden] SD-Karte nicht gefunden.")
            return alarme
        with open(pfad, "r") as f:
            alarm = {}
            for line in f:
                line = line.strip()
                if line == "---":
                    if all(k in alarm for k in ("TIME", "TEXT", "DAYS", "STATUS")):
                        try:
                            stunde, minute = map(int, alarm["TIME"].split(":"))
                        except (ValueError, AttributeError):
                            log_message(
                                log_path,
                                "[Alarme Laden] Ungueltige Alarmzeit: {}".format(alarm.get('TIME')),
                            )
                            alarm = {}
                            continue
                        if alarm["DAYS"] == "-":
                            tage = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]
                        else:
                            tage = alarm["DAYS"].split(",")
                        if alarm["STATUS"].strip().lower() == "aktiv":
                            alarme.append((stunde, minute, alarm["TEXT"], tage))
                    alarm = {}
                elif "=" in line:
                    key, value = line.split("=", 1)
                    alarm[key.strip()] = value.strip()
    except Exception as e:
        log_message(log_path, "[Alarme Laden Fehler] {}".format(str(e)))
    return alarme


def reload_alarms(log_path):
    global weckzeiten, weckstatus
    try:
        new_alarms = lade_alarme_von_datei_new_format(log_path=log_path)
        # Plausibilitaetspruefung
        if isinstance(new_alarms, list) and len(new_alarms) <= 10:  # Max 10 Alarme
            weckzeiten = new_alarms
            weckstatus = [False] * len(weckzeiten)
            # Nur bei Start oder aenderung loggen
            log_once_per_day(log_path, "Alarme geladen: {} Stueck".format(len(weckzeiten)), time.localtime()[7])
        else:
            log_important(log_path, "Ungueltige Alarme-Datei, verwende Fallback")
            weckzeiten = []
            weckstatus = []
    except Exception as e:
        log_message(log_path, "Fehler beim Laden der Alarme: {}".format(str(e)))
        weckzeiten = []
        weckstatus = []


# ---------------- System-Monitor ----------------
def show_cpu_temp_and_free_space(lcd, ladebalken_anzeigen_func=None, path="/sd"):
    if ladebalken_anzeigen_func and lcd:
        ladebalken_anzeigen_func(lcd, "System Monitor")
    
    try:
        def _safe_sleep(sec):
            # Schlaf stueckeln und Watchdog fuettern
            import time as _t
            end = _t.time() + sec
            while _t.time() < end:
                _t.sleep(0.5)
                try:
                    feed_watchdog(log_path_global)
                except Exception:
                    pass
        
        temp_c = read_cpu_temperature()
        free_space = get_sd_card_free_space(path)
        
        # Memory Stats holen
        from memory_monitor import get_memory_stats
        mem_stats = get_memory_stats()
        
        if lcd:
            # Seite 1: CPU & SD
            try:
                set_stage("sysmon:page1", log_path_global)
            except Exception:
                pass
            lcd.clear()
            lcd.putstr("CPU: {:.1f}C".format(temp_c))
            lcd.move_to(0, 1)
            if free_space is not None:
                lcd.putstr("SD: {:.1f}MB".format(free_space))
            else:
                lcd.putstr("SD: Error")
            _safe_sleep(3)
            
            # Seite 2: Memory 
            try:
                set_stage("sysmon:page2", log_path_global)
            except Exception:
                pass
            lcd.clear()
            lcd.putstr("RAM: {}KB frei".format(mem_stats['free']//1024))
            lcd.move_to(0, 1)
            lcd.putstr("Cleanup: {} mal".format(mem_stats['gc_count']))
            # kuerzerer Schlaf mit haeufigerem WDT-Feed, um Timeouts zu vermeiden
            def _short_safe_sleep(total):
                import time as _t
                end = _t.time() + total
                while _t.time() < end:
                    _t.sleep(0.25)
                    try:
                        feed_watchdog(log_path_global)
                    except Exception:
                        pass
            _short_safe_sleep(3)
            
            lcd.clear()
            hour, minute, _, aktueller_tag, _, _, _ = aktualisiere_zeit()
            update_display(
                lcd,
                ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"],
                aktueller_tag,
                hour,
                minute,
            )
            try:
                feed_watchdog(log_path_global)
            except Exception:
                pass
    except Exception as e:
        log_message(log_path_global, "[System Monitor Fehler] {}".format(str(e)))
        if lcd:
            lcd.clear()
            lcd.putstr("Monitor Fehler")
            time.sleep(2)


def read_cpu_temperature():
    try:
        conversion_factor = 3.3 / 65535
        reading = sensor.read_u16() * conversion_factor
        return 27 - (reading - 0.706) / 0.001721
    except Exception as e:
        log_message(log_path_global, "[CPU-Temp Fehler] {}".format(str(e)))
        return 0.0


def get_sd_card_free_space(path="/sd"):
    """Memory-sichere SD-Karten Speicherabfrage mit begrenzter Diagnostik"""
    try:
        if "sd" not in os.listdir("/") or not hasattr(os, "statvfs"):
            return None
        stats = os.statvfs(path)
        
        # BEGRENZTE SD-DIAGNOSE (nur einmal pro Stunde)
        _log_sd_diagnostics_limited(stats, path)
        
        # Einfache Berechnung ohne Memory-intensive Debug-Ausgaben
        return stats[3] * stats[1] / (1024**2)
        
    except Exception as e:
        log_message(log_path_global, "[SD Speicher Fehler] {}".format(str(e)))
        return None

# Globale Variablen fuer SD-Diagnostics-Throttling
_last_sd_diag_time = 0
_sd_diag_interval = 3600  # 1 Stunde

def _log_sd_diagnostics_limited(stats, path):
    """Begrenzte SD-Diagnostics um Memory-Leaks zu verhindern"""
    global _last_sd_diag_time
    import time
    
    current_time = time.time()
    
    # Nur einmal pro Stunde detaillierte Diagnostics
    if current_time - _last_sd_diag_time < _sd_diag_interval:
        return
    
    _last_sd_diag_time = current_time
    
    try:
        if not log_path_global:
            return
            
        # Kompakte Diagnostics ohne Memory-intensive Schleifen
        total_bytes = stats[2] * stats[1] 
        free_bytes = stats[3] * stats[1]
        total_mb = total_bytes / (1024**2)
        free_mb = free_bytes / (1024**2)
        
        # EINE kompakte Log-Nachricht statt vieler
        diag_msg = "SD-Status: {:.1f}MB frei von {:.1f}MB total".format(free_mb, total_mb)
        log_message(log_path_global, diag_msg)
        
        # Datei-Count ohne Detail-Listing (verhindert Memory-Leak)
        try:
            sd_files = os.listdir(path)
            file_count = len(sd_files)
            log_message(log_path_global, "SD-Dateien: {} Stueck".format(file_count))
        except Exception as e:
            log_message(log_path_global, "SD-Listing Fehler: {}".format(str(e)))
            
    except Exception as e:
        log_message(log_path_global, "[SD Diagnostics Fehler] {}".format(str(e)))


def clear_joystick_buffer():
    try:
        while get_joystick_direction() is not None:
            time.sleep(0.05)
    except Exception as e:
        log_message(log_path_global, "[Joystick-Buffer Fehler] {}".format(str(e)))


# ---------------- Anzeige / LEDs ----------------
def update_display(lcd, wochentage, aktueller_tag, hour, minute):
    if not lcd:
        return
    
    try:
        # Plausibilitaetspruefung
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return
        if not (0 <= aktueller_tag < len(wochentage)):
            aktueller_tag = 0  # Fallback
            
        lcd.clear()
        lcd.move_to(0, 0) 
        lcd.putstr("Neuza")
        lcd.move_to(0, 1)
        
        wochentag_str = wochentage[aktueller_tag % 7]
        uhrzeit_str = "{:02d}:{:02d}".format(hour, minute)

        # Zeile 2 sicher clearen und Text zentrieren
        lcd.putstr(" " * 16)
        lcd.move_to(0, 1)
        leer = max(0, (16 - (len(wochentag_str) + 1 + len(uhrzeit_str))) // 2)
        display_text = " " * leer + wochentag_str + " " + uhrzeit_str
        lcd.putstr(display_text[:16])  # Maximal 16 Zeichen
        
    except Exception as e:
        log_message(log_path_global, "[Display Update Fehler] {}".format(str(e)))
        # Fallback: Zumindest Zeit anzeigen
        try:
            lcd.clear()
            lcd.putstr("Zeit: {:02d}:{:02d}".format(hour, minute))
        except Exception:
            pass

def update_leds_based_on_time(np, hour, minute):
    if not np:
        return
    
    try:
        # Plausibilitaetspruefung der Eingabewerte
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return
            
        total_minutes = hour * 60 + minute
        leds_on = min(8, max(0, int((total_minutes % (8 * 7.5)) / 7.5) + 1))
        
        # Robuste LED-Aktualisierung
        for i in range(8):
            try:
                if i < leds_on:
                    np.set_pixel(i, 255, 20, 147)
                else:
                    np.set_pixel(i, 0, 0, 0)
            except Exception:
                # Einzelne LED-Fehler nicht das ganze System crashen lassen
                pass
        
        np.show()
    except Exception as e:
        log_message(log_path_global, "[LED Update Fehler] {}".format(str(e)))


# ---------------- Alarm-Logik ----------------
def get_tag_name(aktueller_tag):
    return ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"][aktueller_tag % 7]


def check_alarm(hour, minute, aktueller_tag, weckzeiten, weckstatus, log_path):
    tag_name = get_tag_name(aktueller_tag)
    aktuelle_minuten = hour * 60 + minute

    for index, (w_h, w_m, text, tage) in enumerate(weckzeiten):
        if weckstatus[index]:
            continue
        if tag_name not in tage:
            continue
        alarm_minuten = w_h * 60 + w_m
        if abs(alarm_minuten - aktuelle_minuten) <= 1:
            return index, text

    return None, None



def alarm_ausloesen(np, lcd, volume, text, idx=None, log_path=None):
    """Memory-sichere Alarm-Funktion mit guaranteed cleanup"""
    
    # MEMORY-SAFE: Lokale Variablen minimieren
    sc.alarm_flag = True
    start_time = utime.time()
    cleanup_done = False
    
    def log_alarm_stopped_manually():
        if log_path is not None and idx is not None:
            log_alarm_event(log_path, "Alarm manuell beendet - Index {}, Text: {}".format(idx, text))

    def emergency_cleanup():
        """Garantierte Aufraeumung bei Alarm-Ende"""
        nonlocal cleanup_done
        if cleanup_done:
            return
            
        try:
            # Display zuruecksetzen
            if lcd:
                lcd.clear()
            
            # LEDs zuruecksetzen
            if np:
                try:
                    np.fill(0, 0, 0)
                    np.show()
                except Exception as e:
                    log_message(log_path_global, "[Alarm Ende LED Reset] {}".format(str(e)))
            
            # Zeit/LEDs aktualisieren 
            try:
                hour, minute, *_ = aktualisiere_zeit()
                update_leds_based_on_time(np, hour, minute)
            except Exception as e:
                log_message(log_path_global, "[Alarm Ende Zeit Update] {}".format(str(e)))
                
            # Joystick-Buffer leeren
            clear_joystick_buffer()
            
            # Memory cleanup
            import gc
            gc.collect()
            
            cleanup_done = True
        except Exception as e:
            log_message(log_path, "[Alarm-Cleanup Fehler] {}".format(str(e)))

    try:
        # ---------- Display Setup (Memory-safe) ----------
        _setup_alarm_display(lcd, text)
        
        # ---------- SIMPLIFIED ALARM LOOP (Memory-safe) ----------
        melody_notes = [(330, 1000), (415, 1000), (370, 1000), (247, 1000), (0, 500),
                       (330, 1000), (370, 1000), (415, 1000), (330, 1000)]
        
        led_cycle = 0
        melody_index = 0
        last_led_time = utime.ticks_ms()
        last_sound_time = utime.ticks_ms()
        
        # SINGLE LOOP statt nested loops - verhindert Memory-Leaks!
        loop_iterations = 0
        while sc.alarm_flag and (utime.time() - start_time) < 900:
            current_time = utime.ticks_ms()
            
            # Watchdog-Fuetterung alle 100 Loop-Iterationen (verhindert Reset-Loops)
            loop_iterations += 1
            if loop_iterations % 100 == 0:
                feed_watchdog(log_path)
            
            # LED-Blinking (alle 300ms)
            if utime.ticks_diff(current_time, last_led_time) >= 300:
                _handle_alarm_leds(np, led_cycle)
                led_cycle = (led_cycle + 1) % 2
                last_led_time = current_time
            
            # Sound-Handling (nach Melodie-Timing)
            if melody_index < len(melody_notes) and utime.ticks_diff(current_time, last_sound_time) >= melody_notes[melody_index][1]:
                note, duration = melody_notes[melody_index]
                sc.play_note(note, duration, volume)
                melody_index = (melody_index + 1) % len(melody_notes)
                last_sound_time = current_time
            
            # KRITISCH: Joystick-Check mit sofortigem Exit
            if get_joystick_direction():
                sc.alarm_flag = False
                log_alarm_stopped_manually()
                feed_watchdog(log_path)  # Final watchdog feed vor Exit
                break  # SOFORTIGER EXIT verhindert Memory-Leak!
            
            # Short sleep to prevent CPU overload
            utime.sleep_ms(10)
            
    except Exception as e:
        log_message(log_path, "[Alarm Fehler] {}".format(str(e)))
    finally:
        # GARANTIERTE Aufraeumung - egal was passiert!
        emergency_cleanup()


def _setup_alarm_display(lcd, text):
    """Memory-sichere Display-Konfiguration fuer Alarm"""
    if not lcd or not text:
        return
        
    try:
        lcd.clear()
        text_len = len(text)
        
        if text_len <= 16:
            # Zentriert auf erster Zeile
            lcd.move_to(max(0, (16 - text_len) // 2), 0)
            lcd.putstr(text)
        elif text_len <= 32:
            # Auf zwei Zeilen aufteilen
            line1 = text[:16]
            line2 = text[16:]
            lcd.move_to(max(0, (16 - len(line1)) // 2), 0)
            lcd.putstr(line1)
            lcd.move_to(max(0, (16 - len(line2)) // 2), 1)
            lcd.putstr(line2)
        else:
            # Lange Texte abschneiden
            lcd.move_to(0, 0)
            lcd.putstr(text[:16])
            lcd.move_to(0, 1)
            lcd.putstr(text[16:32])
    except Exception as e:
        log_message(log_path_global, "[Alarm Display Fehler] {}".format(str(e)))


def _handle_alarm_leds(np, cycle):
    """Memory-sichere LED-Behandlung fuer Alarm"""
    if not np:
        return
        
    try:
        if cycle == 0:
            # Rot
            np.fill(255, 0, 0)
        else:
            # Aus
            np.fill(0, 0, 0)
        np.show()
    except Exception as e:
        log_message(log_path_global, "[Alarm LEDs Fehler] {}".format(str(e)))
    
    
def toggle_led_status(np, lcd, status, hour, minute, led=None, blue_led=None, show_feedback=True):
    try:
        # ---------- LED-Ring ----------
        if np:
            if not status:
                try:
                    np.fill(0, 0, 0)
                except TypeError:
                    np.fill((0, 0, 0))
                np.show()
            else:
                update_leds_based_on_time(np, hour, minute)

        # ---------- Interne LED ----------
        if led:
            try:
                led.value(1 if status else 0)
            except Exception as e:
                log_message(log_path_global, "[LED intern Fehler] {}".format(str(e)))

        # ---------- Blaue Webserver-LED ----------
        if blue_led:
            try:
                blue_led.value(1 if status else 0)
            except Exception as e:
                log_message(log_path_global, "[LED blau Fehler] {}".format(str(e)))

        # ---------- LCD-Backlight ----------
        if lcd:
            try:
                if status:
                    lcd.backlight_on()
                else:
                    lcd.backlight_off()
            except Exception as e:
                log_message(log_path_global, "[LCD Backlight Fehler] {}".format(str(e)))

        # ---------- LCD-Text-Feedback ----------
        if lcd and show_feedback:
            lcd.clear()
            title = "LED-Status"
            state = "LEDs:  An" if status else "LEDs: Aus"
            lcd.move_to((16 - len(title)) // 2, 0)
            lcd.putstr(title)
            lcd.move_to((16 - len(state)) // 2, 1)
            lcd.putstr(state)
            time.sleep(2)
            hour, minute, _, aktueller_tag, _, _, _ = aktualisiere_zeit()
            update_display(
                lcd,
                ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"],
                aktueller_tag,
                hour,
                minute,
            )

    except Exception as e:
        log_message(log_path_global, "[LED Toggle Fehler] {}".format(str(e)))

# --------------------------------------------------------------------
# Haupt-Schleife
# --------------------------------------------------------------------
def run_clock_program(lcd, np, wlan, log_path=None, ladebalken_anzeigen_func=None, led=None, blue_led=None):
    global last_minute, last_sync_day, log_path_global
    global weckstatus, weckzeiten, rtc_status_logged, display_toggle_enabled, last_menu_exit_time

    log_path_global = log_path
    rtc_status_logged = False
    volume_mode = False
    volume_last_interaction = 0
    volume_timeout = 3
    volume_profiles = get_volume_settings(log_path)
    current_volume_profile = 'default'
    volume_dirty = False
    display_on = True
    last_display_check = 0
    manual_override_active = False
    manual_override_state = True
    
    # Initiale Helligkeit basierend auf aktueller Zeit ermitteln
    try:
        hour, minute, _, _, _, _, _ = aktualisiere_zeit()
        _, initial_brightness = should_display_be_on(hour, minute, log_path)
        current_brightness = initial_brightness
    except Exception:
        current_brightness = 64  # Fallback
    
    power_mode_active = get_led_power_mode(log_path) == 'boost'  # LED Power Modus (30% -> 100%)


    test_running = False
    webserver_running = False
    s = None
    volume = volume_profiles['default']
    wochentage = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]
    doppelpunkt_an = True
    letzte_doppelpunkt_zeit = time.time()

    menumode = False
    menu_last_interaction = 0
    menu_timeout = 5
    menu_index = 0
    menu_entries = [
        "1. Testprogramm", 
        "2. Sys Monitor",
        "3. Power Modus",
        "4. IP Adresse",
        "5. Reset"
    ]

    def start_webserver():
        nonlocal s, webserver_running
        try:
            # Ensure any previous server is cleaned up first
            if s:
                stop_webserver_func()
                
            if wlan and wlan.isconnected():
                s, ip = start_webserver_and_show_ip(lcd, wlan, log_path)
                if s:
                    webserver_running = True
                    log_startup(log_path, "Webserver gestartet: {}".format(ip))
                    # Kein Web-LED-Toggle mehr
                else:
                    webserver_running = False
            else:
                log_message(log_path, "[Webserver] WLAN nicht verfuegbar")
        except Exception as e:
            webserver_running = False
            s = None
            log_message(log_path, "[Webserver Start Fehler] {}".format(str(e)))

    def apply_volume_profile(display_state):
        nonlocal volume, current_volume_profile, volume_profiles
        try:
            volume_profiles = get_volume_settings(log_path)
        except Exception:
            pass
        profile = 'default' if display_state else 'night'
        target = volume_profiles['default'] if profile == 'default' else volume_profiles.get('night', volume_profiles['default'])
        volume = max(0, min(100, target))
        current_volume_profile = profile


    def persist_volume_profile():
        nonlocal volume_dirty, volume_profiles, current_volume_profile
        if not volume_dirty:
            return True

        target_profile = 'default' if display_on else 'night'
        default_arg = volume if target_profile == 'default' else None
        night_arg = volume if target_profile == 'night' else None
        success = set_volume_settings(default_arg, night_arg, log_path)
        if success:
            volume_profiles = get_volume_settings(log_path)
            current_volume_profile = target_profile
            volume_dirty = False
        else:
            log_message(log_path, "[Volume] Speichern fehlgeschlagen ({}%).".format(volume))
        return success

    # _web_toggle_leds entfernt – keine Websteuerung der LEDs

    def stop_webserver_func():
        nonlocal s, webserver_running
        try:
            if s:  # Always try to cleanup socket if it exists
                stop_webserver(s, log_path)
                s = None
            webserver_running = False
        except Exception as e:
            log_message(log_path, "[Webserver Stop Fehler] {}".format(str(e)))
            # Force cleanup even on error
            s = None
            webserver_running = False

    try:
        hour, minute, _, aktueller_tag, _, _, _ = aktualisiere_zeit()
        update_leds_based_on_time(np, hour, minute)
    except Exception as e:
        log_message(log_path, "[Initial Zeit/LEDs Fehler] {}".format(str(e)))

    start_webserver()
    
    # Recovery System initialisieren
    init_recovery_system(log_path)

    def set_display_state(
        target_state,
        *,
        source,
        hour,
        minute,
        aktueller_tag,
        show_feedback=True,
        log_entry=None,
        brightness_override=None,
        force_refresh=False,
    ):
        nonlocal display_on, manual_override_active, manual_override_state, current_brightness

        state_changed = force_refresh or (target_state != display_on)

        try:
            if state_changed:
                toggle_led_status(
                    np,
                    lcd,
                    target_state,
                    hour,
                    minute,
                    led,
                    blue_led,
                    show_feedback=show_feedback,
                )

            if target_state and lcd:
                update_display(lcd, wochentage, aktueller_tag, hour, minute)

        except Exception as e:
            log_message(log_path, "[Display State Fehler] {}".format(str(e)))

        display_on = target_state

        if not volume_mode:
            apply_volume_profile(target_state)

        if source == "manual":
            manual_override_active = True
            manual_override_state = target_state
        elif source == "schedule":
            manual_override_active = False
            manual_override_state = target_state
        elif source == "init":
            manual_override_active = False
            manual_override_state = target_state

        if not power_mode_active:
            try:
                desired_brightness = (
                    brightness_override
                    if brightness_override is not None
                    else get_brightness_for_state(target_state, log_path)
                )
                if force_refresh or desired_brightness != current_brightness:
                    if np:
                        np.brightness(desired_brightness)
                    current_brightness = desired_brightness
            except Exception as e:
                log_message(log_path, "[Display Brightness Fehler] {}".format(str(e)))

        if log_entry and log_path:
            log_message(log_path, log_entry)

        return state_changed
    
    # Initiales Display-Check beim Start
    try:
        hour, minute, _, aktueller_tag, _, _, _ = aktualisiere_zeit()
        should_be_on, initial_brightness = should_display_be_on(hour, minute, log_path)
        current_brightness = initial_brightness

        state_changed_init = set_display_state(
            should_be_on,
            source="init",
            hour=hour,
            minute=minute,
            aktueller_tag=aktueller_tag,
            show_feedback=False,
            log_entry="[Display Init] {} (Helligkeit: {})".format(
                'AN' if should_be_on else 'AUS',
                current_brightness,
            ),
            brightness_override=initial_brightness,
            force_refresh=True,
        )
        if power_mode_active and np:
            try:
                np.brightness(255)
                if should_be_on:
                    update_leds_based_on_time(np, hour, minute)
                current_brightness = 255
                if state_changed_init and log_path:
                    log_message(log_path, "[Display Init] Power-Modus aktiv – LEDs auf 100%")
            except Exception as e:
                log_message(log_path, "[Display Init Power-Modus Fehler] {}".format(str(e)))
    except Exception as e:
        log_message(log_path, "[Display Init Fehler] {}".format(str(e)))

    def zuruck_zur_uhranzeige():
        nonlocal menumode, volume_mode
        global display_toggle_enabled, last_menu_exit_time
        try:
            if volume_mode:
                persist_volume_profile()
            menumode = False
            volume_mode = False 
            display_toggle_enabled = True  # Display-Toggle nach Menue wieder aktivieren
            last_menu_exit_time = time.time()  # Merken wann Menue verlassen wurde
            if lcd:
                hour, minute, _, aktueller_tag, _, _, _ = aktualisiere_zeit()
                update_display(lcd, wochentage, aktueller_tag, hour, minute)
        except Exception as e:
            log_message(log_path, "[BackToClock Fehler] {}".format(str(e)))


    
    # Hauptschleife mit garantierter Cleanup
    try:
        while True:
            # Watchdog regelmaessig fuettern (alle Schleifendurchlaeufe)
            feed_watchdog(log_path)
            
            try:
                hour, minute, second, aktueller_tag, day, month, year = aktualisiere_zeit()
            except Exception as e:
                log_message(log_path, "[Zeit Aktualisierung Fehler] {}".format(str(e)))
                continue

            if "weckzeiten" in globals():
                try:
                    result = check_alarm(hour, minute, aktueller_tag, weckzeiten, weckstatus, log_path)
                    if result and isinstance(result, tuple):
                        idx, alarm_text = result
                        if idx is not None and alarm_text:
                            # Debug: Log RTC-Zeit und Alarm-Zeit
                            alarm_hour, alarm_minute = weckzeiten[idx][:2] if idx < len(weckzeiten) else (0, 0)
                            log_alarm_event(log_path, "[ALARM-DEBUG] RTC: {:02d}:{:02d}:{:02d}, Alarm-Soll: {:02d}:{:02d}, Index: {}".format(
                                hour, minute, second, alarm_hour, alarm_minute, idx))
                            
                            alarm_ausloesen(np, lcd, volume, alarm_text, idx=idx, log_path=log_path)
                            weckstatus[idx] = True
                            log_alarm_event(log_path, "Alarm ausgeloest - Index {}, Text: {}".format(idx, alarm_text))
                except Exception as e:
                    log_message(log_path, "[Alarm-Check Fehler] {}".format(str(e)))

            try:
                direction = get_joystick_direction()
            except Exception as e:
                log_message(log_path, "[Joystick Lesen Fehler] {}".format(str(e)))
                direction = None

            if direction:
                menu_last_interaction = time.time() 
                activity_heartbeat()  # System ist aktiv

                # BASIS-MODUS: Links/Rechts = Volume, Oben/Unten = Menue
                if not menumode:
                    # WICHTIG: Wenn Volume-Mode aktiv ist, Up/Down NICHT ins Menue lassen
                    if direction in ("left", "right"):
                        # Volume-Steuerung (wird weiter unten behandelt)
                        pass
                    elif not volume_mode and direction in ("up", "down"):
                        menumode = True
                        menu_index = 0
                        display_toggle_enabled = False  # Display-Toggle waehrend Menue deaktivieren
                        time.sleep(0.3)  # Verhindert ungewollten Doppelsprung

                elif menumode:
                    if direction == "up":
                        menu_index = (menu_index + 1) % len(menu_entries)
                        time.sleep(0.25)
                    elif direction == "down":
                        menu_index = (menu_index - 1) % len(menu_entries)
                        time.sleep(0.25)
                    elif direction == "press":
                        eintrag = menu_entries[menu_index]

                        if eintrag.startswith("1."):
                            test_running = True
                            stop_webserver_func()
                            from test_program import test_program
                            test_program(lcd, np, wlan, log_path, volume)
                            test_running = False
                            start_webserver()
                            zuruck_zur_uhranzeige()  # Korrekte Menue-Verlassen Behandlung

                        elif eintrag.startswith("2."):
                            show_cpu_temp_and_free_space(lcd, ladebalken_anzeigen_func)
                            lcd.clear()
                            zuruck_zur_uhranzeige()  # Korrekte Menue-Verlassen Behandlung

                        elif eintrag.startswith("3."):
                            target_mode = 'boost' if get_led_power_mode(log_path) != 'boost' else 'normal'
                            if set_led_power_mode(target_mode, log_path):
                                power_mode_active = (target_mode == 'boost')
                                if power_mode_active:
                                    if lcd:
                                        lcd.clear()
                                        lcd.putstr("Power Modus AN")
                                        lcd.move_to(0, 1)
                                        lcd.putstr("LEDs: 100%")
                                    if np:
                                        try:
                                            np.brightness(255)
                                            if display_on:
                                                update_leds_based_on_time(np, hour, minute)
                                        except Exception as e:
                                            log_message(log_path, "[Power Modus] LED Boost Fehler: {}".format(str(e)))
                                    current_brightness = 255
                                    log_important(log_path, "[Power Modus] LEDs auf 100% (Config)")
                                else:
                                    if lcd:
                                        lcd.clear()
                                        lcd.putstr("Power Modus AUS")
                                        lcd.move_to(0, 1)
                                        lcd.putstr("LEDs: Normal")
                                    try:
                                        desired = get_brightness_for_state(display_on, log_path)
                                    except Exception:
                                        desired = current_brightness
                                    current_brightness = desired
                                    if np:
                                        try:
                                            np.brightness(desired)
                                            if display_on:
                                                update_leds_based_on_time(np, hour, minute)
                                        except Exception as e:
                                            log_message(log_path, "[Power Modus] LED Normal Fehler: {}".format(str(e)))
                                    log_important(log_path, "[Power Modus] LEDs auf Normal (Config)")
                                time.sleep(2)
                            else:
                                if lcd:
                                    lcd.clear()
                                    lcd.putstr("Power-Config FAIL")
                                log_message(log_path, "[Power Modus] Schreiben nach power_config.txt fehlgeschlagen")
                                time.sleep(2)
                            zuruck_zur_uhranzeige()  # Korrekte Menue-Verlassen Behandlung

                        elif eintrag.startswith("4."):
                            if lcd:
                                lcd.clear()
                                lcd.putstr("IP Adresse:")
                                lcd.move_to(0, 1)
                                lcd.putstr(wlan.ifconfig()[0] if wlan else "Keine Verb.")
                                time.sleep(4)
                                lcd.clear()
                            zuruck_zur_uhranzeige()  # Korrekte Menue-Verlassen Behandlung

                        elif eintrag.startswith("5."):
                            if lcd:
                                lcd.clear()
                            if np:
                                try:
                                    np.fill(0, 0, 0)
                                except TypeError:
                                    np.fill((0, 0, 0))
                                np.show()
                            time.sleep(0.5)
                            try:
                                _mp_reset = __import__('machine').reset
                                _mp_reset()
                            except Exception:
                                pass

            if menumode and lcd:
                # Anti-Bounce: Nur updaten wenn mindestens 100ms im Menu
                if time.time() - menu_last_interaction > 0.1:
                    lcd.clear()
                    lcd.move_to((16 - len("System")) // 2, 0)
                    lcd.putstr("System")
                    text = menu_entries[menu_index]
                    lcd.move_to((16 - len(text)) // 2, 1)
                    lcd.putstr(text)

            if menumode and time.time() - menu_last_interaction > menu_timeout:
                if lcd:
                    lcd.clear()
                zuruck_zur_uhranzeige()  # Korrekte Menue-Verlassen Behandlung

            if not menumode:
                if direction in ("left", "right"):
                    if not volume_mode:
                        volume_mode = True
                        volume_last_interaction = time.time()
                    else:
                        volume_last_interaction = time.time()

                    if direction == "left" and volume > 0:
                        new_volume = max(0, volume - 5)
                        if new_volume != volume:
                            volume = new_volume
                            volume_dirty = True
                    elif direction == "right" and volume < 100:
                        new_volume = min(100, volume + 5)
                        if new_volume != volume:
                            volume = new_volume
                            volume_dirty = True

                    if lcd:
                        lcd.clear()
                        lcd.putstr("Volume: {}%".format(volume))

                elif direction == "press" and volume_mode:
                    volume_mode = False
                    if lcd:
                        lcd.clear()
                        lcd.putstr("Volume: " + str(volume) + "%")
                    persist_volume_profile()
                    fuer_elise(volume)
                    time.sleep(0.5)
                    zuruck_zur_uhranzeige()
                    
                elif direction == "press" and not volume_mode and not menumode:
                    # Display Toggle NUR wenn nicht im Menue-Modus UND genug Zeit seit Menue-Verlassen vergangen
                    current_time = time.time()
                    if display_toggle_enabled and (current_time - last_menu_exit_time) > 1.0:
                        target_state = not display_on
                        set_display_state(
                            target_state,
                            source="manual",
                            hour=hour,
                            minute=minute,
                            aktueller_tag=aktueller_tag,
                            show_feedback=True,
                            log_entry="Display Toggle: {} (Override aktiv)".format(
                                "AN" if target_state else "AUS"
                            ),
                        )
                    # Ignorieren wenn im Menue oder kurz nach Menue-Verlassen

            if webserver_running:
                try:
                    handle_website_connection(s, log_path)
                except Exception as e:
                    log_message(log_path, "[Webserver Fehler] {}".format(str(e)))

            try:
                if hour == 0 and minute == 0 and second < 10 and not rtc_status_logged:
                    log_message(log_path, "[RTC-Status] Zeit: {}:{}, Tag: {}, Wochentag: {}".format(hour, minute, day, aktueller_tag))
                    rtc_status_logged = True
                elif minute != 0:
                    rtc_status_logged = False

                if last_sync_day != day and hour == 0 and minute == 0:
                    if ladebalken_anzeigen_func and lcd:
                        ladebalken_anzeigen_func(lcd, "Auto-Sync...")
                    erfolg = synchronisiere_zeit(log_path)
                    if lcd:
                        lcd.clear()
                        lcd.putstr("Auto-Sync: OK" if erfolg else "Auto-Sync: Fail")
                    log_message(log_path, "Auto-Sync erfolgreich." if erfolg else "Auto-Sync fehlgeschlagen (RTC genutzt).")
                    time.sleep(2)
            except Exception as e:
                log_message(log_path, "[Auto-Sync Fehler] {}".format(str(e)))

            if 1 <= day <= 31 and last_sync_day != day:
                weckstatus = [False] * len(weckzeiten)
                last_sync_day = day
                log_date = "{:02d}.{:02d}.{} - NEUER TAG ({})".format(day, month, year, wochentage[aktueller_tag % 7])
                with open(log_path, "a") as f:
                    f.write("\n" + "-" * 40 + "\n")
                    f.write("{}\n".format(log_date))
                    f.write("-" * 40 + "\n\n")
                log_once_per_day(log_path, "Alarm-Reset fuer neuen Tag: RTC-Tag = {}, last_sync_day = {}".format(day, last_sync_day), day)

            # Display Management (alle 60 Sekunden pruefen)
            try:
                now = time.time()
                if now - last_display_check > 60:  # Alle 60 Sekunden
                    should_be_on, target_brightness = should_display_be_on(hour, minute, log_path)

                    if manual_override_active:
                        if should_be_on == manual_override_state:
                            manual_override_active = False
                            manual_override_state = display_on
                            log_message(log_path, "[Override] Zeitplan entspricht jetzt dem manuellen Zustand - Override beendet")
                        else:
                            if not power_mode_active:
                                try:
                                    desired_brightness = get_brightness_for_state(manual_override_state, log_path)
                                    if desired_brightness != current_brightness:
                                        current_brightness = desired_brightness
                                        if np:
                                            np.brightness(current_brightness)
                                            if manual_override_state and display_on:
                                                try:
                                                    update_leds_based_on_time(np, hour, minute)
                                                except Exception as e:
                                                    log_message(log_path, "[Override LED Fehler] {}".format(str(e)))
                                except Exception as e:
                                    log_message(log_path, "[Override Brightness Fehler] {}".format(str(e)))
                            last_display_check = now
                            continue
                    
                    # Display Ein/Aus aendern wenn noetig
                    if should_be_on != display_on:
                        state_changed = set_display_state(
                            should_be_on,
                            source="schedule",
                            hour=hour,
                            minute=minute,
                            aktueller_tag=aktueller_tag,
                            show_feedback=False,
                            log_entry=None,
                            brightness_override=target_brightness,
                        )
                        if state_changed:
                            log_important(log_path, "[Auto Display] {} um {:02d}:{:02d}".format('AN' if should_be_on else 'AUS', hour, minute))
                    
                    # Helligkeit anpassen wenn noetig (aber nicht wenn Power Modus aktiv)
                    if not power_mode_active and target_brightness != current_brightness:
                        current_brightness = target_brightness
                        if np:
                            np.brightness(current_brightness)
                            if display_on:
                                try:
                                    update_leds_based_on_time(np, hour, minute)
                                except Exception as e:
                                    log_message(log_path, "[LED Update Fehler] {}".format(str(e)))
                    
                    last_display_check = now
            except Exception as e:
                log_message(log_path, "[Display Management Fehler] {}".format(str(e)))

            if minute != last_minute:
                last_minute = minute
                try:
                    if display_on and lcd:
                        update_display(lcd, wochentage, aktueller_tag, hour, minute)
                    if display_on and np:
                        update_leds_based_on_time(np, hour, minute)
                except Exception as e:
                    log_message(log_path, "[Minuten-Update Fehler] {}".format(str(e)))

            # --- NEU: Sekundenparitaet statt eigener Stoppuhr -----------------
            if lcd and not menumode and not volume_mode:
                try:
                    pos = ((16 - (len(wochentage[aktueller_tag % 7]) + 1 + 5)) // 2
                           + len(wochentage[aktueller_tag % 7]) + 3)
                    lcd.move_to(pos, 1)
                    lcd.putstr(":" if second % 2 else " ")
                except Exception as e:
                    log_message(log_path, "[Doppelpunkt Fehler] {}".format(str(e)))

            if volume_mode and time.time() - volume_last_interaction > volume_timeout:
                volume_mode = False
                persist_volume_profile()
                zuruck_zur_uhranzeige()
                fuer_elise(volume)

            # Recovery & Watchdog (alle 30 Sekunden)
            try:
                current_time = int(time.time())
                if current_time % 30 == 0:  # System-Health Check alle 30 Sekunden
                    check_system_health(log_path)
                    
                    # Memory-Check alle 3 Minuten (optimiert von 5 Min)
                    if current_time % 180 == 0:
                        feed_watchdog(log_path)  # Watchdog vor Memory-Ops fuettern
                        free_mem = monitor_memory(log_path, context="main_loop_check")
                        # Sanftes Low-Memory-Handling mit Cooldown statt haeufigen Notfall-Cleanups
                        if free_mem < 12288:  # frueher ansetzen, aber schonend reagieren
                            free_mem = check_and_cleanup_low_memory(log_path, threshold=8192, cooldown_s=600)
                        feed_watchdog(log_path)
                

                            
            except Exception as e:
                log_message(log_path, "[System Check Fehler] {}".format(str(e)))

            time.sleep(0.1)
            
    except KeyboardInterrupt:
        log_message(log_path, "[System] Graceful shutdown angefordert")
    except Exception as e:
        log_message(log_path, "[Hauptschleife Kritischer Fehler] {}".format(str(e)))
    finally:
        # Garantierte Cleanup bei Programmende
        log_message(log_path, "[System] Cleanup wird ausgefuehrt...", force=True)
        try:
            stop_webserver_func()
        except Exception as e:
            log_message(log_path, "[Cleanup] Webserver-Stop Fehler: {}".format(str(e)))
        
        log_message(log_path, "[System] Cleanup abgeschlossen.", force=True)


