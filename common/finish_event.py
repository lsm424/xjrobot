import threading
from contextlib import contextmanager

class FinishEvent(threading.Event):
    def __init__(self):
        super().__init__()
        self.set()

    @contextmanager
    def start_event(self):
        self.clear()
        yield
        self.set()

        