# operations_verify.py

import math


class Verifier:
    def __init__(self, xy, log):
        self.xy = xy
        self.log = log

    def _pad_to_64(self, data: bytes) -> bytes:
        padding = (math.ceil(len(data) / 64) * 64) - len(data)
        if padding > 0:
            return data + (b"\xFF" * padding)
        return data

    def verify_bios(self, filepath, fast=True, progress_cb=None):
        try:
            with open(filepath, "rb") as f:
                filedata = f.read()
        except FileNotFoundError:
            self.log.log(f"BIOS file not found: {filepath}", "ERROR")
            return False

        filedata = self._pad_to_64(filedata)

        if fast:
            if not self.xy.high_speed():
                self.log.log("BIOS verify: failed to set high speed", "ERROR")
                return False

        blocks = len(filedata) // 64
        for idx in range(blocks):
            addr = idx * 64
            if (addr & 0xFFFF) == 0:
                self.xy.write_reg(0x91, addr >> 16)

            read = self.xy.read_bios(addr)
            if read is None or read != filedata[addr:addr + 64]:
                self.log.log(f"BIOS verify failure at 0x{addr:X}", "ERROR")
                if progress_cb:
                    progress_cb(idx, blocks, "error")
                return False

            if progress_cb:
                progress_cb(idx, blocks, "ok")

            if (addr % 0x1000) == 0:
                self.log.log(
                    f"BIOS: verified 0x{addr:X} / 0x{len(filedata):X}",
                    "INFO_HIGH")

        return True

    def verify_smc(self, filepath, fast=True, progress_cb=None):
        try:
            with open(filepath, "rb") as f:
                filedata = f.read()
        except FileNotFoundError:
            self.log.log(f"SMC file not found: {filepath}", "ERROR")
            return False

        filedata = self._pad_to_64(filedata)
        if len(filedata) > 0x4000:
            filedata = filedata[:0x4000]

        if fast:
            if not self.xy.high_speed():
                self.log.log("SMC verify: failed to set high speed", "ERROR")
                return False

        blocks = len(filedata) // 64
        for idx in range(blocks):
            addr = idx * 64
            read = self.xy.read_smc(addr)
            if read is None or read != filedata[addr:addr + 64]:
                self.log.log(f"SMC verify failure at 0x{addr:X}", "ERROR")
                if progress_cb:
                    progress_cb(idx, blocks, "error")
                return False

            if progress_cb:
                progress_cb(idx, blocks, "ok")

            if (addr % 0x800) == 0:
                self.log.log(
                    f"SMC: verified 0x{addr:X} / 0x{len(filedata):X}",
                    "INFO_HIGH")

        return True