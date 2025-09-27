# neopixel_wrapper.py   (ersetzt deine alte Datei 1-zu-1)
import array
import time
from machine import Pin
import rp2


# --------------------------------------------------------------------
#   PIO-Programm  (unverändert)
# --------------------------------------------------------------------
@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24,
)
def ws2812():
    T1, T2, T3 = 2, 5, 8
    wrap_target()  # noqa: F821 - provided by rp2.asm_pio
    label("bitloop")  # noqa: F821 - provided by rp2.asm_pio
    out(x, 1).side(0)[T3 - 1]  # noqa: F821 - provided by rp2.asm_pio
    jmp(not_x, "do_zero").side(1)[T1 - 1]  # noqa: F821 - provided by rp2.asm_pio
    jmp("bitloop").side(1)[T2 - 1]  # noqa: F821 - provided by rp2.asm_pio
    label("do_zero")  # noqa: F821 - provided by rp2.asm_pio
    nop().side(0)[T2 - 1]  # noqa: F821 - provided by rp2.asm_pio
    wrap  # noqa: F821 - provided by rp2.asm_pio


# --------------------------------------------------------------------
#   NeoPixel-Klasse
# --------------------------------------------------------------------
class myNeopixel:
    """Minimaler NeoPixel-Ring-Wrapper für RP2040-PIO."""

    def __init__(self, num_leds, pin, delay_ms=0):
        self.num_leds = num_leds
        self.delay_ms = delay_ms
        self._brightness = 64

        self.pixels = array.array("I", [0] * num_leds)
        self.sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(pin))
        self.sm.active(1)

    # --------------------------------------------------------------
    #   Brightness
    # --------------------------------------------------------------
    def brightness(self, value=None):
        """Getter/Setter (1-255)."""
        if value is None:
            return self._brightness
        value = 1 if value < 1 else 255 if value > 255 else value
        self._brightness = value
        return self._brightness

    # --------------------------------------------------------------
    #   Pixel-Operationen
    # --------------------------------------------------------------
    def _clamp_idx(self, idx):
        return 0 <= idx < self.num_leds

    def set_pixel(self, idx, r, g, b):
        """Einzel-Pixel setzen (RGB)."""
        if not self._clamp_idx(idx):
            return
        scale = self._brightness / 255
        self.pixels[idx] = int(b * scale) | int(r * scale) << 8 | int(g * scale) << 16

    def set_pixel_line(self, start, end, r, g, b):
        for i in range(start, end + 1):
            self.set_pixel(i, r, g, b)

    def set_pixel_line_gradient(self, p1, p2, lr, lg, lb, rr, rg, rb):
        if p1 == p2:
            return
        left, right = sorted((p1, p2))
        span = right - left
        for i in range(span + 1):
            frac = i / span
            self.set_pixel(
                left + i,
                round((rr - lr) * frac + lr),
                round((rg - lg) * frac + lg),
                round((rb - lb) * frac + lb),
            )

    # --------------------------------------------------------------
    #   Fill & Rotate
    # --------------------------------------------------------------
    def fill(self, r, g, b):
        """Alle Pixel puffern (show() separat!)."""
        for i in range(self.num_leds):
            self.set_pixel(i, r, g, b)

    def _rotate(self, steps):
        steps %= self.num_leds
        if steps:
            self.pixels[:] = self.pixels[-steps:] + self.pixels[:-steps]

    def rotate_left(self, n=1):
        self._rotate(-n)

    def rotate_right(self, n=1):
        self._rotate(n)

    # --------------------------------------------------------------
    #   Ausgabe
    # --------------------------------------------------------------
    def show(self):
        put = self.sm.put
        for pix in self.pixels:
            put(pix, 8)
        if self.delay_ms:
            time.sleep_ms(self.delay_ms)
