import requests
import pyaudio
import re
import queue
import threading
import time
from logger import logger
# 假设 text_splitter 在 utils 包下，如果在其他位置请调整引用
from utils.text_splitter import TextSplitter

class CosyTTS:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.target_sr = 22050  # 目标采样率
        
        # 文本队列：接收外部传入的完整文本
        self.text_queue = queue.Queue()
        # 音频队列：存放待播放的音频数据块 (bytes)
        self.audio_queue = queue.Queue()
        
        self.splitter = TextSplitter()
        self.is_running = False
        
        # 播放器配置
        self.p = pyaudio.PyAudio()
        
        # 启动工作线程
        self.start()

    def start(self):
        """启动合成和播放线程"""
        if self.is_running:
            return
        self.is_running = True
        
        # 1. 合成线程：取文本 -> 分词 -> 请求API -> 存入音频队列
        self.synth_thread = threading.Thread(target=self._synthesis_worker, daemon=True)
        self.synth_thread.start()
        
        # 2. 播放线程：取音频队列 -> 播放
        self.play_thread = threading.Thread(target=self._player_worker, daemon=True)
        self.play_thread.start()
        
        logger.info("PaddleTTS 服务已启动 (后台线程运行中)")

    def add_text(self, text: str):
        """
        [外部接口] 添加文本到播放列表
        """
        if not text:
            return
        logger.info(f"TTS 收到文本: {text[:20]}...")
        self.text_queue.put(text)

    def _synthesis_worker(self):
        """
        消费者-生产者中间层：
        消费 text_queue (文本) -> 生产 audio_queue (音频流)
        """
        while self.is_running:
            try:
                # 阻塞获取文本
                text = self.text_queue.get()
                if text is None: break
                
                # 1. 文本预处理
                # text = self._preprocess_text(text)
                
                # 2. 内部进行文本分段 (Splitter logic)
                # 使用传入的 TextSplitter 对长文本进行切分
                segments = self.splitter.split_text(text)
                
                # 3. 逐段请求音频 (保证顺序)
                for seg in segments:
                    if not seg.strip():
                        continue
                    # 这里是阻塞的，必须等这一段的音频流全部接收并放入队列完毕
                    # 才能处理下一段，这样保证了 audio_queue 里的数据顺序是正确的
                    self._stream_audio_to_queue(seg)
                
                self.text_queue.task_done()
                
            except Exception as e:
                logger.error(f"TTS 合成线程异常: {e}")
                time.sleep(1)

    def _stream_audio_to_queue(self, text):
        """
        请求 TTS API 并将流式数据实时推入 audio_queue
        """
        try:
            url = f"http://{self.server_ip}:{self.server_port}/inference_sft"
            payload = {
                'tts_text': text,
                'spk_id': '中文女'
            }
            
            # stream=True 开启流式响应
            response = requests.request("GET", url, data=payload, stream=True)
            
            if response.status_code != 200:
                logger.error(f"TTS请求失败: {response.status_code}")
                return

            # 按块读取，一拿到 chunk 就放入播放队列
            # 这样播放器可以立即开始播放，而不需要等整段下载完
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    self.audio_queue.put(chunk)
                    
        except Exception as e:
            logger.error(f"TTS 请求流异常: {e}")

    def _player_worker(self):
        """
        最终消费者：消费 audio_queue -> 扬声器
        """
        stream = self.p.open(format=pyaudio.paInt16,
                             channels=1,
                             rate=self.target_sr,
                             output=True)
        
        while self.is_running:
            try:
                # 阻塞获取音频块
                chunk = self.audio_queue.get()
                if chunk is None: break
                
                # 播放
                stream.write(chunk)
                self.audio_queue.task_done()
                
            except Exception as e:
                logger.error(f"TTS 播放线程异常: {e}")
        
        stream.stop_stream()
        stream.close()

    def _preprocess_text(self, text):
        replacements = {
            r"[\"'!]": "",       
            r"°": "度",         
            r"～": "。",         
            r"\n\n": "，",      
            r'([^\u4e00-\u9fa5\d])\1+': "。" 
        }
        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text)
        return text

    def stop(self):
        self.is_running = False
        self.p.terminate()

    def wait_until_done(self):
        """
        可选：阻塞等待所有文本和音频播放完毕
        """
        self.text_queue.join()
        self.audio_queue.join()

if __name__ == "__main__":
    # 测试代码
    tts = PaddleTTS(server_ip='127.0.0.1', server_port=8092)
    tts.add_text("你好，这是第一段测试文本。")
    tts.add_text("紧接着是第二段，应该流畅播放。")
    
    # 保持主线程运行以进行测试
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tts.stop()