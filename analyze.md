Architektur auf einen Blick
Startpunkt: main.py
Initialisiert LCD, SD-Karte/Logging, NeoPixel, Joystick, WLAN, Zeit (NTP/RTC), spielt Startsound.
Laedt Alarme von alarm.txt.
Startet die Hauptuhr-Logik in clock_program.run_clock_program.
Setzt Callback, damit der Webserver gespeicherte Alarme nach POST neu laden kann.
Hauptloop: clock_program.py
Anzeige (LCD), LED-Status (NeoPixel), Alarm-Check/-Ausloesung, Lautstaerke und Menue (Joystick), Power-Management, Webserver-Bearbeitung, Watchdog/Recovery, Memory-Monitoring.
Webserver: webserver_program.py
Minimaler HTTP-Server mit Static-File-Whitelist, Formular zum Speichern von Alarmen und Display-Settings, Log-Viewer.
Zeit/RTC: time_config.py + ds3231.py
NTP Sync → RTC setzen → Systemzeit setzen; robuste Zeitlese-Funktion mit Fallback.
Hardware:
LCD: I2C_LCD.py + LCD_API.py
NeoPixel: neopixel.py
Joystick: joystick.py
SD-Karte: sdcard.py
Utilities: Logging, Memory, Recovery, LED-Animationen, Tests, Zeichen etc.
Datei fuer Datei — Funktionen im ueberblick
README.md
Projektbeschreibung, Hardware, Features, Struktur, Setup.
main.py
ladebalken_anzeigen(lcd, text=""): LCD-Progessbar (Custom-Char 0).
read_wifi_credentials(log_path=None): Liest wifis.txt (name, ssid, password) Zeilenweise.
connect_to_wifi_from_file(lcd, log_path, max_attempts=3): Versucht WLAN nacheinander aus Liste; Debug auf LCD/Log.
hard_reset_hardware_state(np, led, blue_led, lcd=None, sound_off_fn=None, log_path=None):
Schaltet LEDs/LCD/Sound/Joystick in definierten Off-Zustand, robust mit Retry und Fehlerlogging.
mount_sd_card(lcd, spi, cs, sd_path="/sd", led=None):
Mount + Test-Schreib/Lese; initialisiert Logdatei; interne LED an.
zaehle_aktive_alarme(pfad="/sd/alarm.txt", retries=5, ...): Zaehlt STATUS=aktiv Bloecke.
teste_joystick(repeats=100, max_dev=6000, ...): Kurzer Selbsttest (Stabilitaet, Button muss HIGH).
main(): Orchestriert gesamten Boot inkl. Tests, WLAN, NTP/RTC, Startsound und Start von run_clock_program.
clock_program.py
Globale Zustaende: weckzeiten, weckstatus, Debounce/Toggle/Status-Flags, log_path_global usw.

lade_alarme_von_datei_new_format(pfad="/sd/alarm.txt", log_path=None):
Parst Bloecke TIME/TEXT/DAYS/STATUS, DAYS='-' = taeglich; liefert Liste (stunde, minute, text, tage) nur fuer aktive.
reload_alarms(log_path): Laedt neu, setzt weckstatus parallel dazu; begrenzt (<=10 Alarme).
show_cpu_temp_and_free_space(lcd, ladebalken_anzeigen_func=None, path="/sd"): CPU-Temp, SD frei, Memory-Stats, zurueck zur Uhr.
read_cpu_temperature(): ADC(4), Konvertierung auf °C.
get_sd_card_free_space(path="/sd"): statvfs, gedrosselte Diagnostik.
clear_joystick_buffer(): Spuelt Pending-Richtungen.
update_display(lcd, wochentage, aktueller_tag, hour, minute): Zeigt “Neuza”, Wochentag + Zeit, zentriert.
update_leds_based_on_time(np, hour, minute):
0–8 LEDs abhaengig von Tagesminuten mit pinker Farbe; robust gegen Einzel-LED-Fehler.
get_tag_name(aktueller_tag): Index → "So"…"Sa".
check_alarm(hour, minute, aktueller_tag, weckzeiten, weckstatus, log_path):
Match, wenn Tag in Alarm-Tagen und |Δmin| ≤ 1; verpasste Alarme werden geloggt und als behandelt markiert.
alarm_ausloesen(np, lcd, volume, text, idx=None, log_path=None):
Memory-sichere Alarmschleife: rote LED blinkt, einfache Melodie-Liste, Joystick bricht ab, garantiertes Cleanup (LEDs/LCD/GC).
_setup_alarm_display(lcd, text): Text auf 1–2 Zeilen passend darstellen.
_handle_alarm_leds(np, cycle): Rot blinkt.
toggle_led_status(np, lcd, status, hour, minute, led=None, blue_led=None):
Schaltet Ring/Backlight/interne/blue LED; aktualisiert Anzeige und Uhr.
run_clock_program(lcd, np, wlan, log_path=None, ladebalken_anzeigen_func=None, led=None, blue_led=None):
Hauptloop:
Watchdog fuettern, Zeit aktualisieren, Alarm-Check/Ausloesen.
Joystick:
Short-press rechts/links → Volume-Mode mit Anzeige und Sample-Sound (Fuer Elise).
up/down → Menue (Testprogramm, System Monitor, Power Modus 100%, IP, Reset).
press ausserhalb Menues → LED/Display Auto-Update toggeln.
Webserver: start_webserver_and_show_ip, handle_website_connection, stop_webserver.
Auto-Sync Zeit taeglich um 00:00, Display-Auto an/aus/brightness via power_management.should_display_be_on.
Minuetliche LCD/LED-Updates, blinkender Doppelpunkt.
Periodische Health/Mem Checks (30s/180s), Emergency-Cleanup unter 8KB frei.
webserver_program.py
Globale: reload_alarms_callback, blue_led, _save_lock (Race-Schutz), _poller (uselect.poll).
start_webserver_and_show_ip(lcd, wlan, log_path=None): Socket auf 0.0.0.0:80; LED an; IP ins Log.
stop_webserver(s, log_path=None): Socket schliessen, LED aus, Poller deregistrieren.
set_reload_alarms_callback(func): Fuer Alarm-Reload nach Speichern.
Whitelist: ALLOWED_STATIC_FILES mit Typen/Orten (flash/sd); debug-only wurde entfernt.
sanitize_filename(filename, log_path=None): Whitelist + Pfad-Bereinigung, blockiert Traversal und sensible Dateien.
Debug-Modus wurde entfernt; es gibt kein /sd/.debug_enabled Flag mehr.
file_exists(path), html_escape(text).
_receive_http_request(sock): Header bis CRLFCRLF, Content-Length beachtet, 8kB Limit.
PollerGuard: Sichere Registrierung im globalen Poller (cleanup garantiert).
handle_website_connection(s, log_path=None):
Non-block accept + Timeout, Request einlesen, Routing:
POST /save_alarms → _save_alarms + reload_alarms_callback(), 200 OK
POST /save_display_settings → _save_display_settings, 200 OK
POST /toggle_debug existiert nicht mehr
GET / → _serve_index_page (gestreamt)
GET /debug existiert nicht mehr
GET /logs → _serve_log_file (immer)
Sonst: _serve_file_from_sd (Whitelist)
_safe_save_operation(operation_name, save_func, ...): Einfache Sperre _save_lock um Race Conditions zu verhindern.
_save_alarms_unsafe(body, log_path=None):
Parsed Zeilen "HH:MM, Text, [Tage...], [Aktiv/Inaktiv]" (max. 5), schreibt strukturiert in alarm.txt.
_save_alarms(body, log_path=None): Wrapper mit Save-Lock.
_serve_file_from_sd(cl, file_name, log_path=None): Whitelist-sicher; sendet chunks, Content-Type aus Whitelist, Watchdog-Feed bei grossen Dateien.
_serve_debug_file(cl, log_path=None): entfernt – stattdessen /logs fuer Log-Ansicht
_serve_log_file(cl, log_path=None): Immer verfuegbarer Log-Viewer (800 Zeilen), huebsches HTML.
_toggle_debug_mode(cl, log_path=None): entfernt
_save_display_settings_unsafe(body, log_path=None):
Schreibt DISPLAY_AUTO, DISPLAY_ON_TIME, DISPLAY_OFF_TIME nach power_config.txt.
_save_display_settings(body, log_path=None): Wrapper mit Save-Lock.
_load_display_settings(): Liest power_config.txt, Defaults bei Fehlern.
_serve_index_page(cl, log_path=None): Streamt HTML in Chunks mit GC-Zwischenschritten; ruft:
_send_http_header(cl)
_send_html_chunks(cl, log_path):
_send_alarm_blocks_safe(cl, alarme): bis 5 Bloecke
_send_display_block_safe(cl)
_send_footer_chunks(cl, log_path) → Buttons und JS
_generate_alarm_block(zeit, text, tage, aktiv): HTML-Form-Element.
_send_display_block_safe(cl): Fuegt “Display-Einstellungen”-Block ein (siehe Hinweis unten).
_send_footer_chunks(cl, log_path=None): Buttons “Alle speichern” und Log-Viewer; JS Snippet eingebettet.
_send_error_response(cl, code, message).
_load_alarms(path): Parsen von alarm.txt in (TIME, TEXT, DAYS[], STATUS) begrenzt auf 5.
JS_SNIPPET:
saveAllSettings(): POST save_alarms und save_display_settings.
toggleLEDs(): POST /toggle_leds (Achtung: Route existiert aktuell nicht!)
_get_content_type(name): Dateiendungen → MIME.
Security/Health Status Helpers: get_security_status(), is_webserver_healthy(s), get_webserver_status().
save_alarms_to_file(log_path=None): Platzhalter (True).
Hinweise:

Doppelte Definitionen von enable/disable_debug_mode existieren (einmal oben bei Security-Block, und spaeter erneut im File); identische Wirkung, aber redundant.
time_config.py
rtc = RTC(sda_pin=20, scl_pin=21)
aktualisiere_zeit(log_path=None): Robustes RTC-Lesen mit Retries, Plausibilitaetspruefung, Fallback auf letzte gute Zeit bzw. sinnvollen Default.
bestimme_zeitzone_offset(jahr, monat, tag, log_path=None): EU DST (Sommer-/Winterzeit).
synchronisiere_zeit(log_path=None):
NTP → UTC → Offset → lokale Zeit → RTC stellen.
Fallback: RTC lesen und Systemzeit setzen (nur wenn Jahr >= 2020).
ds3231.py
RTC-Klasse (I2C):
set_time(sec, minute, hour, weekday(1–7), day, month, year(2000..2099))
read_time(mode=0) → Modi: Roh-Tuple oder formatierte Strings („DIN-...“, „ISO-...“, „time“, „weekday“)
I2C_LCD.py
I2CLcd(LcdApi): HAL fuer PCF8574-Adapter 4-Bit, Backlight-Steuerung, E-Toggle, Init-Sequenz.
LCD_API.py
LcdApi: High-Level LCD-API (clear, cursor, backlight, move_to, putstr, custom_char), HAL-Platzhalter.
neopixel.py
PIO ws2812 Programm und Klasse myNeopixel:
brightness(value=None), set_pixel, set_pixel_line, set_pixel_line_gradient, fill, rotate_left/right, show.
Helligkeitsskalierung, 24-bit GRB packing.
joystick.py
Hardware: ADC 26/27, Pin 22 Pull-Up.
_measure_center(samples=100): Mittelwert-Kalibrierung.
get_joystick_direction():
Debounce fuer Button, robustes Lesen der Achsen.
Rueckgabe: "left", "right", "up", "down", "press" oder None.
sound_config.py
PWM auf Pin 16, sanfte Duty-Rampe, global alarm_flag.
play_note(freq, duration_ms, volume_percent, log_path=None): Ton mit Fade-in/out, Abbruch bei Joystick.
buzz(freq, duration_ms, volume_percent, log_path=None): Konstanter Ton/Pause.
Kurze Hilfsmelodien: fuer_elise, paus, end, xp_start_sound, tempr (umfangreiche Melodie).
adjust_volume(direction, current_volume, log_path=None): In 10er-Schritten.
led.py
Initialisiert NeoPixel (8 LEDs an GPIO28) beim Import.
Utility:
wheel(pos): Regenbogenfarben.
_safe_fill/_safe_set: Kompatibilitaet mit unterschiedl. fill/signatures.
_rotate_right: Fallback wenn rotate_right fehlt.
Animationen:
led_kranz_animation(np, log_path)
Zustandsfunktionen:
led_kranz_einschalten, led_bleibt_rot, led_rosa.
Blink/Countdown:
led_und_buzzer_blinken_rot, led_und_buzzer_blinken_und_aus.
set_yellow_leds(count).
Dispatcher:
set_leds_based_on_mode(np, mode, first_red, volume_percent, log_path=None)
log_utils.py
init_logfile(sd_path="/sd", log_filename="debug_log.txt"): Erstellt/oeffnet Log, rotiert bei >512KB.
log_message(log_path, message, force=False, category=None):
Anti-Spam (1h fuer gleiche Messages), Kategorie-Filter, Fallback Konsole.
Helfer: error, debug, log_important, log_once_per_day, log_startup, log_config_change, log_system_status, log_alarm_event.
power_management.py
_load_settings(force_reload=False): Cache 5 Min; liest power_config.txt oder Default.
_time_to_minutes("HH:MM"): Minuten seit 00:00.
should_display_be_on(hour, minute, log_path=None):
Auto-Fenster Ein/Aus inkl. Mitternacht-ueberschlag; liefert (is_on_time, brightness).
is_display_manually_toggled(): aktuell immer True (Platzhalter).
reload_settings(): Cache invalidieren.
recovery_manager.py
Watchdog-Init (8s), feed_watchdog, check_system_health (Reset bei >5 Min Inaktivitaet), emergency_recovery, activity_heartbeat.
memory_monitor.py
record_boot_memory, monitor_memory(log_path=None, force_gc=False, context=""):
Periodische GC (3 Min), Trends, Warnungen, Notfallgrenze (<15MB? → in Bytes; Warnung unter 15.360 Bytes? Hier: 15KB, also Micropython-angepasst).
emergency_cleanup(log_path=None): Mehrere GC + sleeps.
get_memory_stats, dump_memory_history, analyze_memory_trend, analyze_memory_objects.
memory_diagnostics.py
diagnose_web_request_memory, diagnose_rtc_memory, diagnose_lcd_memory:
Messen von mem_free() vor/nach Operationen; Logging.
run_comprehensive_memory_diagnosis(log_path=None): Alle drei zusammenfassen.
diagnose_boot_memory_loss(log_path=None): Imports und Schritte tracken.
sdcard.py
Robuster MicroPython-kompatibler SPI SD-Treiber:
Init mit Retries, CMD-Sequenzen, CSD lesen, Kapazitaet/Typ, Lese/Schreib-Block-APIs, ioctl.
Zwei SPI-Geschwindigkeiten (Init/Normal).
char.py
ladebalken_erstellen(lcd): Definiert Custom Char 0 als Vollblock.
test_program.py
test_program(lcd, np, wlan, log_path=None, volume_percent=50):
LCD/LED Selbsttest-Sequenz mit Abbruch auf Joystick.
Hilfsfunktionen: _lcd_bar_char, _lcd_bar, _show_date, _blink_green, _smooth_blue, _refresh_clock, _run_led_tests, _finale.
DEVmountSD.py
Thonny-Testscript: SD initialisieren, mounten, Inhalt/Statistiken anzeigen, Schreib-/Lesetest.
Wichtige Beobachtungen und kleinere Bugs
Web UI Display-Settings Mismatch:

_save_display_settings_unsafe schreibt Keys: DISPLAY_AUTO, DISPLAY_ON_TIME, DISPLAY_OFF_TIME.
_load_display_settings liest diese korrekt.
ABER _send_display_block_safe verwendet aktuell settings.get('auto'/'on_time'/'off_time'), d. h. falsche Keys. Folge: Die Formularwerte zeigen Defaults statt gespeicherte Werte.
Fix: In _send_display_block_safe auf 'DISPLAY_AUTO'/'DISPLAY_ON_TIME'/'DISPLAY_OFF_TIME' umstellen.
Fehlende Route: JavaScript toggleLEDs() macht POST auf /toggle_leds, aber es gibt keinen Handler im Webserver.

Loesung: Route POST /toggle_leds implementieren und entweder:
ueber einen Callback oder globalen State clock_program.toggle_led_status(...) triggern, oder
eine geeignete Flag-Datei setzen, die run_clock_program zyklisch abfragt.
Doppelte Funktionen:

webserver_program.py enthaelt keine enable/disable_debug_mode Funktionen mehr.
Sicherheits-/Whitelist-Details:

alarm.txt und power_config.txt sind absichtlich safe=False — werden nicht direkt ausgespielt, nur per API. Gut.
wifis.txt ist explizit verboten. Gut.
Kleinigkeit LCD:

In diversen Orten wird lcd.clear() oft hintereinander aufgerufen; ist ok, aber kostet bei 4-bit I2C ein paar ms.
Joystick-Kalibrierung:

_measure_center() laeuft beim Import und misst 100 Samples (≈20 ms). In Ordnung, nur als Wissen.
Watchdog:

8 Sekunden Timeout ist maximal — das erfordert regelmaessiges feed_watchdog. Das geschieht in Hauptschleife und bei langen Transfers (Chunks → Watchdog-Feed). Gut.
Alarmparser:

reload_alarms begrenzt Alarme auf 10, Web-Formular auf 5. Konsistent halten (beide Seiten gleich begrenzen).
Dateiformat und Kontrakte
alarm.txt (mehrere Bloecke á 4 Zeilen plus ---):
TIME=HH:MM
TEXT=Text
DAYS=Mo,Di,Mi,Do,Fr,Sa,So oder “-” fuer alle Tage
STATUS=Aktiv|Inaktiv
Separator: ---
power_config.txt:
DISPLAY_AUTO=true|false
DISPLAY_ON_TIME=HH:MM
DISPLAY_OFF_TIME=HH:MM
Optional: BRIGHTNESS_DAY/BRIGHTNESS_NIGHT (Defaults im Code)
Edge Cases, die abgedeckt werden
SD-Karte fehlt/instabil: Mehrere Mount-Versuche, Testfile, sanfte Fallbacks, Logging zur Konsole.
WLAN nicht verfuegbar: Keine harte Abhaengigkeit; Webserver startet nur, wenn WLAN verbunden ist.
NTP-Fallback: Nutzt RTC bei Fehlern, verhindert Jahr 2000 Spruenge.
Speicherstress: Periodische GC, Trendanalyse, Emergency Cleanup.
I2C/RTC-Fehler: Retries und sinnvolle Fallbacks.
LED/NeoPixel: Einzel-LED-Fehler crashen nicht die gesamte Aktualisierung.