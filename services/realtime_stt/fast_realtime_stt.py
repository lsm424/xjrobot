import os
from RealtimeSTT import AudioToTextRecorder
from common import logger
from common.finish_event import FinishEvent
from . import BaseRealtimeSTT
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

stt_model = 'small'


class FastRealtimeSTT(BaseRealtimeSTT):
    def __init__(self):
        super().__init__()
        self.recorder = AudioToTextRecorder(
            model=stt_model, 
            language='zh', 
            download_root='assets/model_dir',
            device='cpu', 
            enable_realtime_transcription=True, 
            silero_deactivity_detection=True, 
            on_recording_start=self.on_record_start,
            on_recording_stop=self.on_record_end)

    def start_recording(self):
        try:
            text = self.recorder.text().strip()
            return text
        except Exception as e:
            logger.error(f"录音过程中出错: {e}")
            return None

