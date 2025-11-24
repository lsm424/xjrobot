# from loguru import logger
import sounddevice as sd
import soundfile as sf
import torch
from paddlespeech.server.bin.paddlespeech_client import TTSOnlineClientExecutor
import re
from logger import logger
import os
import asyncio  # <--- 新增引入

# # 引入TTSOnlineClientExecutor后日志打印失效，重新挂载日志处理器
log_dir = './logger/logs'
os.makedirs(log_dir, exist_ok=True)
logger.remove()  # 移除默认处理器
logger.add(
    os.path.join(log_dir, 'llm_interactions.log'),
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 添加控制台输出
logger.add(
    lambda msg: print(msg, end=""),
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

class PaddleTTS:
    def __init__(self, server_ip, server_port):
        
        self.client_executor = TTSOnlineClientExecutor()
        self.paddle_server_ip = server_ip
        self.paddle_server_port = server_port

    def tts(self, text, speak=True, out_file="./assets/synth_audio_websocket.wav"):
        replacements = {
            r"[\"'!]": "",       # 移除引号和感叹号
            r"°": "度",         # 将度数符号替换为汉字
             r"~": "。",         # 将波浪号替换为句号
            r"\n\n": "，",      # 将连续换行替换为逗号
            r'([^\u4e00-\u9fa5\d])\1+': "。" # 非连续的中文和数字，则置。
        }
        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text)
        # logger.info(f'准备调用tts: {text}')
        
        try:
            # --- 修复开始: 检查并修复子线程中缺失 event loop 的问题 ---
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Loop is closed")
            except RuntimeError:
                # 如果当前线程没有 loop (例如在 Thread-1 中)，则创建一个新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            # --- 修复结束 ---

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

# if __name__ == "__main__":
#     tts = PaddleTTS(server_ip='172.30.3.7', server_port=8092)
#     tts.tts("当前音乐播放完毕，请问还有什么能够帮您的吗？")