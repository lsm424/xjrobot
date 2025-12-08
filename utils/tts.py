import asyncio
import edge_tts
import subprocess  # 替换 pyaudio 为 subprocess
import queue
import threading
import time
import re
import shutil
from logger import logger
# from loguru import logger
# 假设 text_splitter 在 utils 包下，如果在其他位置请调整引用
from utils.text_splitter import TextSplitter
# from text_splitter import TextSplitter
class CosyTTS:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        # server_ip 和 server_port 在 edge_tts 中不需要，保留以维持接口一致
        self.voice = voice 
        
        # 检查 ffplay 是否可用
        if not shutil.which("ffplay"):
            logger.error("未找到 ffplay，请确保安装了 FFmpeg 并将其加入了系统环境变量 PATH 中。")
        
        # 文本队列：接收外部传入的完整文本
        self.text_queue = queue.Queue()
        # 音频队列：存放待播放的音频数据块 (bytes)
        self.audio_queue = queue.Queue()
        # 控制队列：用于接收播放控制信号（如刷新、停止）
        self.control_queue = queue.Queue()
        
        # 播放完成事件：用于通知 wait_until_done 方法播放已完成
        self.playback_done_event = threading.Event()
        
        self.splitter = TextSplitter()
        self.is_running = False
        
        # 播放进程句柄
        self.player_process = None
        
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
        
        logger.info("EdgeTTS 服务已启动 (使用 ffplay 播放)")

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
                
                # 1. 文本预处理 (可选)
                # text = self._preprocess_text(text)
                
                # 2. 内部进行文本分段
                segments = self.splitter.split_text(text)
                
                # 3. 逐段请求音频 (保证顺序)
                for seg in segments:
                    if not seg.strip():
                        continue
                    # 这里是阻塞的，必须等这一段的音频流全部接收并放入队列完毕
                    self._stream_audio_to_queue(seg)
                
                self.text_queue.task_done()
                
            except Exception as e:
                logger.error(f"TTS 合成线程异常: {e}")
                time.sleep(1)

    def _stream_audio_to_queue(self, text):
        """
        使用 edge_tts 生成音频并将流式数据实时推入 audio_queue
        """
        async def _gen_audio():
            try:
                communicate = edge_tts.Communicate(text, self.voice)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        # edge_tts 返回的是 mp3 数据块，直接放入队列
                        # 稍后由 ffplay 通过 pipe:0 自动解码播放
                        self.audio_queue.put(chunk["data"])
            except Exception as e:
                logger.error(f"EdgeTTS 生成异常: {e}")

        try:
            asyncio.run(_gen_audio())
        except Exception as e:
            logger.error(f"运行 asyncio 异常: {e}")

    def _player_worker(self):
        """
        最终消费者：消费 audio_queue -> ffplay 进程 (stdin)
        解决了之前 PyAudio 无法直接播放 MP3 的问题
        """
        # 启动 ffplay 子进程，从 stdin 读取数据，不显示窗口，静默日志
        # -autoexit 在 stdin 关闭后退出，但在流式播放中我们保持 stdin 打开
        # -nodisp 隐藏图形窗口
        # -cache 增大缓存以减少卡顿
        cmd = [
            'ffplay', 
            '-i', 'pipe:0', 
            '-nodisp', 
            '-loglevel', 'quiet', 
            '-autoexit'
        ]
        
        def _start_player():
            """启动一个新的 ffplay 播放器进程"""
            try:
                self.player_process = subprocess.Popen(
                    cmd, 
                    stdin=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    bufsize=0 # 无缓冲写入
                )
                return True
            except FileNotFoundError:
                logger.error("启动播放器失败：未找到 ffplay 命令")
                return False
            except Exception as e:
                logger.error(f"启动播放器异常: {e}")
                return False

        # 初始启动播放器
        if not _start_player():
            return

        try:
            while self.is_running:
                try:
                    # 非阻塞获取音频块（超时100ms）
                    chunk = None
                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                        if chunk is None: break
                    except queue.Empty:
                        # 音频队列空，检查控制队列
                        pass

                    # 检查控制队列（非阻塞）
                    control_cmd = None
                    try:
                        control_cmd = self.control_queue.get_nowait()
                    except queue.Empty:
                        pass

                    # 处理音频数据
                    if chunk:
                        # 将 MP3 数据块写入 ffplay 的标准输入
                        if self.player_process and self.player_process.stdin:
                            try:
                                self.player_process.stdin.write(chunk)
                                self.player_process.stdin.flush()
                            except (BrokenPipeError, OSError):
                                logger.warning("播放器管道断开，尝试重启播放器...")
                                # 尝试重启播放器
                                if self.player_process:
                                    self.player_process.kill()
                                if _start_player():
                                    self.player_process.stdin.write(chunk)
                                    self.player_process.stdin.flush()
                        self.audio_queue.task_done()
                    
                    # 处理控制命令
                    if control_cmd == "flush":
                        logger.info("收到播放刷新命令，等待当前音频播放完成...")
                        # 关闭 stdin，让 ffplay 播放完缓冲的音频后自动退出
                        if self.player_process and self.player_process.stdin:
                            try:
                                self.player_process.stdin.close()
                            except Exception as e:
                                logger.error(f"关闭播放器 stdin 失败: {e}")
                        
                        # 等待播放器进程退出
                        try:
                            self.player_process.wait(timeout=5)
                            logger.info("当前音频播放完成")
                            # 触发播放完成事件
                            self.playback_done_event.set()
                            # 重置事件，为下次使用做准备
                            self.playback_done_event.clear()
                        except subprocess.TimeoutExpired:
                            logger.warning("播放器超时未退出，强制终止")
                            self.player_process.kill()
                        
                        # 重新启动播放器，准备下一次播放
                        _start_player()
                    
                    # 检查播放器进程是否意外退出
                    if self.player_process and self.player_process.poll() is not None:
                        logger.warning("播放器进程意外退出，重新启动")
                        _start_player()
                    
                except Exception as e:
                    logger.error(f"TTS 播放线程异常: {e}")
        finally:
            # 清理工作
            if self.player_process:
                try:
                    if self.player_process.stdin:
                        self.player_process.stdin.close()
                    self.player_process.terminate()
                    self.player_process.wait(timeout=2)
                except Exception:
                    pass
            
            # 确保播放完成事件被触发
            self.playback_done_event.set()

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
        # 放入 None 以解除队列阻塞
        self.text_queue.put(None)
        self.audio_queue.put(None)
        
        if self.player_process:
            try:
                self.player_process.terminate()
            except:
                pass

    def wait_until_done(self):
        """
        可选：阻塞等待所有文本和音频播放完毕
        确保最后一句语音播放完毕
        """
        # 1. 等待文本处理完成（所有文本都已转换为音频块）
        logger.info("等待文本处理完成...")
        self.text_queue.join()
        
        # 2. 等待所有音频块都被发送到播放器
        logger.info("等待音频数据发送完成...")
        self.audio_queue.join()
        
        # 3. 发送刷新命令，让播放器播放完剩余音频后通知我们
        logger.info("发送播放刷新命令...")
        self.control_queue.put("flush")
        
        # 4. 等待播放完成事件（最长等待10秒）
        logger.info("等待最后一段音频播放完成...")
        self.playback_done_event.wait(timeout=10)
        
        logger.info("所有音频播放完毕")

if __name__ == "__main__":
    # 测试代码
    tts = CosyTTS(voice="zh-CN-XiaoxiaoNeural")
    tts.add_text("森林住着")
    tts.add_text("一只总爱晚")
    tts.add_text("归的狐狸，它")
    
    logger.info("等待所有语音播放完毕...")
    tts.wait_until_done()
    logger.info("测试完成，退出程序")
    tts.stop()