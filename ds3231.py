import machine


class RTC:
    """
    Minimal-Wrapper fuer den DS3231 (I²C).
    – maskiert 12-h-/Century-Bits
    – korrekter Wochentag-Index
    – liefert wahlweise Format-Strings oder Roh-Tuple
    """

    WDAY = [
        "Sonntag",
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
    ]

    def __init__(
        self, sda_pin=16, scl_pin=17, port=0, speed=100000, address=0x68, register=0x00
    ):
        self.addr = address
        self.reg = register
        sda = machine.Pin(sda_pin)
        scl = machine.Pin(scl_pin)
        self.i2c = machine.I2C(port, sda=sda, scl=scl, freq=speed)

    # ----------------------------------------------------------
    #   Low-Level Helfer
    # ----------------------------------------------------------
    @staticmethod
    def _bcd2bin(val):
        return val - 6 * (val >> 4)

    @staticmethod
    def _bin2bcd(val):
        return ((val // 10) << 4) + (val % 10)

    @staticmethod
    def _z(val):
        return "%02d" % val  # Null auffuellen

    # ----------------------------------------------------------
    #   Public API
    # ----------------------------------------------------------
    def set_time(self, sec, minute, hour, weekday, day, month, year):
        """Stellt die Uhr (24-h-Mode, weekday 1=So … 7=Sa, year 2000-2099)."""
        if not 2000 <= year <= 2099:
            raise ValueError("Year must be 2000-2099")

        data = bytes(
            (
                self._bin2bcd(sec & 0x7F),
                self._bin2bcd(minute & 0x7F),
                self._bin2bcd(hour & 0x3F),  # 24-h
                self._bin2bcd(weekday & 0x07),
                self._bin2bcd(day & 0x3F),
                self._bin2bcd(month & 0x1F),  # Century-Bit 0
                self._bin2bcd(year - 2000),
            )
        )
        self.i2c.writeto_mem(self.addr, self.reg, data)

    def read_time(self, mode=0):
        """
        Liest die Uhr.
        mode: 'DIN-1355-1' | 'DIN-1355-1+time' | 'ISO-8601' | 'time' | 'weekday'
        default 0 → Tuple (sec, min, hour, weekday, day, month, year)
        Fehler (I²C): None
        """
        try:
            buf = self.i2c.readfrom_mem(self.addr, self.reg, 7)
        except Exception:
            return None  # Leser kann pruefen: if x is None: ...

        # --- Maskieren & Dekodieren ---
        sec = self._bcd2bin(buf[0] & 0x7F)
        minute = self._bcd2bin(buf[1] & 0x7F)

        hr_raw = buf[2]
        if hr_raw & 0x40:  # 12-h-Mode
            pm = bool(hr_raw & 0x20)
            hour = self._bcd2bin(hr_raw & 0x1F)
            if pm and hour != 12:
                hour += 12
            if not pm and hour == 12:
                hour = 0
        else:  # 24-h
            hour = self._bcd2bin(hr_raw & 0x3F)

        weekday = self._bcd2bin(buf[3] & 0x07)  # 1-7
        day = self._bcd2bin(buf[4] & 0x3F)
        month = self._bcd2bin(buf[5] & 0x1F)
        year = self._bcd2bin(buf[6]) + 2000

        # --- Formatierte Ausgaben ---
        if mode == "DIN-1355-1":
            return "%s.%s.%d" % (self._z(day), self._z(month), year)

        if mode == "DIN-1355-1+time":
            return "%s.%s.%d %s:%s:%s" % (
                self._z(day),
                self._z(month),
                year,
                self._z(hour),
                self._z(minute),
                self._z(sec),
            )

        if mode == "ISO-8601":
            return "%d-%s-%s" % (year, self._z(month), self._z(day))

        if mode == "time":
            return "%s:%s:%s" % (self._z(hour), self._z(minute), self._z(sec))

        if mode == "weekday":
            return self.WDAY[(weekday - 1) % 7]

        # default: Roh-Tuple
        return sec, minute, hour, weekday, day, month, year
