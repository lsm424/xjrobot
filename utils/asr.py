# -*- encoding: utf-8 -*-
import os
import time
import websockets
import ssl
import json
# import logging
import pyaudio
import struct
import math
import loguru
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
import threading

logger = loguru.logger
# # 配置日志，减少不必要的输出
# logging.basicConfig(level=logging.ERROR)

class SpeechRecognizer:
    def __init__(self, host="172.30.3.7", port=10095):
        self.host = host
        self.port = port
        self.chunk_size = [5, 10, 5]  # chunk配置
        self.chunk_interval = 10
        self.encoder_chunk_look_back = 4
        self.decoder_chunk_look_back = 0
        self.hotword = ""
        self.audio_fs = 16000
        self.mode = "2pass" # 推荐使用 2pass 或 offline
        self.ssl = 1
        self.result_event = threading.Event()

        # 录音控制
        self.running = False
        self.final_text = ""
        self.silence_threshold = 3000  # 静音阈值，根据麦克风灵敏度调整
        self.websocket = None
        self.max_silence_seconds = 1.5  # 静音持续多久后停止
        threading.Thread(target=self._conn_keepalive, daemon=True).start()
        while not self.websocket:
            time.sleep(1)

    def _conn_keepalive(self):
        ssl_context = ssl.SSLContext()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        uri = f"wss://{self.host}:{self.port}" if self.ssl == 1 else f"ws://{self.host}:{self.port}"
        while True:
            if not self.websocket:
                logger.info(f"Connecting to {uri}...")
                self.websocket = connect(uri, subprotocols=["binary"], ssl=ssl_context if self.ssl == 1 else None)
                logger.info("Connected to server")
                threading.Thread(target=self._message_handler, daemon=True).start()
            try:
                self.websocket.ping().wait()
            except BaseException as e:
                logger.error(f"Ping failed: {e}")
                self.websocket = None

    def _is_silent(self, data_chunk):
        """简单的静音检测 (RMS 能量)"""
        if len(data_chunk) == 0:
            return True
        count = len(data_chunk) / 2
        format = "%dh" % (count)
        shorts = struct.unpack(format, data_chunk)
        sum_squares = sum(s**2 for s in shorts)
        rms = math.sqrt(sum_squares / count)
        #print(rms)
        return rms < self.silence_threshold

    def _record_microphone(self):
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        # 计算每次读取的帧大小
        chunk_duration = 60 * self.chunk_size[1] / self.chunk_interval / 1000
        CHUNK = int(RATE * chunk_duration) 

        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
        )

        # 发送握手配置
        message = json.dumps({
            "mode": self.mode,
            "chunk_size": self.chunk_size,
            "chunk_interval": self.chunk_interval,
            "encoder_chunk_look_back": self.encoder_chunk_look_back,
            "decoder_chunk_look_back": self.decoder_chunk_look_back,
            "wav_name": "microphone",
            "is_speaking": True,
            "hotwords": self.hotword,
            "itn": True,
        })
        self.websocket.send(message)

        logger.info(f"正在监听 (请说话, {self.max_silence_seconds}s 静音后自动结束)")
        
        silence_start_time = None
        has_spoken = False # 确保用户至少说了一点话才开始检测静音
        self.running = True
        self.result_event.clear()

        while self.websocket:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                self.websocket.send(data)
                
                # 静音检测逻辑
                is_silent = self._is_silent(data)
                
                if not is_silent:
                    has_spoken = True
                    silence_start_time = None # 重置静音计时
                    # logger.info('重置静音计时')
                else:
                    if has_spoken: # 只有说话后才开始计算静音
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > self.max_silence_seconds:
                            logger.info("End of speech detected.")
                            self.running = False
                            break
                
                time.sleep(0.001)
            except Exception as e:
                logger.error(f"Record error: {e}")
                break

        # 发送结束标志
        try:
            stream.stop_stream()
            stream.close()
        except BaseException as e:
            pass
        p.terminate()
        self.websocket.send(json.dumps({"is_speaking": False}))
        self.result_event.wait()

    def _message_handler(self):
        """接收服务器返回的消息"""
        try:
            while self.websocket:
                try:
                    meg = json.loads(self.websocket.recv(timeout=1))
                except BaseException as e:
                    if not self.running:
                        self.result_event.set()
                    continue
                
                if "text" in meg:
                    # 实时打印，提升交互感
                    if meg.get("mode") == "2pass-online":
                        logger.info(f"Listening: {meg['text']}", end="", flush=True)
                    elif meg.get("mode") == "offline" or meg.get("is_final"):
                        self.final_text = meg['text']
                        logger.info(f"Final Result: {self.final_text}")
     
                if meg.get("is_final", False):
                    if not self.running:
                        self.result_event.set()
                        # logger.info("final")

        except Exception as e:
            # 连接关闭通常是正常的
            pass


    def start(self):
        """同步入口函数"""
        self.final_text = ''
        self._record_microphone()
        return self.final_text

# 导出给 main.py 调用的简单函数
def recognize_speech(host="172.30.3.7", port=10095):
    recognizer = SpeechRecognizer(host, port)
    return recognizer
    # return recognizer.start()

if __name__ == "__main__":
    # 测试代码
    res = recognize_speech()
    while True:
        try:
            text = res.start()
            logger.info(f"Recognized: {text}")
            # Optional: Add a small delay or condition to break
            # time.sleep(1)
        except KeyboardInterrupt:
            break
