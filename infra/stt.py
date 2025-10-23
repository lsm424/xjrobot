import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import io
from common import logger
import requests

def self_speech_to_text(wav_path):
    url = f"http://172.21.198.58:8000/asr"
    if isinstance(wav_path, io.BytesIO):
        wav_path.seek(0)
        files = {"audio": wav_path}
        response = requests.post(url, files=files)
    elif isinstance(wav_path, str):
        with open(wav_path, 'rb') as f:
            files = {"audio": f}
            response = requests.post(url, files=files)
    else:
        raise ValueError("wav_path must be io.BytesIO or str")
        # logger.info(response)
    return response.json()


def start_recording():
    wav_path = record_until_silence()

    # if wav_path is None:
    #     return None
    # with open('test.wav', 'wb') as f:
    #     f.write(wav_path.read())
    # wav_path = 'test.wav'
    resp = speech_to_text(wav_path)
    text = resp[0]['text']
    return text
