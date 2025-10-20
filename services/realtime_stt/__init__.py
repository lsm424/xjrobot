from abc import ABC, abstractmethod
from common import logger
from services.robot_state import RobotState

class BaseRealtimeSTT(ABC):
    def __init__(self):
        super().__init__()

    def on_record_start(self):
        logger.info(f'开始录音')
        RobotState.stt_tts_sema.acquire()

    def on_record_end(self):
        RobotState.stt_tts_sema.release()
        logger.info(f'录音结束')

    @abstractmethod
    def start_recording(self):
        pass