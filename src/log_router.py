# log_router.py

class LogRouter:
    def __init__(self):
        self.full_log = []
        self.gui_log = []

    def log(self, msg, level="INFO_LOW"):
        entry = (level, msg)
        self.full_log.append(entry)

        if level in ("INFO_HIGH", "WARNING", "ERROR"):
            self.gui_log.append(entry)

    def get_gui_log(self):
        return self.gui_log

    def get_full_log(self):
        return self.full_log
