# LCD_API.py
import time


class LcdApi:
    # -----------------------------------------------------------------
    #  HD44780 / ST7066U Instruction Set  (Bitmask-Variante)
    # -----------------------------------------------------------------
    LCD_CLR = 0x01  # clear display, return home
    LCD_HOME = 0x02  # return home (w/ current DDRAM)
    LCD_ENTRY_MODE = 0x04
    LCD_ENTRY_INC = 0x02
    LCD_ENTRY_SHIFT = 0x01

    LCD_ON_CTRL = 0x08
    LCD_ON_DISPLAY = 0x04
    LCD_ON_CURSOR = 0x02
    LCD_ON_BLINK = 0x01

    LCD_MOVE = 0x10
    LCD_MOVE_DISP = 0x08
    LCD_MOVE_RIGHT = 0x04

    LCD_FUNCTION = 0x20
    LCD_FUNCTION_8BIT = 0x10
    LCD_FUNCTION_2LINES = 0x08
    LCD_FUNCTION_10DOTS = 0x04
    LCD_FUNCTION_RESET = 0x30  # special reset sequence

    LCD_CGRAM = 0x40
    LCD_DDRAM = 0x80

    # RS / RW states
    LCD_RS_CMD = 0
    LCD_RS_DATA = 1
    LCD_RW_WRITE = 0
    LCD_RW_READ = 1

    # -----------------------------------------------------------------
    #   Init
    # -----------------------------------------------------------------
    def __init__(self, num_lines, num_columns):
        self.num_lines = min(4, num_lines)
        self.num_columns = min(40, num_columns)
        self.cursor_x = 0
        self.cursor_y = 0
        self.backlight = 1  # int, nicht bool (Kompat. zu shifts)

        self.display_off()
        self.backlight_on()
        self.clear()
        self.hal_write_command(self.LCD_ENTRY_MODE | self.LCD_ENTRY_INC)
        self.hide_cursor()
        self.display_on()

    # -----------------------------------------------------------------
    #   High-Level API
    # -----------------------------------------------------------------
    def clear(self):
        """Clear display + Cursor Home (1 Befehl genuegt)."""
        self.hal_write_command(self.LCD_CLR)  # 4.1 ms delay in HAL
        self.cursor_x = 0
        self.cursor_y = 0

    # --- Cursor Sichtbarkeit -----------------------------------------
    def show_cursor(self):
        self.hal_write_command(
            self.LCD_ON_CTRL | self.LCD_ON_DISPLAY | self.LCD_ON_CURSOR
        )

    def hide_cursor(self):
        self.hal_write_command(self.LCD_ON_CTRL | self.LCD_ON_DISPLAY)

    def blink_cursor_on(self):
        self.hal_write_command(
            self.LCD_ON_CTRL
            | self.LCD_ON_DISPLAY
            | self.LCD_ON_CURSOR
            | self.LCD_ON_BLINK
        )

    def blink_cursor_off(self):
        self.hal_write_command(
            self.LCD_ON_CTRL | self.LCD_ON_DISPLAY | self.LCD_ON_CURSOR
        )

    # --- Display an/aus ----------------------------------------------
    def display_on(self):
        self.hal_write_command(self.LCD_ON_CTRL | self.LCD_ON_DISPLAY)

    def display_off(self):
        self.hal_write_command(self.LCD_ON_CTRL)

    # --- Backlight ----------------------------------------------------
    def backlight_on(self):
        self.backlight = 1
        self.hal_backlight_on()

    def backlight_off(self):
        self.backlight = 0
        self.hal_backlight_off()

    # -----------------------------------------------------------------
    #   Position & Schreiben
    # -----------------------------------------------------------------
    def move_to(self, cursor_x, cursor_y):
        self.cursor_x = cursor_x % self.num_columns
        self.cursor_y = cursor_y % self.num_lines
        addr = self.cursor_x & 0x3F
        if self.cursor_y & 1:
            addr += 0x40
        if self.cursor_y & 2:
            addr += 0x14
        self.hal_write_command(self.LCD_DDRAM | addr)

    def putchar(self, char):
        if char != "\n":
            self.hal_write_data(ord(char))
            self.cursor_x += 1
        if self.cursor_x >= self.num_columns or char == "\n":
            self.cursor_x = 0
            self.cursor_y = (self.cursor_y + 1) % self.num_lines
            self.move_to(self.cursor_x, self.cursor_y)

    def putstr(self, string, _max=256):
        """
        Schreibt String auf das LCD, maximal _max Zeichen
        (Schutz gegen versehentliche Riesen-Strings).
        """
        for char in string[:_max]:
            self.putchar(char)

    # -----------------------------------------------------------------
    #   CGRAM / Custom Characters
    # -----------------------------------------------------------------
    def custom_char(self, location, charmap):
        location &= 0x7
        self.hal_write_command(self.LCD_CGRAM | (location << 3))
        self.hal_sleep_us(40)
        try:
            for row in charmap[:8]:
                self.hal_write_data(row)
                self.hal_sleep_us(40)
        except Exception as e:
            # Fehler weiterwerfen, damit Caller loggen kann
            raise e
        finally:
            # Cursor zurueck
            self.move_to(self.cursor_x, self.cursor_y)

    # -----------------------------------------------------------------
    #   HAL-Platzhalter – von abgeleiteter Klasse zu implementieren
    # -----------------------------------------------------------------
    def hal_backlight_on(self):
        pass

    def hal_backlight_off(self):
        pass

    def hal_write_command(self, cmd):
        raise NotImplementedError

    def hal_write_data(self, data):
        raise NotImplementedError

    def hal_sleep_us(self, usecs):
        time.sleep_us(usecs)
