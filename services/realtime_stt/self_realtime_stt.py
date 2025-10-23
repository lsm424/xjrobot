import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import io
from common import logger
import requests
from datetime import datetime
from infra.stt import self_speech_to_text
from infra.audio import audio_tool
from . import BaseRealtimeSTT

class SelfRealtimeSTT(BaseRealtimeSTT):
    def __init__(self):
        super().__init__()
        
    def start_recording(self):
        try:
            wav_path = audio_tool.record_until_silence(self.on_record_start, self.on_record_end)
            if wav_path is None:
                return None
            with open('test.wav', 'wb') as f:
                f.write(wav_path.read())
            wav_path = 'test.wav'
            resp = self_speech_to_text(wav_path)
            text = resp[0]['text']
            return text
        except Exception as e:
            logger.error(f"录音过程中出错: {e}")
            return None
