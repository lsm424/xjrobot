import threading

class RobotState:
    running = True
    stt_tts_sema = threading.Semaphore(1)
    tts_client = None  # 全局TTS客户端实例
    is_playing_music = False  # 是否正在播放音乐的标志位