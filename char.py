# char.py
def ladebalken_erstellen(lcd):
    full_block = [
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
    ]
    lcd.custom_char(0, full_block)
