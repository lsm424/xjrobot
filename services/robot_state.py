import threading

class RobotState:
    running = True
    stt_tts_sema = threading.Semaphore(1)
    tts_client = None  # 全局TTS客户端实例