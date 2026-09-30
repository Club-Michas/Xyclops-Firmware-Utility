# serial_manager.py

import serial.tools.list_ports


class SerialManager:
    """
    Enumerate serial ports. That's it.
    Probing and connecting live in XyclopsBackend, which knows how to
    talk to the Xyclops protocol.
    """

    def list_ports(self):
        result = []
        for p in serial.tools.list_ports.comports():
            desc = p.description or ""
            hwid = p.hwid or ""
            label = f"{p.device}: {desc}" if desc else p.device
            result.append((p.device, label, hwid))
        return result