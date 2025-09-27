# 🏠 Neuza's Smart Wecker 💖

> *Ein liebevolles Projekt für meine Tochter Neuza, damit sie pünktlich aufsteht und einen guten Start in den Schultag hat* ❤️

![Status: In Betrieb](https://img.shields.io/badge/Status-In%20Betrieb-green)
![Platform: Raspberry Pi Pico](https://img.shields.io/badge/Platform-Raspberry%20Pi%20Pico-blue)
![Language: MicroPython](https://img.shields.io/badge/Language-MicroPython-yellow)
![Made with: Love](https://img.shields.io/badge/Made%20with-❤️%20Love-red)

## 🎯 Das Projekt

Dieser intelligente Wecker wurde speziell für meine Tochter Neuza entwickelt und ist täglich im Einsatz! Das Gehäuse besteht aus **Lego-Bausteinen** - perfekt für ein Kinderzimmer und robust genug für den täglichen Gebrauch.

### ✨ Was macht diesen Wecker besonders?

- **Liebevoll personalisiert**: Mit Neuzas Foto und personalisierten Wecknachrichten
- **Kinderfreundlich**: Einfache Joystick-Bedienung und bunte LED-Anzeigen
- **Robust & spielerisch**: Lego-Gehäuse lädt zum Entdecken ein
- **Smart & flexibel**: Web-Interface für Eltern zur einfachen Konfiguration
- **Zuverlässig**: Offline-fähig mit Backup-Funktionen

## 🛠️ Hardware-Ausstattung

### Hauptkomponenten
- **Raspberry Pi Pico** - Das Herzstück
- **DS3231 RTC-Modul** - Präzise Zeitmessung auch ohne Strom
- **16x2 I2C LCD-Display** - Klare, gut lesbare Anzeige
- **8x NeoPixel LED-Ring** - Bunte Beleuchtungseffekte
- **Analoger Joystick** - Intuitive Steuerung
- **Buzzer/Lautsprecher** - Melodische Wecktöne
- **MicroSD-Karte** - Lokale Datenspeicherung
- **Status-LEDs** - Visuelle Systemanzeigen

### 🧱 Das Lego-Gehäuse
Das gesamte System ist in ein **selbst gebautes Lego-Gehäuse** integriert, das:
- Alle Komponenten sicher aufnimmt
- Kinderfreundlich und robust ist
- Einfachen Zugang für Wartung bietet
- Perfekt ins Kinderzimmer passt

## 🚀 Funktionen im Detail

### ⏰ Intelligentes Alarm-System
```
📅 Wochentags-spezifische Alarme
🎵 Melodische Wecktöne (keine harten Pieptöne!)
💬 Personalisierte Wecknachrichten
🔄 Automatische Snooze-Funktion
📊 Verpasste-Alarme-Erkennung
```

### 🌈 LED-Zeitanzeige
- **Stundenanzeige**: LEDs zeigen die aktuelle Stunde an
- **Nachtmodus**: Automatische Helligkeit je nach Tageszeit
- **Alarm-Animation**: Blinkende rote LEDs beim Weckruf
- **Status-Feedback**: Verschiedene Farben für System-Status

### 🕹️ Joystick-Steuerung
```
⬅️➡️ Lautstärke anpassen
⬆️⬇️ Menü aufrufen
🔘 Alarm stoppen / Bestätigen
```

### 🌐 Web-Interface
Ein liebevoll gestaltetes Web-Interface mit **Neuzas Foto** ermöglicht:
- 📝 Alarme hinzufügen/bearbeiten
- ⏰ Weckzeiten für jeden Wochentag setzen
- 💬 Persönliche Wecknachrichten erstellen
- 🔧 Display-Einstellungen anpassen
- 📊 System-Status überwachen

### 🔋 Power-Management
- **Automatischer Nachtmodus**: Display dimmt sich nachts automatisch
- **Energiesparfunktionen**: Optimierte Stromnutzung
- **Batterie-Backup**: RTC läuft auch bei Stromausfall weiter

## 📁 Projekt-Struktur

```
Pico/
├── 🏠 main.py                 # Hauptprogramm & System-Start
├── ⏰ clock_program.py        # Uhr-Logik & Alarm-System
├── 🌐 webserver_program.py    # Web-Interface & HTTP-Server
├── 🕹️ joystick.py             # Joystick-Steuerung
├── 🎵 sound_config.py         # Melodien & Töne
├── ⏱️ time_config.py          # Zeit-Synchronisation (NTP/RTC)
├── 💾 sdcard.py               # SD-Karten-Management
├── 🌈 neopixel.py             # LED-Ring-Steuerung
├── 📺 I2C_LCD.py              # LCD-Display-Treiber
├── 🔧 ds3231.py               # RTC-Modul-Treiber
├── 📊 log_utils.py            # Logging-System
├── ⚡ power_management.py     # Energie-Management
├── 🛡️ recovery_manager.py     # System-Überwachung
├── 💾 memory_monitor.py       # Speicher-Überwachung
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
# Lego-Gehäuse zusammenbauen
```

### 2. Software installieren
```bash
# Alle Python-Dateien auf den Pico kopieren
# SD-Karte mit Ordnerstruktur vorbereiten
# WLAN-Zugangsdaten in /sd/wifis.txt eintragen
```

### 3. Konfiguration
```bash
# Alarm-Zeiten über Web-Interface einstellen
# Persönliche Nachrichten hinzufügen
# Display-Zeiten nach Schlafenszeiten anpassen
```

## 🎵 Besondere Features

### 🎼 Melodische Wecktöne
Statt harter Pieptöne spielt der Wecker sanfte Melodien:
- **"Für Elise"** von Beethoven beim Systemstart
- **Windows XP Start-Sound** als Bestätigungston
- **Sanfte Alarm-Melodie** zum Aufwachen

### 💬 Personalisierte Nachrichten
Beispiel-Nachrichten für Neuza:
```
06:45 - "Guten Morgen :)"
07:15 - "Hab einen schönen Tag!"
19:45 - "Bettzeit! Schlaf gut."
```

### 🌈 Intelligente LED-Anzeige
- **Ruhemodus**: Sanftes blaues Licht
- **Weckzeit**: Blinkende rote LEDs
- **Menü-Navigation**: Grüne Bestätigung
- **Stundenanzeige**: Entsprechende Anzahl LEDs leuchtet

## 🔧 System-Monitoring

Das System überwacht sich selbst und protokolliert alles:

### 📊 Automatische Überwachung
- **Speicher-Management**: Verhindert Abstürze durch Speichermangel
- **Watchdog-System**: Automatischer Neustart bei Problemen
- **Gesundheits-Checks**: Regelmäßige System-Diagnose
- **Error-Recovery**: Intelligente Fehlerbehandlung

### 📝 Logging-System
```
Systemstart: ✅ SD: ✓ Sound: ✓ LEDs: ✓ Joy: ✓ WiFi: ✓
Alarm ausgelöst: 06:45 "Guten Morgen :)"
WLAN verbunden: MeinNetzwerk
Zeit synchronisiert: NTP erfolgreich
```

## 🌐 Web-Interface

Das Web-Interface ist speziell für Neuza gestaltet:
- **Ihr Foto** als zentrales Element
- **Kindgerechte Farben** (Rosa/Pink-Töne)
- **Einfache Bedienung** für Eltern
- **Responsive Design** für Handy & Tablet

### Funktionen:
- ✏️ Alarme bearbeiten
- 📅 Wochentage auswählen
- 💬 Nachrichten personalisieren
- ⚙️ Display-Einstellungen
- 🔧 System-Debug-Infos

## 🛠️ Technische Details

### Hardware-Pins
```python
# Display & Sensoren
LCD_SDA = Pin(14)    # I2C für LCD
LCD_SCL = Pin(15)    # I2C für LCD
RTC_SDA = Pin(20)    # I2C für RTC
RTC_SCL = Pin(21)    # I2C für RTC

# Joystick
JOYSTICK_VRX = Pin(26)  # ADC0 - X-Achse
JOYSTICK_VRY = Pin(27)  # ADC1 - Y-Achse  
JOYSTICK_SW = Pin(22)   # Button

# Audio & LEDs
BUZZER = Pin(16)        # PWM für Töne
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
- **Memory-optimiert**: Für 264KB RAM des Pico optimiert
- **Event-driven**: Reaktiv auf Benutzer-Eingaben

## 💝 Das Herzstück

Dieses Projekt ist mehr als nur ein Wecker - es ist ein **täglicher Liebesbeweis**:

- 🌅 **Jeden Morgen** weckt Neuza eine liebevolle Nachricht
- 🏠 Das **Lego-Gehäuse** macht den Wecker zu einem Spielzeug
- 🎨 Das **personalisierte Interface** zeigt, dass es nur für sie ist  
- ⏰ Die **sanften Melodien** sorgen für einen entspannten Start
- 💤 Der **Nachtmodus** stört ihren Schlaf nicht

## 🚀 Status: Im täglichen Einsatz!

**Betriebszeit**: Seit Installation läuft der Wecker zuverlässig jeden Tag
**Erfolgsrate**: 100% - Neuza steht pünktlich auf! 🎉
**Zufriedenheit**: Beide daumen hoch von Neuza 👍👍

## 🛠️ Wartung & Erweiterungen

### Geplante Features
- [ ] 🎮 Mini-Spiele zur Motivation
- [ ] 📱 Handy-App für Remote-Steuerung  
- [ ] 🌡️ Temperatur-Anzeige
- [ ] 📊 Schlafmuster-Analyse
- [ ] 🎵 Mehr Melodie-Optionen

### Wartung
- 🔋 Gelegentlich SD-Karte auf freien Speicher prüfen
- 🧹 Log-Dateien bei Bedarf archivieren
- ⚡ Bei WLAN-Änderungen neue Zugangsdaten eintragen

## 📞 Support

Bei Fragen oder Problemen:
- 📝 Debug-Logs in `/sd/debug_log.txt` prüfen
- 🌐 Web-Interface `/debug` für System-Status
- 🔄 Bei Problemen: Joystick 2 Sekunden gedrückt halten für Neustart

---

*Gemacht mit ❤️ für Neuza - möge jeder Morgen mit einem Lächeln beginnen! 🌅*

**"Der beste Wecker ist der, der aus Liebe gemacht wurde"** 💕