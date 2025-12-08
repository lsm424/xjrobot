# # -*- encoding: utf-8 -*-
# import os
# import time
# import websockets
# import ssl
# import json
# # import logging
# import pyaudio
# import struct
# import math
# import loguru
# from websockets.sync.client import connect
# from websockets.exceptions import ConnectionClosed
# import threading
# # from utils.turn_detector import TurnDetector
# # from collections import deque
# logger = loguru.logger
# # # 配置日志，减少不必要的输出
# # logging.basicConfig(level=logging.ERROR)

# class SpeechRecognizer:
#     def __init__(self, host="172.30.3.7", port=10095):
#         self.host = host
#         self.port = port
#         self.chunk_size = [5, 10, 5]  # chunk配置
#         self.chunk_interval = 10
#         self.encoder_chunk_look_back = 4
#         self.decoder_chunk_look_back = 0
#         self.hotword = ""
#         self.audio_fs = 16000
#         self.mode = "2pass" # 推荐使用 2pass 或 offline
#         self.ssl = 1
#         self.result_event = threading.Event()

#         # 录音控制
#         self.running = False
#         self.final_text = ""
#         self.silence_threshold = 1000  # 静音阈值，根据麦克风灵敏度调整
#         self.websocket = None
#         self.max_silence_seconds = 1.5  # 静音持续多久后停止
#         threading.Thread(target=self._conn_keepalive, daemon=True).start()
#         while not self.websocket:
#             time.sleep(1)

#     def _conn_keepalive(self):
#         ssl_context = ssl.SSLContext()
#         ssl_context.check_hostname = False
#         ssl_context.verify_mode = ssl.CERT_NONE
#         uri = f"wss://{self.host}:{self.port}" if self.ssl == 1 else f"ws://{self.host}:{self.port}"
#         while True:
#             if not self.websocket:
#                 logger.info(f"Connecting to {uri}...")
#                 self.websocket = connect(uri, subprotocols=["binary"], ssl=ssl_context if self.ssl == 1 else None)
#                 logger.info("Connected to server")
#                 threading.Thread(target=self._message_handler, daemon=True).start()
#             try:
#                 self.websocket.ping().wait()
#             except BaseException as e:
#                 logger.error(f"Ping failed: {e}")
#                 self.websocket = None

#     def _is_silent(self, data_chunk):
#         """简单的静音检测 (RMS 能量)"""
#         if len(data_chunk) == 0:
#             return True
#         count = len(data_chunk) / 2
#         format = "%dh" % (count)
#         shorts = struct.unpack(format, data_chunk)
#         sum_squares = sum(s**2 for s in shorts)
#         rms = math.sqrt(sum_squares / count)
#         #print(rms)
#         return rms < self.silence_threshold

#     def _record_microphone(self):
#         FORMAT = pyaudio.paInt16
#         CHANNELS = 1
#         RATE = 16000
#         # 计算每次读取的帧大小
#         chunk_duration = 60 * self.chunk_size[1] / self.chunk_interval / 1000
#         CHUNK = int(RATE * chunk_duration) 

#         p = pyaudio.PyAudio()
#         stream = p.open(
#             format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
#         )

#         # 发送握手配置
#         message = json.dumps({
#             "mode": self.mode,
#             "chunk_size": self.chunk_size,
#             "chunk_interval": self.chunk_interval,
#             "encoder_chunk_look_back": self.encoder_chunk_look_back,
#             "decoder_chunk_look_back": self.decoder_chunk_look_back,
#             "wav_name": "microphone",
#             "is_speaking": True,
#             "hotwords": self.hotword,
#             "itn": True,
#         })
#         self.websocket.send(message)

#         logger.info(f"正在监听 (请说话, {self.max_silence_seconds}s 静音后自动结束)")
        
#         silence_start_time = None
#         has_spoken = False # 确保用户至少说了一点话才开始检测静音
#         self.running = True
#         self.result_event.clear()

#         while self.websocket:
#             try:
#                 data = stream.read(CHUNK, exception_on_overflow=False)
#                 self.websocket.send(data)
#                 # 静音检测逻辑
#                 is_silent = self._is_silent(data)
                
#                 if not is_silent:
#                     has_spoken = True
#                     silence_start_time = None # 重置静音计时
#                     self.final_text=''
#                     # logger.info('重置静音计时')
#                 else:
#                     if has_spoken: # 只有说话后才开始计算静音
#                         if silence_start_time is None:
#                             silence_start_time = time.time()
#                         elif time.time() - silence_start_time > self.max_silence_seconds:
#                             logger.info("End of speech detected.")
#                             self.running = False
#                             break
                
#                 time.sleep(0.001)
#             except Exception as e:
#                 logger.error(f"Record error: {e}")
#                 break

#         # 发送结束标志
#         try:
#             stream.stop_stream()
#             stream.close()
#         except BaseException as e:
#             pass
#         p.terminate()
#         self.websocket.send(json.dumps({"is_speaking": False}))
#         self.result_event.wait()

#     def _message_handler(self):
#         """接收服务器返回的消息"""
#         try:
#             while self.websocket:
#                 try:
#                     meg = json.loads(self.websocket.recv(timeout=1))
#                 except BaseException as e:
#                     if not self.running:
#                         self.result_event.set()
#                     continue
                
#                 if "text" in meg:
#                     # 实时打印，提升交互感
#                     if meg.get("mode") == "2pass-online":
#                         logger.info(f"Listening: {meg['text']}", end="", flush=True)
#                     elif meg.get("mode") == "offline" or meg.get("is_final"):
#                         self.final_text = meg['text']
#                         if not self.running:logger.info(f"Final Result: {self.final_text}")
     
#                 if meg.get("is_final", False):
#                     if not self.running:
#                         self.result_event.set()
#                         # logger.info("final")

#         except Exception as e:
#             # 连接关闭通常是正常的
#             pass


#     def start(self):
#         """同步入口函数"""
#         self.final_text = ''
#         self._record_microphone()
#         return self.final_text

# # 导出给 main.py 调用的简单函数
# def recognize_speech(host="172.30.3.7", port=10095):
#     recognizer = SpeechRecognizer(host, port)
#     return recognizer
#     # return recognizer.start()

# if __name__ == "__main__":
#     # 测试代码
#     res = recognize_speech()
#     while True:
#         try:
#             text = res.start()
#             logger.info(f"Recognized: {text}")
#             # Optional: Add a small delay or condition to break
#             # time.sleep(1)
#         except KeyboardInterrupt:
#             break
# -*- encoding: utf-8 -*-
# import os
# import time
# import websockets
# import ssl
# import json
# import pyaudio
# import struct
# import math
# import loguru
# from websockets.sync.client import connect
# from websockets.exceptions import ConnectionClosed
# import threading
# from collections import deque
# import concurrent.futures  # === 关键引入 ===

# # 假设你的 turn_detector 在 utils 文件夹下，如果和 asr.py 同级请去掉 utils.
# try:
#     from utils.turn_detector import TurnDetector
# except ImportError:
#     from turn_detector import TurnDetector

# logger = loguru.logger

# class SpeechRecognizer:
#     def __init__(self, host="172.30.3.7", port=10095):
#         self.host = host
#         self.port = port
#         self.chunk_size = [5, 10, 5]
#         self.chunk_interval = 10
#         self.encoder_chunk_look_back = 4
#         self.decoder_chunk_look_back = 0
#         self.hotword = ""
#         self.audio_fs = 16000
#         self.mode = "2pass"
#         self.ssl = 1
#         self.result_event = threading.Event()

#         self.running = False
#         self.final_text = ""
#         self.silence_threshold = 1000
#         self.websocket = None
#         self.max_silence_seconds = 1.5
        
#         # === 核心修改：线程池 ===
#         # 创建一个单线程的池子，专门用来跑模型，不卡主线程
#         self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
#         # =====================

#         # 初始化判断模型
#         self.turn_detector = TurnDetector()
#         self.model_check_min_silence = 1.0 
        
#         threading.Thread(target=self._conn_keepalive, daemon=True).start()
#         while not self.websocket:
#             time.sleep(1)

#     def _conn_keepalive(self):
#         ssl_context = ssl.SSLContext()
#         ssl_context.check_hostname = False
#         ssl_context.verify_mode = ssl.CERT_NONE
#         uri = f"wss://{self.host}:{self.port}" if self.ssl == 1 else f"ws://{self.host}:{self.port}"
#         while True:
#             if not self.websocket:
#                 logger.info(f"Connecting to {uri}...")
#                 try:
#                     self.websocket = connect(uri, subprotocols=["binary"], ssl=ssl_context if self.ssl == 1 else None)
#                     logger.info("Connected to server")
#                     threading.Thread(target=self._message_handler, daemon=True).start()
#                 except Exception as e:
#                     logger.error(f"Connection failed: {e}")
#                     time.sleep(3)
#                     continue
#             try:
#                 self.websocket.ping().wait()
#                 time.sleep(1) # Ping interval
#             except BaseException as e:
#                 logger.error(f"Ping failed: {e}")
#                 self.websocket = None

#     def _is_silent(self, data_chunk):
#         if len(data_chunk) == 0:
#             return True
#         count = len(data_chunk) / 2
#         format = "%dh" % (count)
#         shorts = struct.unpack(format, data_chunk)
#         sum_squares = sum(s**2 for s in shorts)
#         rms = math.sqrt(sum_squares / count)
#         return rms < self.silence_threshold

#     def _record_microphone(self):
#         FORMAT = pyaudio.paInt16
#         CHANNELS = 1
#         RATE = 16000
#         chunk_duration = 60 * self.chunk_size[1] / self.chunk_interval / 1000
#         CHUNK = int(RATE * chunk_duration) 

#         p = pyaudio.PyAudio()
#         stream = p.open(
#             format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
#         )

#         message = json.dumps({
#             "mode": self.mode,
#             "chunk_size": self.chunk_size,
#             "chunk_interval": self.chunk_interval,
#             "encoder_chunk_look_back": self.encoder_chunk_look_back,
#             "decoder_chunk_look_back": self.decoder_chunk_look_back,
#             "wav_name": "microphone",
#             "is_speaking": True,
#             "hotwords": self.hotword,
#             "itn": True,
#         })
#         self.websocket.send(message)

#         logger.info(f"正在监听 (请说话, {self.max_silence_seconds}s 静音或智能断句后结束)")
        
#         silence_start_time = None
#         has_spoken = False
#         self.running = True
#         self.result_event.clear()

#         audio_context_buffer = deque(maxlen=256000)
        
#         # === 异步任务控制变量 ===
#         last_model_submit_time = 0
#         model_check_interval = 0.3 # 即使是异步，也没必要提交得太频繁
#         prediction_future = None   # 用来存放正在运行的“未来”结果
#         # =====================

#         while self.websocket:
#             try:
#                 # 1. 这一步是阻塞的，决定了录音的流畅度
#                 data = stream.read(CHUNK, exception_on_overflow=False)
                
#                 # 2. 只有这里不卡顿，音频才能发出去
#                 self.websocket.send(data)
#                 audio_context_buffer.extend(data)
                
#                 # 3. 简单的 RMS 计算（极快，忽略不计）
#                 is_silent = self._is_silent(data)
                
#                 # === 检查之前提交的模型任务是否完成 ===
#                 if prediction_future is not None and prediction_future.done():
#                     try:
#                         # 获取结果（非阻塞，因为已经 done 了）
#                         is_complete, prob = prediction_future.result()
#                         # logger.info(f"Async Check: {is_complete}, {prob:.2f}")
                        
#                         if is_complete:
#                             logger.info(f"End of speech detected (Smart Model: {prob:.2f}).")
#                             self.running = False
#                             break
#                     except Exception as e:
#                         logger.error(f"Model prediction error: {e}")
#                     finally:
#                         # 重置 future，允许提交新任务
#                         prediction_future = None
#                 # =================================

#                 if not is_silent:
#                     has_spoken = True
#                     silence_start_time = None 
#                     self.final_text = ''
#                     # 如果用户说话了，且当前有正在跑的预测任务，其实那个任务已经作废了
#                     # 但没关系，下次循环查到它 done 了以后不理会，或者让它自然结束即可
#                 else:
#                     if has_spoken:
#                         now = time.time()
#                         if silence_start_time is None:
#                             silence_start_time = now
                        
#                         silence_duration = now - silence_start_time

#                         # 1. 硬性兜底超时
#                         if silence_duration > self.max_silence_seconds:
#                             logger.info("End of speech detected (Max Silence Timeout).")
#                             self.running = False
#                             break
                        
#                         # 2. 智能模型判断 (异步提交)
#                         # 条件：静音够久 + 间隔够久 + 当前没有正在跑的任务
#                         if (silence_duration > self.model_check_min_silence and 
#                             (now - last_model_submit_time) > model_check_interval and 
#                             prediction_future is None):
                            
#                             last_model_submit_time = now
                            
#                             # 拷贝一份数据给线程用 (bytes转换是瞬间的内存操作)
#                             current_audio = bytes(audio_context_buffer)
                            
#                             # ★★★ 关键：提交任务到线程池，立马返回，不等待结果 ★★★
#                             prediction_future = self.executor.submit(self.turn_detector.predict, current_audio)
#                 time.sleep(0.001)       
#             except Exception as e:
#                 logger.error(f"Record error: {e}")
#                 break

#         # 清理工作
#         try:
#             stream.stop_stream()
#             stream.close()
#         except BaseException as e:
#             pass
#         p.terminate()
#         self.websocket.send(json.dumps({"is_speaking": False}))
#         self.result_event.wait()

#     def _message_handler(self):
#         try:
#             while self.websocket:
#                 try:
#                     meg = json.loads(self.websocket.recv(timeout=1))
#                 except BaseException as e:
#                     if not self.running:
#                         self.result_event.set()
#                     continue
                
#                 if "text" in meg:
#                     if meg.get("mode") == "2pass-online":
#                         # logger.info(f"Listening: {meg['text']}", end="", flush=True)
#                         pass
#                     elif meg.get("mode") == "offline" or meg.get("is_final"):
#                         self.final_text = meg['text']
#                         if not self.running:logger.info(f"Final Result: {self.final_text}")
     
#                 if meg.get("is_final", False):
#                     if not self.running:
#                         self.result_event.set()

#         except Exception as e:
#             pass

#     def start(self):
#         self.final_text = ''
#         self._record_microphone()
#         return self.final_text

# def recognize_speech(host="172.30.3.7", port=10095):
#     recognizer = SpeechRecognizer(host, port)
#     return recognizer

# if __name__ == "__main__":
#     res = recognize_speech()
#     while True:
#         try:
#             text = res.start()
#             logger.info(f"Recognized: {text}")
#         except KeyboardInterrupt:
#             break

import os
import time
import websockets
import ssl
import json
import pyaudio
import struct
import math
import loguru
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
import threading
from collections import deque
import concurrent.futures

try:
    from utils.turn_detector import TurnDetector
except ImportError:
    from turn_detector import TurnDetector

logger = loguru.logger

class SpeechRecognizer:
    def __init__(self, host="172.30.3.7", port=10095):
        self.host = host
        self.port = port
        self.chunk_size = [5, 10, 5]
        self.chunk_interval = 10
        self.encoder_chunk_look_back = 4
        self.decoder_chunk_look_back = 0
        self.hotword = ""
        self.audio_fs = 16000
        self.mode = "2pass"
        self.ssl = 0
        self.result_event = threading.Event()

        self.running = False
        self.final_text = ""
        self.silence_threshold = 1000
        self.websocket = None
        self.max_silence_seconds = 1.5
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        self.turn_detector = TurnDetector()
        self.model_check_min_silence = 0.3 
        
        # === 新增: 等待最终结果的超时时间 ===
        self.final_result_timeout = 2.0
        
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
                try:
                    self.websocket = connect(uri, subprotocols=["binary"], ssl=ssl_context if self.ssl == 1 else None)
                    logger.info("Connected to server")
                    threading.Thread(target=self._message_handler, daemon=True).start()
                except Exception as e:
                    logger.error(f"Connection failed: {e}")
                    time.sleep(3)
                    continue
            try:
                self.websocket.ping().wait()
                time.sleep(1)
            except BaseException as e:
                logger.error(f"Ping failed: {e}")
                self.websocket = None

    def _is_silent(self, data_chunk):
        if len(data_chunk) == 0:
            return True
        count = len(data_chunk) / 2
        format = "%dh" % (count)
        shorts = struct.unpack(format, data_chunk)
        sum_squares = sum(s**2 for s in shorts)
        rms = math.sqrt(sum_squares / count)
        return rms < self.silence_threshold

    def _record_microphone(self):
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        chunk_duration = 60 * self.chunk_size[1] / self.chunk_interval / 1000
        CHUNK = int(RATE * chunk_duration) 

        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
        )

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

        logger.info(f"正在监听 (请说话, {self.max_silence_seconds}s 静音或智能断句后结束)")
        
        silence_start_time = None
        has_spoken = False
        self.running = True
        self.result_event.clear()

        audio_context_buffer = deque(maxlen=256000)
        
        last_model_submit_time = 0
        model_check_interval = 0.3
        prediction_future = None

        while self.websocket:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                self.websocket.send(data)
                audio_context_buffer.extend(data)
                
                is_silent = self._is_silent(data)
                
                if prediction_future is not None and prediction_future.done():
                    try:
                        is_complete, prob = prediction_future.result()
                        
                        if is_complete:
                            logger.info(f"End of speech detected (Smart Model: {prob:.2f}).")
                            self.running = False
                            break
                    except Exception as e:
                        logger.error(f"Model prediction error: {e}")
                    finally:
                        prediction_future = None

                if not is_silent:
                    has_spoken = True
                    silence_start_time = None 
                    self.final_text = ''
                else:
                    if has_spoken:
                        now = time.time()
                        if silence_start_time is None:
                            silence_start_time = now
                        
                        silence_duration = now - silence_start_time

                        if silence_duration > self.max_silence_seconds:
                            logger.info("End of speech detected (Max Silence Timeout).")
                            self.running = False
                            break
                        
                        if (silence_duration > self.model_check_min_silence and 
                            (now - last_model_submit_time) > model_check_interval and 
                            prediction_future is None):
                            
                            last_model_submit_time = now
                            current_audio = bytes(audio_context_buffer)
                            prediction_future = self.executor.submit(self.turn_detector.predict, current_audio)
                            
                time.sleep(0.001)       
            except Exception as e:
                logger.error(f"Record error: {e}")
                break

        # === 关键修改: 清理并强制flush ===
        try:
            stream.stop_stream()
            stream.close()
        except BaseException as e:
            pass
        p.terminate()
        
        # 1. 发送 is_speaking=False 触发服务端处理剩余音频
        logger.info("Sending final flush signal to server...")
        self.websocket.send(json.dumps({"is_speaking": False}))
        
        # 2. 等待最终结果 (带超时)
        if not self.result_event.wait(timeout=self.final_result_timeout):
            logger.warning(f"Timeout waiting for final result after {self.final_result_timeout}s")
        
        logger.info(f"Recording stopped, final_text: '{self.final_text}'")

    def _message_handler(self):
        try:
            while self.websocket:
                try:
                    meg = json.loads(self.websocket.recv(timeout=1))
                except BaseException as e:
                    if not self.running:
                        self.result_event.set()
                    continue
                
                if "text" in meg:
                    if meg.get("mode") == "2pass-online":
                        # logger.info(f"Listening: {meg['text']}")
                        pass
                    elif meg.get("mode") in ["offline", "2pass-offline"] or meg.get("is_final"):
                        self.final_text = meg['text']
                        if not self.running:
                            logger.info(f"Final Result: {self.final_text}")
     
                if meg.get("is_final", False) == False:  # 明确检查 is_final=False 表示处理完成
                    if not self.running:
                        self.result_event.set()

        except Exception as e:
            pass

    def start(self):
        self.final_text = ''
        self._record_microphone()
        return self.final_text

def recognize_speech(host="172.30.3.7", port=10095):
    recognizer = SpeechRecognizer(host, port)
    return recognizer

if __name__ == "__main__":
    res = recognize_speech()
    while True:
        try:
            text = res.start()
            logger.info(f"Recognized: {text}")
        except KeyboardInterrupt:
            break