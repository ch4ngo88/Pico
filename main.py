from machine import Pin, SPI, I2C
import time
import os
import network
from I2C_LCD import I2CLcd
from char import ladebalken_erstellen
from sound_config import fuer_elise, xp_start_sound
from led import led_kranz_animation
from clock_program import run_clock_program, reload_alarms
from log_utils import init_logfile, log_message
import sdcard
from neopixel import myNeopixel
from time_config import synchronisiere_zeit
import joystick
from webserver_program import set_reload_alarms_callback


# --------------------------------------------------------------------------
# Helfer-Funktionen
# --------------------------------------------------------------------------


def ladebalken_anzeigen(lcd, text=""):
    full_block = [0b11111] * 8
    lcd.custom_char(0, full_block)
    lcd.clear()
    if text:
        lcd.putstr(text)
    lcd.move_to(0, 1)
    for _ in range(16):
        lcd.putchar(chr(0))
        time.sleep(0.1)


def read_wifi_credentials(log_path=None):
    wifi_list = []
    try:
        with open("/sd/wifis.txt", "r") as file:
            for line in file:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    name, ssid, password = parts
                    wifi_list.append((name, ssid, password))
    except FileNotFoundError:
        log_message(log_path, "Die Datei wifis.txt wurde nicht gefunden.")
    except Exception as e:
        log_message(log_path, "Fehler beim Lesen der WLAN-Datei: {}".format(str(e)))
    return wifi_list


def connect_to_wifi_from_file(lcd, log_path, max_attempts=3):
    wifi_list = read_wifi_credentials(log_path)
    if not wifi_list:
        if lcd:
            lcd.clear()
            lcd.putstr("Keine WLAN-Daten")
        log_message(log_path, "Keine WLAN-Daten gefunden.")
        time.sleep(2)
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    for name, ssid, password in wifi_list:
        wlan.disconnect()
        attempt = 0
        while attempt < max_attempts:
            wlan.connect(ssid, password)
            max_wait = 10
            while max_wait > 0:
                if wlan.isconnected():
                    log_message(log_path, "Erfolgreich mit " + ssid + " verbunden!")
                    return wlan
                time.sleep(1)
                max_wait -= 1
            log_message(
                log_path,
                "Verbindung mit " + ssid + " fehlgeschlagen, Versuch " + str(attempt + 1) + ".",
            )
            attempt += 1

    log_message(log_path, "Kein WLAN verbunden.")
    wlan.active(False)
    return None


# AUS

def hard_reset_hardware_state(np, led, blue_led, lcd=None, sound_off_fn=None, log_path=None):
    """
    Setzt das gesamte System in einen definierten Grundzustand.
    Alles aus, alles auf False. Robuste Fehlerbehandlung für langfristigen Betrieb.
    """
    reset_errors = []
    
    try:
        # LED-Ring aus (mehrere Versuche)
        for attempt in range(3):
            try:
                np.fill(0, 0, 0)
                np.show()
                break
            except Exception as e:
                if attempt == 2:  # Letzter Versuch
                    reset_errors.append("LED-Ring: " + str(e))
                time.sleep(0.1)

        # Externe LEDs (robust)
        for led_name, led_obj in [("Interne LED", led), ("Blaue LED", blue_led)]:
            if led_obj:
                try:
                    led_obj.value(0)
                except Exception as e:
                    reset_errors.append(led_name + ": " + str(e))

        # LCD sicher zurücksetzen
        if lcd:
            for action_name, action in [("LCD Clear", lambda: lcd.clear()), 
                                      ("LCD Backlight", lambda: lcd.backlight_off())]:
                try:
                    action()
                    time.sleep(0.1)  # LCD braucht Zeit
                except Exception as e:
                    reset_errors.append(action_name + ": " + str(e))

        # Sound stoppen (mehrere Versuche)
        if sound_off_fn:
            for attempt in range(2):
                try:
                    sound_off_fn(50)  # volume_percent Parameter hinzugefügt
                    break
                except Exception as e:
                    if attempt == 1:
                        reset_errors.append("Sound: " + str(e))

        # Joystick "sanft anfassen" (Diagnostik)
        try:
            _ = joystick._vrx.read_u16()
            _ = joystick._vry.read_u16() 
            _ = joystick._sw.value()
        except Exception as e:
            reset_errors.append("Joystick: " + str(e))

        # System-State zurücksetzen (nur bei explizitem Request)
        # NOTE: Status flags werden in main() explizit initialisiert
        # Diese Funktion setzt nur Hardware zurück, keine Software-Flags

        # Nur kritische Fehler loggen
        if reset_errors:
            log_message(log_path, "[Hardware-Reset Warnungen] " + str(len(reset_errors)) + " Probleme: " + "; ".join(reset_errors[:3]))

    except Exception as e:
        log_message(log_path, "[Kritischer Hardware-Reset Fehler] " + str(e))

    time.sleep(0.5)


def mount_sd_card(lcd, spi, cs, sd_path="/sd", led=None):
    # Mehrere Versuche für SD-Mount (oft instabil beim Boot)
    for attempt in range(3):
        try:
            if "sd" not in os.listdir("/"):
                sd = sdcard.SDCard(spi, cs)
                os.mount(sd, sd_path)
            
            # Teste ob SD wirklich funktioniert
            test_file = "{}/test_write.tmp".format(sd_path)
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)

            log_path = init_logfile(sd_path)

            if log_path:
                with open(log_path, "a") as f:
                    f.write("\n" + "#" * 40 + "\n")
                    t = time.gmtime()
                    ts = "{:02d}.{:02d}.{}  {:02d}:{:02d}:{:02d} UTC".format(t[2], t[1], t[0], t[3], t[4], t[5])
                    f.write(ts + "\n")
                    f.write("#" * 40 + "\n\n")
                log_message(log_path, "SD-Karte erfolgreich gemountet.")
            
            # Interne LED AN (nur wenn Parameter übergeben)
            if led:
                try:
                    led.value(1)
                except Exception:
                    pass            

            return log_path

        except Exception as e:
            if attempt < 2:  # Noch Versuche übrig
                if lcd:
                    lcd.clear()
                    lcd.putstr("SD Versuch {}/3".format(attempt + 1))
                time.sleep(1)
                continue
            else:  # Letzter Versuch fehlgeschlagen
                if lcd:
                    lcd.clear()
                    lcd.putstr("SD Fehler")
                log_message(None, "[SD Mount Fehler nach 3 Versuchen] {}".format(str(e)))
                time.sleep(2)
    
    return None


def zaehle_aktive_alarme(pfad="/sd/alarm.txt", retries=5, delay=0.2, log_path=None):
    for attempt in range(retries):
        try:
            if "sd" not in os.listdir("/") or pfad[4:] not in os.listdir("/sd"):
                log_message(
                    log_path,
                    "[Alarm Zaehlversuch {}] Datei noch nicht vorhanden.".format(attempt + 1),
                )
                time.sleep(delay)
                continue
            count = 0
            alarm = {}
            with open(pfad, "r") as f:
                for line in f:
                    line = line.strip()
                    if line == "---":
                        if alarm.get("STATUS", "").lower() == "aktiv":
                            count += 1
                        alarm = {}
                    elif "=" in line:
                        key, value = line.split("=", 1)
                        alarm[key.strip()] = value.strip()
            if alarm and alarm.get("STATUS", "").lower() == "aktiv":
                count += 1
            return count
        except Exception as e:
            log_message(log_path, "[Alarm Zaehlfehler, Versuch {}] {}".format(attempt + 1, str(e)))
            time.sleep(delay)
    log_message(
        log_path,
        "Fehler: Alarme-Datei nicht gefunden oder lesbar nach allen Versuchen.",
    )
    return 0


def teste_joystick(repeats=100, max_dev=6000, log_path=None):
    """
    Kurzer Selbsttest für den Joystick.

    - misst 'repeats' Samples (≈0,5 s)
    - akzeptiert eine max. Abweichung 'max_dev' (Default 6000 ≈ 9 % ADC-Range)
    - Button muss die ganze Zeit HIGH bleiben
    - gibt True/False zurück
    """
    try:
        x_vals, y_vals, sw_vals = [], [], []

        for _ in range(repeats):
            # Rohwerte direkt aus dem Modul – klappt auch nach Soft-Reset
            x_vals.append(joystick._vrx.read_u16())
            y_vals.append(joystick._vry.read_u16())
            sw_vals.append(joystick._sw.value())
            time.sleep(0.005)  # ≈200 Hz, genügt locker

        # Mittelwert und max. Abweichung ermitteln
        mean_x = sum(x_vals) // repeats
        mean_y = sum(y_vals) // repeats
        dev_x = max(abs(v - mean_x) for v in x_vals)
        dev_y = max(abs(v - mean_y) for v in y_vals)

        axes_ok = (dev_x < max_dev) and (dev_y < max_dev)
        button_ok = all(v == 1 for v in sw_vals)  # nie LOW gesehen

        return axes_ok and button_ok

    except Exception as e:
        log_message(log_path, "[Joystick-Test Fehler] {}".format(str(e)))
        return False


# --------------------------------------------------------------------------
# Haupt-Einstieg
# --------------------------------------------------------------------------

def main():
    global np, led, blue_led
    
    # ========================================================================
    # EXPLICIT STATUS INITIALIZATION - Ensures deterministic startup state
    # ========================================================================
    sd_ok = False
    sound_ok = False  
    leds_ok = False
    joystick_ok = False
    wlan = None
    log_path = None
    lcd = None

    i2c_lcd = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
    lcd_devices = i2c_lcd.scan()

    spi = SPI(0, sck=Pin(6), mosi=Pin(7), miso=Pin(4))
    cs = Pin(5, Pin.OUT)

    NUM_LEDS = 8
    np = myNeopixel(NUM_LEDS, 28)

    try:
        led = Pin("LED", Pin.OUT)
    except Exception:
        led = Pin(25, Pin.OUT)
    led.value(0)

    blue_led = Pin(13, Pin.OUT)
    blue_led.value(0)
    
    
    # Sound Reset: Nicht nötig beim Boot da PWM schon aus ist
    # KEIN paus() aufrufen - das ist eine Melodie!
    sound_off_function = None
    
    # ========== ALLES PLATT MACHEN ZUERST ==========
    hard_reset_hardware_state(
        np=np,
        led=led,
        blue_led=blue_led,
        lcd=None,  # LCD noch nicht verfügbar
        sound_off_fn=sound_off_function,
        log_path=None  # kein Logfile zu dem Zeitpunkt – Konsole only
    )
    
    # ---------- LCD INIT (und AN lassen!) ----------
    try:
        if lcd_devices:
            lcd = I2CLcd(i2c_lcd, lcd_devices[0], 2, 16)
            time.sleep(2)

            lcd.clear()
            lcd.putstr("Display: OK")
            lcd.backlight_on()  # Explizit AN lassen!
            time.sleep(2)
            ladebalken_erstellen(lcd)
        else:
            log_message(None, "LCD nicht gefunden.")
    except Exception as e:
        log_message(None, "[LCD Init Fehler] " + str(e))    

    # ---------- SD ----------
    if lcd:
        ladebalken_anzeigen(lcd, "Mount SD...")
    try:
        log_path = mount_sd_card(lcd, spi, cs, led=led)
        sd_ok = log_path is not None

        # SD erfolgreich gemountet - zeige Status an
        if sd_ok:
            # Freien Speicher ermitteln - bewährte Formel verwenden
            try:
                statvfs = os.statvfs("/sd")
                
                # TEMPORÄRER DEBUG für SD-Problem
                if log_path:
                    debug_info = "statvfs debug: [0]={} [1]={} [2]={} [3]={}".format(
                        statvfs[0], statvfs[1], statvfs[2], statvfs[3])
                    log_message(log_path, debug_info)
                    
                    total_sectors = statvfs[2]  # f_blocks
                    sector_size = statvfs[1]    # f_frsize  
                    total_gb = (total_sectors * sector_size) / (1024 * 1024 * 1024)
                    log_message(log_path, "Berechnete SD-Groesse: {:.2f} GB".format(total_gb))
                
                free_mb = statvfs[3] * statvfs[1] / (1024 * 1024)  # Wie im Systemmonitor
                
                if lcd:
                    lcd.clear()
                    lcd.putstr("SD: OK")
                    lcd.move_to(0, 1)
                    lcd.putstr("{:.1f} MB frei".format(free_mb))
                    time.sleep(2)
            except Exception:
                # Fallback ohne Speicher-Info
                if lcd:
                    lcd.clear()
                    lcd.putstr("SD: OK")
                    lcd.move_to(0, 1)
                    lcd.putstr("Bereit")
                    time.sleep(2)
            
            # Systemstart loggen
            ts = time.localtime()
            log_timestamp = "{:02d}.{:02d}.{}  {:02d}:{:02d}:{:02d}".format(ts[2], ts[1], ts[0], ts[3], ts[4], ts[5])
            with open(log_path, "a") as f:
                f.write("\n" + "#" * 40 + "\n")
                f.write(log_timestamp + " - SYSTEMSTART\n")
                f.write("#" * 40 + "\n\n")
            log_message(log_path, "=== Systemstart: Uhr wird initialisiert ===")

    except Exception as e:
        log_message(None, "[SD Mount Fehler] " + str(e))

    if not sd_ok:
        log_message(
            None, "SD nicht verfuegbar, Logdatei nicht nutzbar – schreibe in Konsole."
        )

    # ---------- Alarme ----------
    if sd_ok:
        try:
            reload_alarms(log_path)
            time.sleep(0.5)
            anzahl_alarme = zaehle_aktive_alarme("/sd/alarm.txt", log_path=log_path)
            log_message(log_path, "Geladene Alarme: " + str(anzahl_alarme))
            if lcd:
                lcd.clear()
                lcd.putstr("SD: OK")
                alarm_text = "Alarme: " + str(anzahl_alarme)
                lcd.move_to((16 - len(alarm_text)) // 2, 1)
                lcd.putstr(alarm_text)
        except Exception as e:
            log_message(log_path, "[Alarme Laden Fehler] " + str(e))
    else:
        if lcd:
            lcd.clear()
            lcd.putstr("Keine SD!")
            lcd.move_to(0, 1)
            lcd.putstr("0 Alarme")
            time.sleep(1)

    # ---------- Sound + LED-Test ----------
    if lcd:
        ladebalken_anzeigen(lcd, "Sync Sound & LED")
    
    volume = 50  # Initialize volume regardless of sound test outcome
    try:
        # Nur kurzer Test-Ton, keine ganze Melodie beim Booten!
        from sound_config import play_note
        play_note(440, 200, volume)  # Kurzer Test-Ton
        sound_ok = True
    except Exception as e:
        sound_ok = False  # Explicit fallback
        log_message(log_path, "[Sound Fehler] " + str(e))
    log_message(log_path, "Sound-Test " + ("OK" if sound_ok else "FEHLER"))

    try:
        led_kranz_animation(np)
        leds_ok = True
    except Exception as e:
        leds_ok = False  # Explicit fallback
        log_message(log_path, "[LED Fehler] " + str(e))
    log_message(log_path, "LED-Test " + ("OK" if leds_ok else "FEHLER"))

    if lcd:
        lcd.clear()
        lcd.putstr("Sound:" + ("OK" if sound_ok else "Fail"))
        lcd.move_to(0, 1)
        lcd.putstr("LEDs :" + ("OK" if leds_ok else "Fail"))
        time.sleep(1)

    # ---------- Joystick-Selbsttest ----------
    if lcd:
        ladebalken_anzeigen(lcd, "Sync Joystick...")
    try:
        joystick_ok = teste_joystick(log_path=log_path)
    except Exception as e:
        joystick_ok = False  # Explicit fallback
        log_message(log_path, "[Joystick-Test Fehler] " + str(e))
    log_message(log_path, "Joystick-Test " + ("OK" if joystick_ok else "FEHLER"))

    if lcd:
        lcd.clear()
        lcd.putstr("Steuerung: OK" if joystick_ok else "Steuerung: Fehler")
        time.sleep(1)

    # ---------- WLAN ----------
    if lcd:
        ladebalken_anzeigen(lcd, "Connecting...")
    try:
        if sd_ok:
            wlan = connect_to_wifi_from_file(lcd, log_path)
    except Exception as e:
        log_message(log_path, "[WLAN-Verbindungsfehler] " + str(e))

    if lcd:
        lcd.clear()
        if wlan and wlan.isconnected():
            try:
                try:
                    ssid = wlan.config("ssid")
                except Exception:
                    ssid = wlan.config("essid")
                lcd.putstr("SSID: " + ssid)
                log_message(log_path, "WLAN verbunden: SSID=" + ssid)
            except Exception as e:
                log_message(log_path, "[WLAN-Status Fehler] " + str(e))
        else:
            lcd.putstr("WLAN: Fehler")
            log_message(log_path, "WLAN-Verbindung fehlgeschlagen.")
        time.sleep(2)

    # ---------- Zeit-Sync ----------
    if lcd:
        ladebalken_anzeigen(lcd, "Sync Time...")
    try:
        erfolg = synchronisiere_zeit(log_path)
        if lcd:
            lcd.clear()
            lcd.putstr("Sync Time: NTP" if erfolg else "RTC genutzt")
        log_message(
            log_path,
            "Zeit synchronisiert" if erfolg else "RTC genutzt (NTP fehlgeschlagen)",
        )
    except Exception as e:
        log_message(log_path, "[Zeit-Sync Fehler] " + str(e))

    time.sleep(1)

    # ---------- Start-Sound ----------
    try:
        if sound_ok:
            xp_start_sound(volume)
            log_message(log_path, "Start-Sound abgespielt.")
    except Exception as e:
        log_message(log_path, "[Start-Sound Fehler] " + str(e))

    # ---------- System Status Summary ----------
    status_summary = [
        "SD: " + ("✓" if sd_ok else "✗"),
        "Sound: " + ("✓" if sound_ok else "✗"),
        "LEDs: " + ("✓" if leds_ok else "✗"),
        "Joy: " + ("✓" if joystick_ok else "✗"),
        "WiFi: " + ("✓" if wlan and wlan.isconnected() else "✗")
    ]
    log_message(log_path, "=== System bereit: " + " ".join(status_summary) + " ===", force=True)

    # ---------- Hauptprogramm ----------
    log_message(log_path, "Hauptprogramm wird gestartet.")
    try:
        set_reload_alarms_callback(lambda: reload_alarms(log_path))
        time.sleep(0.2)

        run_clock_program(lcd, np, wlan, log_path, ladebalken_anzeigen, led, blue_led)
    except Exception as e:
        log_message(log_path, "[Hauptprogramm Fehler] " + str(e))
        # Bei kritischem Fehler: Status-Report für Debugging
        log_message(log_path, "Status bei Fehler: " + " ".join(status_summary), force=True)

if __name__ == "__main__":
    main()
