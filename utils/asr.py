import os
import time
import websockets
import ssl
import json
import pyaudio
import struct
import math
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
import threading
from collections import deque
import concurrent.futures
from logger import logger
# from loguru import logger
try:
    from utils.turn_detector import TurnDetector
except ImportError:
    from turn_detector import TurnDetector

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
        self.silence_threshold = 100
        self.websocket = None
        self.max_silence_seconds = 1.5
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        self.turn_detector = TurnDetector()
        self.model_check_min_silence = 0.3 
        
        # === 新增: 等待最终结果的超时时间 ===
        self.final_result_timeout = 2.0

        self.rms_list = []
        
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
        self.rms_list.append(rms)
        return rms < self.silence_threshold
    
    def _record_microphone(self, start=0):
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
        is_silent = True
        silent_list = [1]*10
        self.running = True
        self.result_event.clear()

        audio_context_buffer = deque(maxlen=256000)
        
        last_model_submit_time = 0
        model_check_interval = 0.3
        prediction_future = None
        complete_count = 0  # 连续 complete 次数计数

        while self.websocket:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                # if not is_silent and has_spoken:
                #     self.websocket.send(data)
                # logger.info(f"is_silent: {is_silent}, has_spoken: {has_spoken}")
                if (sum(silent_list) >= len(silent_list) / 2 or not is_silent) and has_spoken:
                    self.websocket.send(data)
                    # logger.info(f"send data {silent_list}")
                audio_context_buffer.extend(data)
                
                is_silent = self._is_silent(data)
                silent_list.append(0) if is_silent else silent_list.append(1) 
                silent_list = silent_list[-10:]                
                if prediction_future is not None and prediction_future.done():
                    try:
                        is_complete, prob = prediction_future.result()
                        logger.info(f"End of speech detected result (Smart Model: {'complete' if is_complete else 'incomplete'}, Prob: {prob:.2f}). "
                                   f"Complete count: {complete_count}")
                        if is_complete:
                            complete_count += 1
                            if complete_count >= 2:
                                logger.info("End of speech detected (2 consecutive complete).")
                                self.running = False
                                break
                        else:
                            complete_count = 0
                            # silence_start_time = None  # incomplete 时重置静音计时
                    except Exception as e:
                        logger.error(f"Model prediction error: {e}")
                    finally:
                        prediction_future = None
                # logger.info(f"is_silent: {is_silent}, has_spoken: {has_spoken}")
                if not is_silent:
                    if not has_spoken:
                        self.final_text = ''
                    has_spoken = True
                    silence_start_time = None 
                    complete_count = 0  # 重新开始说话，重置计数
                    # self.final_text = ''
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
        logger.info(f"Sending final flush signal to server... {self.running}")
        if start==1:
            return
        self.websocket.send(json.dumps({"is_speaking": False}))
        # time.sleep(0.01)  
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
                    continue
                if "text" in meg:
                    if meg.get("mode") in ["offline", "2pass-offline"] or meg.get("is_final"):
                        # self.final_text += meg['text']
                        # logger.info(f"Listening: {meg['text']}")
                        if not self.running:
                            logger.info(f"Final Result: {self.final_text} {meg.get("is_final", None)}")
                            if meg.get("is_final", None) == False:
                                self.final_text = meg['text']
                                self.result_event.set()

        except Exception as e:
            pass

    def start(self):
        self.final_text = ''
        self._record_microphone()
        # while True:
        #     time.sleep(0.01)
        #     yield self.final_text
        return self.final_text
    
    # def get_asr_text(self):
    #     cnt = 0
    #     for user_query in self.start():
    #         cnt+=1
    #         if user_query or cnt>10:
    #             break
    #     return user_query
def set_silence_threshold(recognizer):
    recognizer._record_microphone(start=1)
    recognizer.silence_threshold = max(recognizer.rms_list)+500
    logger.info(f"silence_threshold: {recognizer.silence_threshold}")

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