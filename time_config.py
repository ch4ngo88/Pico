import ntptime
import machine
import time
from ds3231 import RTC
from log_utils import log_message

# -------- RTC-Instanz -------------------------------------------------
rtc = RTC(sda_pin=20, scl_pin=21)  # Pins ggf. anpassen

# Fallback fuer RTC-Ausfaelle (verhindert Zeitspruenge auf 2000)
_last_good_time = None


# ---------------------------------------------------------------------
#   Zeit lesen
# ---------------------------------------------------------------------
def aktualisiere_zeit(log_path=None):
    """
    Liefert (hour, minute, second, weekday_index_0, day, month, year).
    Bei Fehler → mehrere Versuche, dann Fallback.
    """
    # Mehrere Versuche fuer RTC-Lesung (I2C kann manchmal haengen)
    for attempt in range(3):
        try:
            result = rtc.read_time()
            if result is None:
                if attempt < 2:
                    time.sleep(0.1)  # Kurz warten vor naechstem Versuch
                    continue
                raise ValueError("RTC read returned None after 3 attempts")
            
            second, minute, hour, weekday, day, month, year = result
            
            # Plausibilitaetspruefung
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                if attempt < 2:
                    time.sleep(0.1)
                    continue
                raise ValueError("Invalid time values: {}:{}:{}".format(hour, minute, second))
                
            aktueller_tag = weekday - 1  # 0=So … 6=Sa
            
            # Speichere als letzte gute Zeit (verhindert 2000er-Zeitspruenge)
            global _last_good_time
            _last_good_time = (hour, minute, second, aktueller_tag, day, month, year)
            
            return hour, minute, second, aktueller_tag, day, month, year

        except Exception as e:
            if attempt == 2:  # Letzter Versuch
                log_message(log_path, "RTC-Fehler nach 3 Versuchen: %s" % e)
            time.sleep(0.05)  # Kurze Pause zwischen Versuchen
    
    # Fallback: Letzte bekannte gute Zeit oder sinnvoller Default
    global _last_good_time
    if _last_good_time:
        log_message(log_path, "[RTC-Fallback] Verwende letzte gute Zeit")
        return _last_good_time
    else:
        # Erstes Boot - verwende aktuelles Jahr statt 2000
        log_message(log_path, "[RTC-Fallback] Erstboot - verwende 2025")
        return 12, 0, 0, 1, 30, 9, 2025  # 30.9.2025 12:00 (Montag)


# ---------------------------------------------------------------------
#   Sommer-/Winterzeit-Offset EU
# ---------------------------------------------------------------------
def bestimme_zeitzone_offset(jahr, monat, tag, log_path=None):
    try:
        # letzter Sonntag im Maerz
        sommerzeit_start = max(
            w
            for w in range(25, 32)
            if time.localtime(time.mktime((jahr, 3, w, 0, 0, 0, 0, 0)))[6] == 6
        )
        # letzter Sonntag im Oktober
        winterzeit_start = max(
            w
            for w in range(25, 32)
            if time.localtime(time.mktime((jahr, 10, w, 0, 0, 0, 0, 0)))[6] == 6
        )
    except Exception as e:
        log_message(log_path, "Fehler bei Sommerzeit-Berechnung: %s" % e)
        return 1  # Default MEZ

    if 4 <= monat <= 9:
        return 2  # MESZ
    if monat == 3:
        return 2 if tag >= sommerzeit_start else 1
    if monat == 10:
        return 1 if tag >= winterzeit_start else 2
    return 1  # MEZ


# ---------------------------------------------------------------------
#   NTP-Sync  → RTC → System-RTC
# ---------------------------------------------------------------------
def synchronisiere_zeit(log_path=None):
    try:
        ntptime.host = "pool.ntp.org"
        ntptime.settime()  # System-RTC auf UTC
        log_message(log_path, "NTP-Zeit geholt.")

        # UTC-Zeit holen und Offset anwenden
        t = time.localtime()  # noch UTC!
        jahr, monat, tag = t[0], t[1], t[2]
        hour, minute, second = t[3], t[4], t[5]
        weekday = t[6]  # 0=Mo … 6=So

        offset = bestimme_zeitzone_offset(jahr, monat, tag, log_path)
        local_seconds = time.mktime(t) + offset * 3600
        lt = time.localtime(local_seconds)

        jahr, monat, tag = lt[0], lt[1], lt[2]
        hour, minute, second = lt[3], lt[4], lt[5]
        weekday = (lt[6] + 1) % 7 + 1  # 1=So … 7=Sa

        # ---- RTC stellen (neue API) ----
        rtc.set_time(second, minute, hour, weekday, tag, monat, jahr)

        log_message(
            log_path,
            "RTC neu gestellt: %02d:%02d:%02d, %02d.%02d.%d, Offset UTC+%d"
            % (hour, minute, second, tag, monat, jahr, offset),
        )
        return True

    except Exception as e:
        log_message(log_path, "NTP fehlgeschlagen: %s" % e)
        
        # ---- Robuster Fallback: RTC → System-Uhr ----
        try:
            # Nutze die robuste aktualisiere_zeit Funktion statt direktes RTC-Read
            hour, minute, second, aktueller_tag, day, month, year = aktualisiere_zeit(log_path)
            
            # Plausibilitaetspruefung - verhindert Zeitspruenge
            if year < 2020:  # Verhindert Fallback auf 2000 oder andere ungueltige Jahre
                log_message(log_path, "RTC-Jahr {} unplausibel, behalte aktuelle Zeit", year)
                return False
                
            weekday = (aktueller_tag + 1) % 7 + 1  # Konvertiere zu DS3231-Format
            
            log_message(log_path, "NTP-Fallback: RTC-Zeit {}:{:02d} {}.{}.{} verwendet".format(
                hour, minute, day, month, year))
            
            machine.RTC().datetime(
                (year, month, day, weekday % 7, hour, minute, second, 0)
            )
            log_message(log_path, "Systemzeit auf plausible RTC-Zeit gesetzt.")
        except Exception as e2:
            log_message(log_path, "Fehler beim RTC-Fallback: %s" % e2)
        return False
