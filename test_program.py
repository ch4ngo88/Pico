# test_program.py
import time
from sound_config import tempr
from led import led_kranz_animation, set_yellow_leds, led_kranz_einschalten
from time_config import aktualisiere_zeit
from log_utils import log_message
from joystick import get_joystick_direction
from recovery_manager import feed_watchdog
from crash_guard import set_stage

# --------------------------------------------------------------------
#   Konstante Lookup-Tabellen
# --------------------------------------------------------------------
DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_LED_TEST_TIMES = [
    (0, 8, 45),
    (0, 10, 0),
    (0, 16, 30),
    (1, 9, 45),
    (1, 10, 2),
    (1, 18, 45),
    (2, 10, 45),
    (2, 11, 49),
    (2, 21, 0),
    (3, 11, 30),
    (3, 11, 51),
    (3, 23, 15),
    (0, 12, 45),
    (0, 14, 8),
    (0, 1, 30),
    (1, 13, 45),
    (1, 14, 10),
    (1, 3, 45),
    (2, 14, 45),
    (2, 15, 57),
    (2, 6, 0),
    (3, 15, 30),
    (3, 15, 59),
    (3, 8, 15),
    (4, 14, 0),
    (5, 12, 15),
    (5, 18, 45),
    (6, 0, 0),
]


# --------------------------------------------------------------------
#   Haupt-Routine
# --------------------------------------------------------------------
def test_program(lcd, np, wlan, log_path=None, volume_percent=50):
    """
    Selbsttest-Sequenz (ca. 1 ½ Minuten) – bricht sofort ab,
    wenn die Joystick-Taste gedrueckt wird.
    """

    # ------------------------------------------------------------
    #   interne Helper
    # ------------------------------------------------------------
    def _feed():
        try:
            feed_watchdog(log_path)
        except Exception:
            pass

    def safe_sleep(sec):
        _feed()
        time.sleep(sec)
        _feed()

    def _lcd_bar_char():
        try:
            lcd.custom_char(0, [0b11111] * 8)
        except Exception as e:
            log_message(log_path, "Ladebalken-Char: {}".format(str(e)))

    def _lcd_bar(text):
        try:
            lcd.clear()
            lcd.putstr(text)
            lcd.move_to(0, 1)
            for _ in range(16):
                lcd.putchar(chr(0))
                safe_sleep(0.05)
        except Exception as e:
            log_message(log_path, "Ladebalken: {}".format(str(e)))

    def _show_date():
        try:
            h, m, s, wd, d, mo, y = aktualisiere_zeit()
            lcd.clear()
            lcd.putstr("{:02}.{:02}.{:02}".format(d, mo, y%100).center(16))
            _feed()
        except Exception as e:
            lcd.clear()
            lcd.putstr("Datum Fehler")
            log_message(log_path, "Datumlesen: {}".format(str(e)))
            safe_sleep(2)

    def _blink_green(count=3, delay=0.2):
        for _ in range(count):
            np.fill(0, 255, 0)
            np.show()
            safe_sleep(delay)
            np.fill(0, 0, 0)
            np.show()
            safe_sleep(delay)

    def _smooth_blue():
        try:
            for b in range(0, 129, 16):
                for i in range(8):
                    np.set_pixel(i, 0, 0, b)
                np.show()
                safe_sleep(0.05)
        except Exception as e:
            log_message(log_path, "Blue-fade: {}".format(str(e)))
        safe_sleep(1)

    def _refresh_clock():
        try:
            from clock_program import update_display, update_leds_based_on_time

            h, m, _, wd, *_ = aktualisiere_zeit()
            update_display(lcd, DAY_NAMES, wd, h, m)
            update_leds_based_on_time(np, h, m)
            _feed()
        except Exception as e:
            log_message(log_path, "Clock-Refresh: {}".format(str(e)))

    # ------------------------------------------------------------
    #   LED-Test-Sequenz
    # ------------------------------------------------------------
    def _run_led_tests():
        leds_total, y_count, toggle = 8, 1, True
        loop_counter = 0
        for wd, h, m in _LED_TEST_TIMES:
            _feed()
            loop_counter += 1
            
            # Memory-Cleanup alle 10 Iterationen
            if loop_counter % 10 == 0:
                import gc
                gc.collect()
                _feed()
            
            # Sofort-Abbruch?
            if get_joystick_direction() == "press":
                lcd.clear()
                lcd.putstr("Test beendet.")
                log_message(log_path, "Test abgebrochen (Joystick).")
                safe_sleep(1.5)
                return True

            # Display-Update
            try:
                lcd.clear()
                lcd.move_to(0, 1)
                lcd.putstr("{} {:02d}:{:02d}".format(DAY_NAMES[wd], h, m).center(16))
            except Exception as e:
                log_message(log_path, "LCD-Update: {}".format(str(e)))

            # LED-Spielerei
            try:
                if toggle:
                    set_yellow_leds(np, y_count)
                    y_count = y_count + 1 if y_count < leds_total else leds_total
                else:
                    led_kranz_einschalten(np)
                toggle = not toggle
            except Exception as e:
                log_message(log_path, "LED-Update: {}".format(str(e)))

            # Kurze Pause mit extra WDT-Feed
            safe_sleep(0.25)
            
            # Stage-Update alle 5 Iterationen
            if loop_counter % 5 == 0:
                try:
                    set_stage("test:led_{}".format(loop_counter), log_path)
                except Exception:
                    pass

        log_message(log_path, "LED-Tests erfolgreich abgeschlossen.")
        return False

    # ------------------------------------------------------------
    #   Finale Show-Sequenz
    # ------------------------------------------------------------
    def _finale():
        try:
            # Memory-Cleanup vor Finale
            import gc
            gc.collect()
            _feed()
            safe_sleep(1)
            lcd.clear()
            lcd.putstr("    System    ")
            lcd.move_to(0, 1)
            lcd.putstr("    Ready     ")
            safe_sleep(2)

            _blink_green(4, 0.15)
            np.fill(0, 0, 0)
            np.show()
            safe_sleep(0.3)
            _smooth_blue()

            lcd.clear()
            lcd.putstr("By")
            lcd.move_to(0, 1)
            lcd.putstr("Marco da Silva")
            tempr(volume_percent)  # Musik
            safe_sleep(1.5)

            lcd.clear()
            lcd.putstr("Hab dich lieb")
            lcd.move_to(0, 1)
            lcd.putstr("kleine Maus")
            safe_sleep(2)

            lcd.clear()
            np.fill(0, 0, 0)
            np.show()
            _refresh_clock()
            log_message(log_path, "Testprogramm abgeschlossen.")
        except Exception as e:
            log_message(log_path, "Final-Sequenz: {}".format(str(e)))

    # ------------------------------------------------------------
    #   Ablauf starten
    # ------------------------------------------------------------
    _lcd_bar_char()
    _feed()
    log_message(log_path, "Testprogramm gestartet.")
    try:
        set_stage("test:start", log_path)
    except Exception:
        pass
    _lcd_bar("Self-Diagnostic")
    try:
        set_stage("test:bar", log_path)
    except Exception:
        pass
    _show_date()
    try:
        set_stage("test:anim", log_path)
    except Exception:
        pass
    led_kranz_animation(np)
    _feed()

    if not _run_led_tests():
        try:
            set_stage("test:finale", log_path)
        except Exception:
            pass
        _finale()
