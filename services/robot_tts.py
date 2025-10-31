import queue
from common.finish_event import FinishEvent
from infra.tts import PaddleTTS
from services.robot_state import RobotState
import threading
import time
from common import logger
import asyncio

class RobotTTS(FinishEvent):
    def __init__(self, paddle_server_ip, paddle_server_port):
        super().__init__()
        self.tts = PaddleTTS(paddle_server_ip, paddle_server_port)
        self.text_queue = queue.Queue()
        self.text_queue.put(f'机器人语音对话开启')
        threading.Thread(target=self.tts_play_thread, daemon=True).start()

    def tts_play_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            answer = self.text_queue.get()
            with RobotState.stt_tts_sema:
                with self.start_event():
                    self.tts.tts(answer, speak=True)

    def wait_tts_finish(self):
        # if RobotState.is_playing_music:
        #     return
        while not self.text_queue.empty():
            time.sleep(0.1)
        self.wait()

    def input_text(self, text):
        self.text_queue.put(text)