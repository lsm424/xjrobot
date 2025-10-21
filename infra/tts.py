import io
import sounddevice as sd
import soundfile as sf
import ctypes
import requests
import torch
import os
from common import logger
from paddlespeech.server.bin.paddlespeech_client import TTSOnlineClientExecutor
import re

class PaddleTTS:
    def __init__(self, server_ip, server_port):
        
        self.client_executor = TTSOnlineClientExecutor()
        self.paddle_server_ip = server_ip
        self.paddle_server_port = server_port

    def tts(self, text, speak=False, out_file="./assets/synth_audio_websocket.wav"):
        text = re.sub(r"[\"'!]", "", text)
        try:
            self.client_executor(
                input=text,
                server_ip=self.paddle_server_ip,
                port=self.paddle_server_port,
                protocol="websocket",  # 指定使用 websocket 协议
                output=out_file,
                play=speak  # Disable internal playback to avoid thread issues
            )
        except Exception as e:
            logger.error(f"Error during PaddleTTS: {e}，input text: {text}")
        # if speak:
        #     try:
        #         data, samplerate = sf.read(out_file, dtype='float32')
        #         sd.play(data, samplerate)
        #         sd.wait()  # Wait for playback to finish
        #     except Exception as e:
        #         logger.error(f"Error during audio playback: {e}")

    
    def self_text_to_speech(self, text, prompt_path=None, prompt_text=None, mode="zero_shot", play=False):
        url = f"http://172.21.198.58:8000/tts"
        files = {}
        if prompt_path:
            files["audio"] = open(prompt_path, 'rb')
        data = {
            "text": text,
            "prompt": prompt_text,
            "mode": mode
        }
        response = requests.post(url, data=data, files=files)
        if response.status_code == 200:
            audio_bytes = io.BytesIO(response.content)
            # 读取音频数据和采样率
            data, samplerate = sf.read(audio_bytes, dtype='float32')
            sf.write("./assets/self_tts_output.wav", data, samplerate)
            # 播放音频
            if play:
                sd.play(data, samplerate)
                sd.wait()  # 等待播放完成
            # 读取音频数据和采样率
            # 将音频数据写入本地 wav 文件
        else:
            logger.error("TTS failed:", response.json())
        # return response.status_code
