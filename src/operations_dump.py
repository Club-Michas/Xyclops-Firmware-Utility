# operations_dump.py

class Dumper:
    def __init__(self, xy, log):
        self.xy = xy
        self.log = log

    def _dump_generic(self, read_fn, size, label, progress_cb=None):
        blocks = size // 64
        data = bytearray()

        for idx in range(blocks):
            addr = idx * 64
            chunk = read_fn(addr)
            if chunk is None or len(chunk) != 64:
                self.log.log(f"{label}: read error at 0x{addr:X}", "ERROR")
                if progress_cb:
                    progress_cb(idx, blocks, "error")
                return None

            data.extend(chunk)
            if progress_cb:
                progress_cb(idx, blocks, "ok")

            if (addr % 0x1000) == 0:
                self.log.log(f"{label}: dumped 0x{addr:X} / 0x{size:X}", "INFO_HIGH")

        return bytes(data)

    def _double_read(self, read_fn, size, label, progress_cb):
        first = self._dump_generic(read_fn, size, label, progress_cb)
        if first is None:
            return None

        second = self._dump_generic(read_fn, size, f"{label} (2nd)", progress_cb)
        if second is None:
            return None

        if first != second:
            self.log.log(f"{label} double-read mismatch", "WARNING")
            return {"status": "mismatch", "dump1": first, "dump2": second}

        self.log.log(f"{label} double-read verified OK", "INFO_HIGH")
        return {"status": "ok", "dump": first}

    def dump_bios(self, size=0x40000, double_read=True, progress_cb=None):
        # Always return a dict — consistent contract for the GUI.
        if double_read:
            return self._double_read(self.xy.read_bios, size, "BIOS", progress_cb)

        data = self._dump_generic(self.xy.read_bios, size, "BIOS", progress_cb)
        if data is None:
            return None
        return {"status": "ok", "dump": data}

    def dump_smc(self, size=0x4000, double_read=True, progress_cb=None):
        if double_read:
            return self._double_read(self.xy.read_smc, size, "SMC", progress_cb)

        data = self._dump_generic(self.xy.read_smc, size, "SMC", progress_cb)
        if data is None:
            return None
        return {"status": "ok", "dump": data}