"""
sdcard.py – SPI-Treiber für SD-/microSD-Karten (MicroPython)

* 100 % API-kompatibel zu MicroPythons Original
* Init robuster (groessere Timeouts + mehrere CMD0-Versuche)
* optionale Karten­typ-Abfrage (ioctl op==6)
* universelle write()-/write_token()-Variante (keine SPI.read())
"""

from micropython import const
import time

# ---------------- Parameter, die Du bei Bedarf anpassen kannst ------------
_CMD_TIMEOUT = const(200)  # Loops á 1 ms  →  0–200 ms
_INIT_RETRIES = const(8)  # Wie oft CMD0/CMD8-Sequenz probieren
_INIT_CLK_HZ = 100_000  # SPI-Takt während Init
_DATA_CLK_HZ = 4_000_000  # SPI-Takt nach erfolgreichem Init
# --------------------------------------------------------------------------

_R1_IDLE_STATE = const(0x01)
_R1_ILLEGAL_COMMAND = const(0x04)
_TOKEN_CMD25 = const(0xFC)
_TOKEN_STOP_TRAN = const(0xFD)
_TOKEN_DATA = const(0xFE)


class SDCard:
    def __init__(self, spi, cs, baudrate=_DATA_CLK_HZ):
        self.spi, self.cs = spi, cs
        self.cmdbuf = bytearray(6)
        self.tokenbuf = bytearray(1)
        self.dummybuf = bytes([0xFF]) * 512  # fuer write_readinto()

        # CS-Pin vorbereiten, SPI auf Low-Speed
        self.cs.init(cs.OUT, value=1)
        self.init_spi(_INIT_CLK_HZ)

        # Mind. 74 Dummy-Clocks mit CS = HIGH
        self.spi.write(b"\xff" * 16)

        # -------- Karten-Initialisierung mit mehreren Versuchen --------
        for _ in range(_INIT_RETRIES):
            try:
                self._card_init(baudrate)
                break
            except OSError:
                # Karten ziehen / stecken simulieren
                self.cs(1)
                self.spi.write(b"\xff")
                time.sleep_ms(200)
        else:
            raise OSError("no SD card")

    # ------------------------------------------------------------------
    # Low-Level-SPI-Init
    # ------------------------------------------------------------------
    def init_spi(self, baud):
        try:  # RP2040 / Pyboard
            master = self.spi.MASTER
            self.spi.init(master, baudrate=baud, phase=0, polarity=0)
        except AttributeError:  # ESP / allgemeines API
            self.spi.init(baudrate=baud, phase=0, polarity=0)

    # ------------------------------------------------------------------
    # Karten-Init-Sequenz (v1 / v2)
    # ------------------------------------------------------------------
    def _card_init(self, data_baud):
        if self._cmd(0, 0, 0x95) != _R1_IDLE_STATE:
            raise OSError("CMD0")

        r = self._cmd(8, 0x01AA, 0x87, 4)  # Echo-Pattern
        if r == _R1_IDLE_STATE:
            self._init_v2()
        elif r == (_R1_IDLE_STATE | _R1_ILLEGAL_COMMAND):
            self._init_v1()
        else:
            raise OSError("CMD8")

        # ---------- Kapazitaet ueber CSD ermitteln ----------
        if self._cmd(9, 0, 0, 0, False):
            raise OSError("CSD")
        csd = bytearray(16)
        self._readinto(csd)

        if csd[0] & 0xC0 == 0x40:  # CSD v2.0 (SDHC/XC)
            self.sectors = ((csd[8] << 8 | csd[9]) + 1) * 1024
            self.card_type = 1
        else:  # bis 2 GB (SDSC)
            c_size = ((csd[6] & 3) << 10) | (csd[7] << 2) | (csd[8] >> 6)
            c_size_mult = ((csd[9] & 3) << 1) | (csd[10] >> 7)
            bl_len = csd[5] & 0x0F
            capacity = (c_size + 1) * (1 << (c_size_mult + 2)) * (1 << bl_len)
            self.sectors = capacity // 512
            self.card_type = 0

        if self._cmd(16, 512, 0):
            raise OSError("SET_BL_LEN")

        # High-Speed-SPI aktivieren
        self.init_spi(data_baud)

    def _init_v1(self):
        for _ in range(_CMD_TIMEOUT):
            self._cmd(55, 0, 0)
            if self._cmd(41, 0, 0) == 0:
                self.cdv = 512  # byte-addressing
                return
            time.sleep_ms(1)
        raise OSError("v1 timeout")

    def _init_v2(self):
        for _ in range(_CMD_TIMEOUT):
            self._cmd(58, 0, 0, 4)  # OCR lesen
            self._cmd(55, 0, 0)
            if self._cmd(41, 0x40000000, 0) == 0:
                self._cmd(58, 0, 0, -4)
                self.cdv = 1 if (self.tokenbuf[0] & 0x40) else 512
                return
            time.sleep_ms(1)
        raise OSError("v2 timeout")

    # ------------------------------------------------------------------
    # CMD-Low-Level
    # ------------------------------------------------------------------
    def _cmd(self, cmd, arg, crc, final=0, release=True, skip1=False):
        self.cs(0)
        buf = self.cmdbuf
        buf[0] = 0x40 | cmd
        buf[1] = (arg >> 24) & 0xFF
        buf[2] = (arg >> 16) & 0xFF
        buf[3] = (arg >> 8) & 0xFF
        buf[4] = (arg) & 0xFF
        buf[5] = crc
        self.spi.write(buf)

        if skip1:
            self.spi.readinto(self.tokenbuf, 0xFF)

        for _ in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if not (self.tokenbuf[0] & 0x80):
                if final < 0:  # Sonderfall OCR
                    self.spi.readinto(self.tokenbuf, 0xFF)
                    final = -1 - final
                for _ in range(final):
                    self.spi.write(b"\xff")
                if release:
                    self.cs(1)
                    self.spi.write(b"\xff")
                return self.tokenbuf[0]
            time.sleep_ms(1)

        self.cs(1)
        self.spi.write(b"\xff")
        return -1  # Timeout

    # ------------------------------------------------------------------
    # Data-Transfer-Hilfen
    # ------------------------------------------------------------------
    def _readinto(self, buf):
        self.cs(0)
        # auf Start-Token warten
        for _ in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == _TOKEN_DATA:
                break
            time.sleep_ms(1)
        else:
            self.cs(1)
            raise OSError("read token")

        self.spi.write_readinto(self.dummybuf[: len(buf)], buf)
        self.spi.write(b"\xff\xff")  # CRC wegwerfen
        self.cs(1)
        self.spi.write(b"\xff")

    def _write_token(self, token, buf):
        self.cs(0)
        self.spi.write(bytes([token]))
        self.spi.write(buf)
        self.spi.write(b"\xff\xff")  # CRC
        # Data-Response
        self.spi.readinto(self.tokenbuf, 0xFF)
        if (self.tokenbuf[0] & 0x1F) != 0x05:
            self.cs(1)
            self.spi.write(b"\xff")
            raise OSError("write ack")
        # Busy wait
        while True:
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == 0xFF:
                break
        self.cs(1)
        self.spi.write(b"\xff")

    # ------------------------------------------------------------------
    # oeffentliche Block-API
    # ------------------------------------------------------------------
    def readblocks(self, block_num, buf):
        self.spi.write(b"\xff")
        n = len(buf) // 512
        assert n and not len(buf) % 512
        if n == 1:
            if self._cmd(17, block_num * self.cdv, 0, release=False):
                self.cs(1)
                raise OSError(5)
            self._readinto(buf)
        else:
            if self._cmd(18, block_num * self.cdv, 0, release=False):
                self.cs(1)
                raise OSError(5)
            mv = memoryview(buf)
            for i in range(n):
                self._readinto(mv[i * 512 : (i + 1) * 512])
            if self._cmd(12, 0, 0xFF, skip1=True):
                raise OSError(5)

    def writeblocks(self, block_num, buf):
        self.spi.write(b"\xff")
        n, rem = divmod(len(buf), 512)
        assert n and not rem
        if n == 1:
            if self._cmd(24, block_num * self.cdv, 0):
                raise OSError(5)
            self._write_token(_TOKEN_DATA, buf)
        else:
            if self._cmd(25, block_num * self.cdv, 0):
                raise OSError(5)
            mv = memoryview(buf)
            for i in range(n):
                self._write_token(_TOKEN_CMD25, mv[i * 512 : (i + 1) * 512])
            self._write_token(_TOKEN_STOP_TRAN, b"")

    # ------------------------------------------------------------------
    # ioctl-Bridge für VFS
    # ------------------------------------------------------------------
    def ioctl(self, op, arg):
        if op == 4:
            return self.sectors  # SEC_COUNT
        if op == 5:
            return 512  # SEC_SIZE
        if op == 6:
            return getattr(self, "card_type", 0)  # 0=SDSC 1=SDHC/XC
