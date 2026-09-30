# operations_flash.py

import math
import os
from datetime import datetime

from src.utils import make_backup_folder, save_file, md5


class Flasher:
    def __init__(self, xy, log):
        self.xy = xy
        self.log = log

    def _pad_to_64(self, data: bytes) -> bytes:
        padding = (math.ceil(len(data) / 64) * 64) - len(data)
        if padding > 0:
            return data + (b"\xFF" * padding)
        return data

    def _ensure_high_speed(self, fast, label):
        if fast:
            if not self.xy.high_speed():
                self.log.log(f"{label}: failed to set high speed, use slow mode",
                             "ERROR")
                return False
        return True

    def _ensure_synced(self, label):
        if self.xy.sync():
            return True
        self.log.log(f"{label}: initial sync failed, trying 38400", "WARNING")
        self.xy.port.baudrate = 38400
        if not self.xy.sync():
            self.log.log(f"{label}: no communication from Xyclops", "ERROR")
            return False
        self.xy.low_speed()
        self.log.log(f"{label}: Xyclops was at 38400, reset to 9600",
                     "INFO_HIGH")
        return True

    def flash_bios(self, filepath, override=False, verify=True, fast=True,
                   progress_cb=None, backup=True):
        try:
            with open(filepath, "rb") as f:
                filedata = f.read()
        except FileNotFoundError:
            self.log.log(f"BIOS file not found: {filepath}", "ERROR")
            return False

        filedata = self._pad_to_64(filedata)

        if not override:
            if len(filedata) < 0x1000:
                self.log.log("BIOS file very small (< 0x1000)", "ERROR")
                return False
            if len(filedata) > 0x40000:
                self.log.log("BIOS file too big (> 256KiB)", "ERROR")
                return False

        if not self._ensure_synced("BIOS"):
            return False

        if backup:
            self._backup_bios()

        self.xy.enable_prog()
        ok, t = self.xy.erase_bios()
        if not ok:
            self.log.log("BIOS erase failed", "ERROR")
            return False
        self.log.log(f"BIOS erase took {t:.3f}s" if t is not None
                     else "BIOS erase ok", "INFO_HIGH")

        chk = self.xy.read_bios(0)
        if chk != (b"\xFF" * 64):
            self.log.log("BIOS erase check failed (first 64 bytes not FF)",
                         "ERROR")
            return False

        if not self._ensure_high_speed(fast, "BIOS"):
            return False

        blocks = len(filedata) // 64
        for idx in range(blocks):
            addr = idx * 64
            if (addr & 0xFFFF) == 0:
                self.xy.write_reg(0x91, addr >> 16)

            if not self.xy.write_bios_block(addr, filedata[addr:addr + 64]):
                self.log.log(f"BIOS: bad response at 0x{addr:X}", "ERROR")
                if progress_cb:
                    progress_cb(idx, blocks, "error")
                return False

            if progress_cb:
                progress_cb(idx, blocks, "ok")

            if (addr % 0x1000) == 0:
                self.log.log(
                    f"BIOS: programmed 0x{addr:X} / 0x{len(filedata):X}",
                    "INFO_HIGH")

        if verify:
            from src.operations_verify import Verifier
            ver = Verifier(self.xy, self.log)
            if not ver.verify_bios(filepath, fast=fast,
                                   progress_cb=progress_cb):
                self.log.log("BIOS verification failed", "ERROR")
                return False
            self.log.log("BIOS verification passed", "INFO_HIGH")

        return True

    def _backup_bios(self):
        folder = make_backup_folder()
        self.log.log(f"BIOS backup -> {folder}", "INFO_HIGH")
        from src.operations_dump import Dumper
        d = Dumper(self.xy, self.log)
        res = d.dump_bios(double_read=False)
        if res and res.get("status") == "ok":
            path = os.path.join(folder, "bios_before_flash.bin")
            save_file(path, res["dump"])
            self.log.log(f"BIOS backup saved: {path} (MD5 {md5(res['dump'])})",
                         "INFO_HIGH")
        else:
            self.log.log("BIOS backup FAILED — continuing anyway", "WARNING")

    def flash_smc(self, filepath, override=False, verify=True, fast=True,
                  progress_cb=None, backup=True):
        try:
            with open(filepath, "rb") as f:
                filedata = f.read()
        except FileNotFoundError:
            self.log.log(f"SMC file not found: {filepath}", "ERROR")
            return False

        filedata = self._pad_to_64(filedata)

        if not override:
            if len(filedata) < 0x1000:
                self.log.log("SMC file very small (< 0x1000)", "ERROR")
                return False
            if len(filedata) > 0x10000:
                self.log.log("SMC file too big (> 64KiB)", "ERROR")
                return False

        if len(filedata) > 0x4000:
            filedata = filedata[:0x4000]

        if not self._ensure_synced("SMC"):
            return False

        if backup:
            self._backup_smc()

        self.xy.enable_prog()
        ok, t = self.xy.erase_smc()
        if not ok:
            self.log.log("SMC erase failed", "ERROR")
            return False
        self.log.log(f"SMC erase took {t:.3f}s" if t is not None
                     else "SMC erase ok", "INFO_HIGH")

        chk = self.xy.read_smc(0)
        if chk != (b"\xFF" * 64):
            self.log.log("SMC erase check failed (first 64 bytes not FF)",
                         "ERROR")
            return False

        if not self._ensure_high_speed(fast, "SMC"):
            return False

        blocks = len(filedata) // 64
        for idx in range(blocks):
            addr = idx * 64
            if not self.xy.write_smc_block(addr, filedata[addr:addr + 64]):
                self.log.log(f"SMC: bad response at 0x{addr:X}", "ERROR")
                if progress_cb:
                    progress_cb(idx, blocks, "error")
                return False

            if progress_cb:
                progress_cb(idx, blocks, "ok")

            if (addr % 0x800) == 0:
                self.log.log(
                    f"SMC: programmed 0x{addr:X} / 0x{len(filedata):X}",
                    "INFO_HIGH")

        if verify:
            from src.operations_verify import Verifier
            ver = Verifier(self.xy, self.log)
            if not ver.verify_smc(filepath, fast=fast,
                                  progress_cb=progress_cb):
                self.log.log("SMC verification failed", "ERROR")
                return False
            self.log.log("SMC verification passed", "INFO_HIGH")

        return True

    def _backup_smc(self):
        folder = make_backup_folder()
        self.log.log(f"SMC backup -> {folder}", "INFO_HIGH")
        from src.operations_dump import Dumper
        d = Dumper(self.xy, self.log)
        res = d.dump_smc(double_read=False)
        if res and res.get("status") == "ok":
            path = os.path.join(folder, "smc_before_flash.bin")
            save_file(path, res["dump"])
            self.log.log(f"SMC backup saved: {path} (MD5 {md5(res['dump'])})",
                         "INFO_HIGH")
        else:
            self.log.log("SMC backup FAILED — continuing anyway", "WARNING")