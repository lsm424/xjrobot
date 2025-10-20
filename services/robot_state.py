import threading

class RobotState:
    running = True
    stt_tts_sema = threading.Semaphore(1)