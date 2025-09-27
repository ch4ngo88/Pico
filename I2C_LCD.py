from LCD_API import LcdApi
from time import sleep
from machine import I2C

# ---------------------------------------------------------------------
#      PCF8574-Pin-Belegung
# ---------------------------------------------------------------------
MASK_RS = 0x01
MASK_RW = 0x02
MASK_E = 0x04
SHIFT_BACKLIGHT = 3
SHIFT_DATA = 4  # D4-D7 → PCF8574 Bit4-Bit7


def sleep_ms(ms):
    sleep(ms / 1000)


class I2CLcd(LcdApi):
    """HAL-Klasse für HD44780 über PCF8574 (LCD1602/2004)."""

    # --------------------------------------------------------------
    #   Initialisierung
    # --------------------------------------------------------------
    def __init__(self, i2c: I2C, i2c_addr: int, num_lines: int, num_columns: int):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.backlight = 1  # 1 = AN, 0 = AUS

        self._write(0x00)  # alle Pins Low
        sleep_ms(20)

        # Reset-Sequenz (3×)
        for _ in range(3):
            self._hal_write_init_nibble(self.LCD_FUNCTION_RESET)
            sleep_ms(5 if _ == 0 else 1)

        # 4-Bit-Mode aktivieren
        self._hal_write_init_nibble(self.LCD_FUNCTION)
        sleep_ms(1)

        # Basisklasse initialisieren
        super().__init__(num_lines, num_columns)

        # 2-Zeilen-Flag, falls nötig
        cmd = self.LCD_FUNCTION
        if num_lines > 1:
            cmd |= self.LCD_FUNCTION_2LINES
        self.hal_write_command(cmd)

    # --------------------------------------------------------------
    #   Backlight-Handling
    # --------------------------------------------------------------
    def hal_backlight_on(self):
        self.backlight = 1
        self._write(1 << SHIFT_BACKLIGHT)

    def hal_backlight_off(self):
        self.backlight = 0
        self._write(0x00)

    # --------------------------------------------------------------
    #   Low-Level-Writes
    # --------------------------------------------------------------
    def _write(self, byte):
        """I²C-Write mit einfachem OSError-Catch (Bus hängt)."""
        try:
            self.i2c.writeto(self.i2c_addr, bytearray([byte]))
        except OSError:
            # kurzer Bus-Stall – in der Praxis reicht ein µs-Delay
            sleep_ms(1)
            self.i2c.writeto(self.i2c_addr, bytearray([byte]))

    def _hal_write_init_nibble(self, nibble):
        """Nur während des Resets verwendet."""
        byte = (((nibble >> 4) & 0x0F) << SHIFT_DATA) | (
            self.backlight << SHIFT_BACKLIGHT
        )
        self._write(byte | MASK_E)
        self._write(byte)

    # --------------------------------------------------------------
    #   Öffentliche HAL-Funktionen für LcdApi
    # --------------------------------------------------------------
    def hal_write_command(self, cmd):
        high = (((cmd >> 4) & 0x0F) << SHIFT_DATA) | (self.backlight << SHIFT_BACKLIGHT)
        low = (((cmd) & 0x0F) << SHIFT_DATA) | (self.backlight << SHIFT_BACKLIGHT)

        for half in (high, low):
            self._write(half | MASK_E)
            self._write(half)

        if cmd <= 3:  # HOME / CLEAR
            sleep_ms(5)

    def hal_write_data(self, data):
        high = (
            MASK_RS
            | (self.backlight << SHIFT_BACKLIGHT)
            | (((data >> 4) & 0x0F) << SHIFT_DATA)
        )
        low = (
            MASK_RS
            | (self.backlight << SHIFT_BACKLIGHT)
            | ((data & 0x0F) << SHIFT_DATA)
        )

        for half in (high, low):
            self._write(half | MASK_E)
            self._write(half)
