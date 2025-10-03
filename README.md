# 🏠 Neuza's Smart Wecker 💖

> *Ein liebevolles Projekt fuer meine Tochter Neuza, damit sie puenktlich aufsteht und einen guten Start in den Schultag hat* ❤️

![Status: In Betrieb](https://img.shields.io/badge/Status-In%20Betrieb-green)
![Platform: Raspberry Pi Pico](https://img.shields.io/badge/Platform-Raspberry%20Pi%20Pico-blue)
![Language: MicroPython](https://img.shields.io/badge/Language-MicroPython-yellow)
![Made with: Love](https://img.shields.io/badge/Made%20with-❤️%20Love-red)

## 🎯 Das Projekt

Dieser intelligente Wecker wurde speziell fuer meine Tochter Neuza entwickelt und ist taeglich im Einsatz! Das Gehaeuse besteht aus **Lego-Bausteinen** - perfekt fuer ein Kinderzimmer und robust genug fuer den taeglichen Gebrauch.

### ✨ Was macht diesen Wecker besonders?

- **Liebevoll personalisiert**: Mit Neuzas Foto und personalisierten Wecknachrichten
- **Kinderfreundlich**: Einfache Joystick-Bedienung und bunte LED-Anzeigen
- **Robust & spielerisch**: Lego-Gehaeuse laedt zum Entdecken ein
- **Smart & flexibel**: Web-Interface fuer Eltern zur einfachen Konfiguration
- **Zuverlaessig**: Offline-faehig mit Backup-Funktionen

## 🛠️ Hardware-Ausstattung

### Hauptkomponenten
- **Raspberry Pi Pico** - Das Herzstueck
- **DS3231 RTC-Modul** - Praezise Zeitmessung auch ohne Strom
- **16x2 I2C LCD-Display** - Klare, gut lesbare Anzeige
- **8x NeoPixel LED-Ring** - Bunte Beleuchtungseffekte
- **Analoger Joystick** - Intuitive Steuerung
- **Buzzer/Lautsprecher** - Melodische Wecktoene
- **MicroSD-Karte** - Lokale Datenspeicherung
- **Status-LEDs** - Visuelle Systemanzeigen

### 🧱 Das Lego-Gehaeuse
Das gesamte System ist in ein **selbst gebautes Lego-Gehaeuse** integriert, das:
- Alle Komponenten sicher aufnimmt
- Kinderfreundlich und robust ist
- Einfachen Zugang fuer Wartung bietet
- Perfekt ins Kinderzimmer passt

## 🚀 Funktionen im Detail

### ⏰ Intelligentes Alarm-System
```
📅 Wochentags-spezifische Alarme
🎵 Melodische Wecktoene (keine harten Pieptoene!)
💬 Personalisierte Wecknachrichten
🔄 Automatische Snooze-Funktion
📊 Verpasste-Alarme-Erkennung
```

### 🌈 LED-Zeitanzeige
- **Stundenanzeige**: LEDs zeigen die aktuelle Stunde an
- **Nachtmodus**: Automatische Helligkeit je nach Tageszeit
- **Alarm-Animation**: Blinkende rote LEDs beim Weckruf
- **Status-Feedback**: Verschiedene Farben fuer System-Status

### 🕹️ Joystick-Steuerung
```
⬅️➡️ Lautstaerke anpassen
⬆️⬇️ Menue aufrufen
🔘 Alarm stoppen / Bestaetigen
```

### 🌐 Web-Interface
Ein liebevoll gestaltetes Web-Interface mit **Neuzas Foto** ermoeglicht:
- 📝 Alarme hinzufuegen/bearbeiten
- ⏰ Weckzeiten fuer jeden Wochentag setzen
- 💬 Persoenliche Wecknachrichten erstellen
- 🔧 Display-Einstellungen anpassen
- 📊 System-Status ueberwachen

### 🔋 Power-Management
- **Automatischer Nachtmodus**: Display dimmt sich nachts automatisch
- **Energiesparfunktionen**: Optimierte Stromnutzung
- **Batterie-Backup**: RTC laeuft auch bei Stromausfall weiter

## 📁 Projekt-Struktur

```
Pico/
├── 🏠 main.py                 # Hauptprogramm & System-Start
├── ⏰ clock_program.py        # Uhr-Logik & Alarm-System
├── 🌐 webserver_program.py    # Web-Interface & HTTP-Server
├── 🕹️ joystick.py             # Joystick-Steuerung
├── 🎵 sound_config.py         # Melodien & Toene
├── ⏱️ time_config.py          # Zeit-Synchronisation (NTP/RTC)
├── 💾 sdcard.py               # SD-Karten-Management
├── 🌈 neopixel.py             # LED-Ring-Steuerung
├── 📺 I2C_LCD.py              # LCD-Display-Treiber
├── 🔧 ds3231.py               # RTC-Modul-Treiber
├── 📊 log_utils.py            # Logging-System
├── ⚡ power_management.py     # Energie-Management
├── 🛡️ recovery_manager.py     # System-ueberwachung
├── 💾 memory_monitor.py       # Speicher-ueberwachung
├── 🎨 char.py                 # LCD-Sonderzeichen
├── 🧪 test_program.py         # Hardware-Tests
├── 📁 sd/                     # SD-Karten-Daten
│   ├── ⏰ alarm.txt           # Gespeicherte Alarme
│   ├── 📝 debug_log.txt       # System-Logs
│   ├── ⚡ power_config.txt    # Power-Einstellungen
│   └── 📶 wifis.txt           # WLAN-Zugangsdaten
└── 🎨 web_assets/             # Web-Interface Dateien
    ├── 🖼️ neuza.webp          # Neuzas Foto
    ├── 🎨 styles.css          # Stylesheets
    └── 🏠 favicon.ico         # Website-Icon
```

## 🔧 Installation & Setup

### 1. Hardware vorbereiten
```bash
# Raspberry Pi Pico mit MicroPython flashen
# Alle Komponenten nach Schaltplan verbinden
# Lego-Gehaeuse zusammenbauen
```

### 2. Software installieren
```bash
# Alle Python-Dateien auf den Pico kopieren
# SD-Karte mit Ordnerstruktur vorbereiten
# WLAN-Zugangsdaten in /sd/wifis.txt eintragen
```

### 3. Konfiguration
```bash
# Alarm-Zeiten ueber Web-Interface einstellen
# Persoenliche Nachrichten hinzufuegen
# Display-Zeiten nach Schlafenszeiten anpassen
# LED Power Modus in /sd/power_config.txt setzen (LED_POWER_MODE=normal|boost)
# Lautstaerke-Profile in /sd/power_config.txt pflegen (VOLUME_DEFAULT/VOLUME_NIGHT)
```

## 🎵 Besondere Features

### 🎼 Melodische Wecktoene
Statt harter Pieptoene spielt der Wecker sanfte Melodien:
- **"Fuer Elise"** von Beethoven beim Systemstart
- **Windows XP Start-Sound** als Bestaetigungston
- **Sanfte Alarm-Melodie** zum Aufwachen

### 💬 Personalisierte Nachrichten
Beispiel-Nachrichten fuer Neuza:
```
06:45 - "Guten Morgen :)"
07:15 - "Hab einen schoenen Tag!"
19:45 - "Bettzeit! Schlaf gut."
```

### 🌈 Intelligente LED-Anzeige
- **Ruhemodus**: Sanftes blaues Licht
- **Weckzeit**: Blinkende rote LEDs
- **Menue-Navigation**: Gruene Bestaetigung
- **Stundenanzeige**: Entsprechende Anzahl LEDs leuchtet

## 🔧 System-Monitoring

Das System ueberwacht sich selbst und protokolliert alles:

### 📊 Automatische ueberwachung
- **Speicher-Management**: Verhindert Abstuerze durch Speichermangel
- **Watchdog-System**: Automatischer Neustart bei Problemen
- **Gesundheits-Checks**: Regelmaessige System-Diagnose
- **Error-Recovery**: Intelligente Fehlerbehandlung

### 📝 Logging-System
```
Systemstart: ✅ SD: ✓ Sound: ✓ LEDs: ✓ Joy: ✓ WiFi: ✓
Alarm ausgeloest: 06:45 "Guten Morgen :)"
WLAN verbunden: MeinNetzwerk
Zeit synchronisiert: NTP erfolgreich
```

## 🌐 Web-Interface

Das Web-Interface ist speziell fuer Neuza gestaltet:
- **Ihr Foto** als zentrales Element
- **Kindgerechte Farben** (Rosa/Pink-Toene)
- **Einfache Bedienung** fuer Eltern
- **Responsive Design** fuer Handy & Tablet

### Funktionen:
- ✏️ Alarme bearbeiten
- 📅 Wochentage auswaehlen
- 💬 Nachrichten personalisieren
- ⚙️ Display-Einstellungen
- 🔧 System-Debug-Infos

## 🛠️ Technische Details

### Hardware-Pins
```python
# Display & Sensoren
LCD_SDA = Pin(14)    # I2C fuer LCD
LCD_SCL = Pin(15)    # I2C fuer LCD
RTC_SDA = Pin(20)    # I2C fuer RTC
RTC_SCL = Pin(21)    # I2C fuer RTC

# Joystick
JOYSTICK_VRX = Pin(26)  # ADC0 - X-Achse
JOYSTICK_VRY = Pin(27)  # ADC1 - Y-Achse  
JOYSTICK_SW = Pin(22)   # Button

# Audio & LEDs
BUZZER = Pin(16)        # PWM fuer Toene
NEOPIXEL = Pin(28)      # LED-Ring
STATUS_LED = Pin(25)    # Interne LED
BLUE_LED = Pin(13)      # Webserver-Status

# SD-Karte
SD_SCK = Pin(6)      # SPI Clock
SD_MOSI = Pin(7)     # SPI Data Out
SD_MISO = Pin(4)     # SPI Data In
SD_CS = Pin(5)       # Chip Select
```

### Software-Architektur
- **Modular aufgebaut**: Jede Funktion in eigenem Modul
- **Robust & fehlertolerant**: Umfangreiche Fehlerbehandlung
- **Memory-optimiert**: Fuer 264KB RAM des Pico optimiert
- **Event-driven**: Reaktiv auf Benutzer-Eingaben

## 💝 Das Herzstueck

Dieses Projekt ist mehr als nur ein Wecker - es ist ein **taeglicher Liebesbeweis**:

- 🌅 **Jeden Morgen** weckt Neuza eine liebevolle Nachricht
- 🏠 Das **Lego-Gehaeuse** macht den Wecker zu einem Spielzeug
- 🎨 Das **personalisierte Interface** zeigt, dass es nur fuer sie ist  
- ⏰ Die **sanften Melodien** sorgen fuer einen entspannten Start
- 💤 Der **Nachtmodus** stoert ihren Schlaf nicht

## 🚀 Status: Im taeglichen Einsatz!

**Betriebszeit**: Seit Installation laeuft der Wecker zuverlaessig jeden Tag
**Erfolgsrate**: 100% - Neuza steht puenktlich auf! 🎉
**Zufriedenheit**: Beide daumen hoch von Neuza 👍👍

## 🛠️ Wartung & Erweiterungen

### Geplante Features
- [ ] 🎮 Mini-Spiele zur Motivation
- [ ] 📱 Handy-App fuer Remote-Steuerung  
- [ ] 🌡️ Temperatur-Anzeige
- [ ] 📊 Schlafmuster-Analyse
- [ ] 🎵 Mehr Melodie-Optionen

### Wartung
- 🔋 Gelegentlich SD-Karte auf freien Speicher pruefen
- 🧹 Log-Dateien bei Bedarf archivieren
- ⚡ Bei WLAN-aenderungen neue Zugangsdaten eintragen

## 📞 Support

Bei Fragen oder Problemen:
- 📝 Debug-Logs in `/sd/debug_log.txt` pruefen (auch ueber Web: Menue → Logs)
- 🔄 Bei Problemen: Joystick 2 Sekunden gedrueckt halten fuer Neustart

---

*Gemacht mit ❤️ fuer Neuza - moege jeder Morgen mit einem Laecheln beginnen! 🌅*

**"Der beste Wecker ist der, der aus Liebe gemacht wurde"** 💕