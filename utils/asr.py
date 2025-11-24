# -*- encoding: utf-8 -*-
import os
import time
import websockets
import ssl
import asyncio
import json
# import logging
import pyaudio
import struct
import math

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
        
        # 录音控制
        self.running = False
        self.final_text = ""
        self.silence_threshold = 3000  # 静音阈值，根据麦克风灵敏度调整
        self.max_silence_seconds = 1.5  # 静音持续多久后停止

    def _is_silent(self, data_chunk):
        """简单的静音检测 (RMS 能量)"""
        if len(data_chunk) == 0:
            return True
        count = len(data_chunk) / 2
        format = "%dh" % (count)
        shorts = struct.unpack(format, data_chunk)
        sum_squares = sum(s**2 for s in shorts)
        rms = math.sqrt(sum_squares / count)
        return rms < self.silence_threshold

    async def _record_microphone(self, websocket):
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
        await websocket.send(message)

        print(f"Listening... (Speak now, stops after {self.max_silence_seconds}s silence)")
        
        silence_start_time = None
        has_spoken = False # 确保用户至少说了一点话才开始检测静音

        while self.running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                await websocket.send(data)
                
                # 静音检测逻辑
                is_silent = self._is_silent(data)
                
                if not is_silent:
                    has_spoken = True
                    silence_start_time = None # 重置静音计时
                else:
                    if has_spoken: # 只有说话后才开始计算静音
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > self.max_silence_seconds:
                            print("End of speech detected.")
                            self.running = False
                            break
                
                await asyncio.sleep(0.001)
            except Exception as e:
                print(f"Record error: {e}")
                break

        # 发送结束标志
        stream.stop_stream()
        stream.close()
        p.terminate()
        await websocket.send(json.dumps({"is_speaking": False}))

    async def _message_handler(self, websocket):
        """接收服务器返回的消息"""
        try:
            while True:
                if not self.running: 
                    # 如果录音停止了，等待最后的识别结果，设置超时防止死锁
                    try:
                        meg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        break
                else:
                    meg = await websocket.recv()
                
                meg = json.loads(meg)
                
                if "text" in meg:
                    # 实时打印，提升交互感
                    if meg.get("mode") == "2pass-online":
                        print(f"\rListening: {meg['text']}", end="", flush=True)
                    elif meg.get("mode") == "offline" or meg.get("is_final"):
                        self.final_text = meg['text']
                        print(f"\rFinal Result: {self.final_text}")
                        
                if meg.get("is_final", False) and not self.running:
                    break

        except Exception as e:
            # 连接关闭通常是正常的
            pass

    async def _execute_ws(self):
        ssl_context = ssl.SSLContext()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        uri = f"wss://{self.host}:{self.port}" if self.ssl == 1 else f"ws://{self.host}:{self.port}"
        
        self.running = True
        self.final_text = ""
        
        try:
            async with websockets.connect(
                uri, subprotocols=["binary"], ping_interval=None, ssl=ssl_context if self.ssl == 1 else None
            ) as websocket:
                # 同时运行录音和接收消息
                record_task = asyncio.create_task(self._record_microphone(websocket))
                msg_task = asyncio.create_task(self._message_handler(websocket))
                
                await record_task
                await msg_task
        except Exception as e:
            print(f"Connection failed: {e}")
            return ""
            
        return self.final_text

    def start(self):
        """同步入口函数"""
        try:
            return asyncio.run(self._execute_ws())
        except KeyboardInterrupt:
            return ""

# 导出给 main.py 调用的简单函数
def recognize_speech(host="172.30.3.7", port=10095):
    recognizer = SpeechRecognizer(host, port)
    return recognizer.start()

if __name__ == "__main__":
    # 测试代码
    res = recognize_speech()
    print(f"Recognized: {res}")