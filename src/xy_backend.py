# xy_backend.py

import serial

from src.xyclops_core import XyclopsCore
from src.serial_manager import SerialManager
from src.log_router import LogRouter
from src.operations_dump import Dumper
from src.operations_flash import Flasher
from src.operations_verify import Verifier


class XyclopsBackend:
    def __init__(self, settings=None):
        self.settings = settings
        self.log = LogRouter()
        self.serial_mgr = SerialManager()
        self.port = None
        self.xy = None
        self.dumper = None
        self.flasher = None
        self.verifier = None

    def list_ports(self):
        return self.serial_mgr.list_ports()

    def probe_port(self, device):
        try:
            s = serial.Serial(device, 9600, timeout=0.15)
        except Exception as e:
            self.log.log(f"{device}: open failed: {e}", "WARNING")
            return False
        try:
            xy = XyclopsCore(s)
            return xy.ping()
        except Exception as e:
            self.log.log(f"{device}: probe error: {e}", "WARNING")
            return False
        finally:
            try:
                s.close()
            except Exception:
                pass

    def auto_detect(self):
        ports = self.list_ports()
        if not ports:
            self.log.log("No serial ports found on this system", "WARNING")
            return None
        for device, label, _ in ports:
            self.log.log(f"Probing {label}", "INFO_HIGH")
            if self.probe_port(device):
                return device
        self.log.log("No Xyclops device detected on any port", "ERROR")
        return None

    def connect(self, device):
        if self.port:
            self.disconnect()

        try:
            self.port = serial.Serial(device, 9600, timeout=0.5)
        except Exception as e:
            self.log.log(f"Failed to open {device}: {e}", "ERROR")
            return False

        self.xy = XyclopsCore(self.port)
        if not self.xy.sync():
            self.log.log(f"No response from Xyclops on {device}", "ERROR")
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.xy = None
            return False

        self.dumper = Dumper(self.xy, self.log)
        self.flasher = Flasher(self.xy, self.log)
        self.verifier = Verifier(self.xy, self.log)

        self.log.log(f"Connected on {device}", "INFO_HIGH")
        return True

    def is_connected(self):
        return self.xy is not None and self.port is not None

    def disconnect(self):
        if self.xy:
            try:
                self.xy.low_speed()
                self.xy.exit_debug()
            except Exception:
                pass
        if self.port:
            try:
                self.port.close()
            except Exception:
                pass
        self.port = None
        self.xy = None
        self.dumper = None
        self.flasher = None
        self.verifier = None
        self.log.log("Disconnected", "INFO_HIGH")

    def dump_bios(self, size=0x40000, double_read=True, progress_cb=None):
        return self.dumper.dump_bios(size=size, double_read=double_read,
                                     progress_cb=progress_cb)

    def dump_smc(self, size=0x4000, double_read=True, progress_cb=None):
        return self.dumper.dump_smc(size=size, double_read=double_read,
                                    progress_cb=progress_cb)

    def flash_bios(self, filepath, override=False, verify=True, fast=True,
                   progress_cb=None, backup=True):
        return self.flasher.flash_bios(filepath, override=override,
                                       verify=verify, fast=fast,
                                       progress_cb=progress_cb,
                                       backup=backup)

    def flash_smc(self, filepath, override=False, verify=True, fast=True,
                  progress_cb=None, backup=True):
        return self.flasher.flash_smc(filepath, override=override,
                                      verify=verify, fast=fast,
                                      progress_cb=progress_cb,
                                      backup=backup)

    def verify_bios(self, filepath, fast=True, progress_cb=None):
        return self.verifier.verify_bios(filepath, fast=fast,
                                         progress_cb=progress_cb)

    def verify_smc(self, filepath, fast=True, progress_cb=None):
        return self.verifier.verify_smc(filepath, fast=fast,
                                        progress_cb=progress_cb)

    def get_gui_log(self):
        return self.log.get_gui_log()

    def get_full_log(self):
        return self.log.get_full_log()