# xyclops_core.py
#
# Wire protocol is identical to the reference scripts (xyclops_flasher.py /
# xyclops_smc_flasher.py / xyclops_dumper.py):
#
#   sync:       write 0x00              -> read 2
#   read BIOS:  [0x14, ah, al, 0]       -> read 65  (resp[0] must == 0x14)
#   read SMC:   [0x15, ah, al, 0]       -> read 65  (resp[0] must == 0x15)
#   write BIOS: [0x16, ah, al] + 64B    -> read 2   (resp[0] must == 0x16)
#   write SMC:  [0x17, ah, al] + 64B    -> read 2   (resp[0] must == 0x17)
#   erase BIOS: [0x84, 0, 0, 0]         -> read 2   (resp[0] must == 0x84)
#   erase SMC:  [0x85, 0, 0, 0]         -> read 2   (resp[0] must == 0x85)
#   read RAM:   [0x01, 0, a, 0]         -> read 2   (byte 1 is value)
#   write RAM:  [0x0B, 0, a, v]         -> read 2
#   read reg:   [0x28, 0, a, 0]         -> read 2   (byte 1 is value)
#   write reg:  [0x2B, 0, a, v]         -> read 2 (unless skipread)
#   enable prog: b"C..."                -> read 2
#   exit debug:  b"B..."                -> read 4
#   baud reg 0xE9: 0xEC -> 38400, 0xB0 -> 9600
#   BIOS bank reg 0x91 = addr >> 16
#
# Deviations from the reference are limited to:
#   * read_bios/read_smc validate the echoed command byte (the reference
#     dumper does this; the reference flasher does not, which is a latent bug).
#   * sync() and erase_*() use a real deadline instead of sleep()-based polling.
#   * Short reads return None instead of raising IndexError.
# No wire-level behavior has been changed.

import time
import serial


class XyclopsCore:
    # timeouts (seconds)
    SYNC_REPLY_TIMEOUT   = 0.15
    SYNC_ATTEMPTS        = 5
    ERASE_TIMEOUT        = 1.5
    READ_TIMEOUT         = 1.0
    SHORT_REPLY_TIMEOUT  = 1.0
    BAUD_SWITCH_DELAY    = 0.03

    def __init__(self, port: serial.Serial):
        self.port = port

    # -------------------------
    # Low-level read helper
    # -------------------------
    def _read_exact(self, n, timeout):
        """Read exactly n bytes or return None on timeout."""
        deadline = time.time() + timeout
        buf = bytearray()
        while len(buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            chunk = self.port.read(n - len(buf))
            if chunk:
                buf.extend(chunk)
            else:
                # read() returned empty; loop until deadline
                time.sleep(0.005)
        return bytes(buf)

    # -------------------------
    # Sync
    # -------------------------
    def sync(self):
        """
        Reference behavior:
            reset input, up to 5 attempts of { write 0x00; wait; read 2 }
            success = got 2 bytes AND nothing left in the buffer.

        We keep the same semantics but wait on a deadline instead of sleeping
        a fixed 30 ms per attempt.
        """
        self.port.reset_input_buffer()

        for _ in range(self.SYNC_ATTEMPTS):
            self.port.write(b"\x00")
            resp = self._read_exact(2, self.SYNC_REPLY_TIMEOUT)
            if resp is not None:
                # Must have drained the buffer for this to count as a sync.
                if self.port.in_waiting == 0:
                    return True
                # Stale bytes -> flush and retry.
                self.port.reset_input_buffer()

        return False

    def ping(self):
        """
        Cheap liveness check that does not reset the input buffer.
        Used by SerialManager.probe_port() so probing a port doesn't
        clobber anything mid-session.
        """
        try:
            self.port.write(b"\x00")
            resp = self._read_exact(2, self.SYNC_REPLY_TIMEOUT)
            return resp is not None
        except Exception:
            return False

    # -------------------------
    # RAM access
    # -------------------------
    def read_ram(self, addr):
        self.port.write([0x01, 0, addr & 0xFF, 0])
        resp = self._read_exact(2, self.SHORT_REPLY_TIMEOUT)
        return resp[1] if resp else None

    def write_ram(self, addr, value):
        self.port.write([0x0B, 0, addr & 0xFF, value & 0xFF])
        self._read_exact(2, self.SHORT_REPLY_TIMEOUT)

    # -------------------------
    # Register access
    # -------------------------
    def read_reg(self, addr):
        self.port.write([0x28, 0, addr & 0xFF, 0])
        resp = self._read_exact(2, self.SHORT_REPLY_TIMEOUT)
        return resp[1] if resp else None

    def write_reg(self, addr, value, skipread=False):
        self.port.write([0x2B, 0, addr & 0xFF, value & 0xFF])
        if not skipread:
            self._read_exact(2, self.SHORT_REPLY_TIMEOUT)

    # -------------------------
    # Debug / programming mode
    # -------------------------
    def exit_debug(self):
        self.port.write(b"B...")
        self._read_exact(4, self.SHORT_REPLY_TIMEOUT)

    def enable_prog(self):
        self.port.write(b"C...")
        self._read_exact(2, self.SHORT_REPLY_TIMEOUT)

    # -------------------------
    # Erase
    # -------------------------
    def _erase(self, cmd, label):
        self.port.write([cmd, 0, 0, 0])
        start = time.time()

        # Reference polls until in_waiting == 2 with a 1.5 s budget.
        # We use >= 2 (chunked USB delivery) and then read exactly 2.
        while (time.time() - start) < self.ERASE_TIMEOUT:
            if self.port.in_waiting >= 2:
                resp = self._read_exact(2, self.SHORT_REPLY_TIMEOUT)
                elapsed = time.time() - start
                if resp is None:
                    return False, None
                return (resp[0] == cmd), elapsed
            time.sleep(0.02)

        return False, None

    def erase_bios(self):
        return self._erase(0x84, "BIOS")

    def erase_smc(self):
        return self._erase(0x85, "SMC")

    # -------------------------
    # BIOS read
    # -------------------------
    def read_bios(self, addr):
        self.port.write([0x14, (addr >> 8) & 0xFF, addr & 0xFF, 0])
        resp = self._read_exact(65, self.READ_TIMEOUT)
        if resp is None or resp[0] != 0x14:
            return None
        return resp[1:]

    # -------------------------
    # SMC read
    # -------------------------
    def read_smc(self, addr):
        self.port.write([0x15, (addr >> 8) & 0xFF, addr & 0xFF, 0])
        resp = self._read_exact(65, self.READ_TIMEOUT)
        if resp is None or resp[0] != 0x15:
            return None
        return resp[1:]

    # -------------------------
    # Write helpers (used by Flasher)
    # -------------------------
    def write_bios_block(self, addr, block64):
        """
        Write one 64-byte block to BIOS at `addr`.
        Returns True on ack, False on bad/absent ack.
        """
        self.port.write([0x16, (addr >> 8) & 0xFF, addr & 0xFF])
        self.port.write(block64)
        resp = self._read_exact(2, self.SHORT_REPLY_TIMEOUT)
        return resp is not None and resp[0] == 0x16

    def write_smc_block(self, addr, block64):
        self.port.write([0x17, (addr >> 8) & 0xFF, addr & 0xFF])
        self.port.write(block64)
        resp = self._read_exact(2, self.SHORT_REPLY_TIMEOUT)
        return resp is not None and resp[0] == 0x17

    # -------------------------
    # Baud switching
    # -------------------------
    def high_speed(self):
        # Register 0xE9 controls baud. 0xEC -> 38400.
        self.write_reg(0xE9, 0xEC, skipread=True)
        time.sleep(self.BAUD_SWITCH_DELAY)
        self.port.baudrate = 38400
        self.port.reset_input_buffer()
        return self.sync()

    def low_speed(self):
        # 0xB0 -> 9600.
        self.write_reg(0xE9, 0xB0, skipread=True)
        time.sleep(self.BAUD_SWITCH_DELAY)
        self.port.baudrate = 9600
        self.port.reset_input_buffer()
        return self.sync()

    # -------------------------
    # Teardown
    # -------------------------
    def close(self):
        try:
            if self.port and self.port.is_open:
                self.port.close()
        except Exception:
            pass