import zipfile
import os
import time
import queue
import threading
import requests
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import io,sys
import shutil
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
from common import logger
import pygame
import subprocess
import platform
import tarfile
threshold=2
silence_duration=2
samplerate=8000

class AudioTool:
    def __init__(self):
        pygame.mixer.init()
    
    def play_wav(self, wav_path):
        # 初始化pygame的mixer模块
        # 加载WAV文件
        logger.info(f'broadcasting path_name: {wav_path}')
        pygame.mixer.music.load(wav_path)
        # 播放音乐
        pygame.mixer.music.play()

        # 等待音频播放完毕或被停止
        while pygame.mixer.music.get_busy():
            # 停止播放
            pygame.mixer.music.stop()

    def stop_play_audio(self):
        # 停止播放音乐
        pygame.mixer.music.stop()

    # 监听并存储为wav文件
    def record_until_silence(self, on_record_start=None, on_record_end=None):
        logger.info("🎙 录音监听...")
        block_duration = 0.1  # 每块音频时长（秒）
        block_size = int(samplerate * block_duration)
        silence_blocks = int(silence_duration / block_duration)
        buffer = []
        recording_started = False
        silent_count = 0
        try:
            with sd.InputStream(samplerate=samplerate, channels=1, dtype='float32') as stream:
                while True:
                    audio_block, _ = stream.read(block_size) # 读一个语句块
                    volume = np.linalg.norm(audio_block) # 计算音量
                    if volume > threshold:
                        logger.info(volume)
                    if volume > threshold:
                        # 若音量大于预定值，且不是bot在聊天
                        if not recording_started: # 若没有启动录音
                            recording_started = True # 置录音启动
                            logger.info('开始录音')
                            if on_record_start:
                                on_record_start()
                        silent_count = 0 # 静音时长置0
                    elif recording_started: # 已启动录音，但音量不到预定值
                        silent_count += 1 # 静音时长加1
                    if recording_started:
                        # 如果没有bot说话和wav播放，就说明是用户的语音
                        buffer.append(audio_block)
                    if recording_started and silent_count >= silence_blocks:
                        # 用户语音录制结束
                        logger.info("⏹ 检测到持续静音，结束录音")
                        break
        except BaseException as e:
            return None

        if not buffer:
            logger.info("⚠ 没有检测到用户语音")
            return None

        if on_record_end:
            on_record_end()
        
        # 存储用户语音
        audio_data = np.concatenate(buffer, axis=0)
        # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # wav.write(wav_path, samplerate, (audio_data * 32767).astype(np.int16))
        wav_io = io.BytesIO()
        wav.write(wav_io, samplerate, (audio_data * 32767).astype(np.int16))
        wav_io.seek(0)
        logger.info("✅ 录音完成，WAV 数据已写入内存")
        return wav_io

audio_tool = AudioTool()


class FlacStreamPlayer:
    """
    在线解析 FLAC 链接，边下边播
    使用 ffmpeg 解码并播放
    """
    linux_download_url = 'https://xget.xi-xu.me/gh/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz'
    windows_download_url = 'https://xget.xi-xu.me/gh/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip'
    def __init__(self, buffer_size: int = 1024 * 64):
        self.buffer_size = buffer_size
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.ffmpeg_proc = None

        # 根据操作系统设置ffmpeg路径
        system = platform.system().lower()
        if system not in ('windows', 'linux'):
            raise RuntimeError(f"不支持的操作系统: {system}")
        ffmpeg_dir = os.path.join('assets', 'ffmpeg', system)
        if not os.path.exists(ffmpeg_dir):
            os.makedirs(ffmpeg_dir)
            self._download_ffmpeg(self.linux_download_url if system == 'linux' else self.windows_download_url, ffmpeg_dir)

        # 将ffmpeg目录添加到PATH环境变量
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

    @staticmethod
    def _download_ffmpeg(url, ffmpeg_dir):
        """下载并解压ffmpeg"""
        # 下载ffmpeg
        logger.info(f"正在下载 ffmpeg 到 {ffmpeg_dir}...")
        resp = requests.get(url, stream=True, timeout=10)
        resp.raise_for_status()
        # 将下载的压缩包写入本地临时文件
        filename = os.path.basename(url)
        tar_path = os.path.join(ffmpeg_dir, filename)
        with open(tar_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"✅ 已成功下载 ffmpeg 压缩包到 {tar_path}")
        # 解压到ffmpeg_dir目录下
        if filename.endswith('.tar.xz'):
            with tarfile.open(tar_path, mode='r:xz') as tar:
                tar.extractall(path=ffmpeg_dir)
        elif filename.endswith('.zip'):
            with zipfile.ZipFile(tar_path, 'r') as zip_ref:
                zip_ref.extractall(ffmpeg_dir)
        # 解压完成后删除原压缩包
        bin_dir = os.path.join(ffmpeg_dir, filename.split('.')[0], 'bin')
        # 拷贝bin目录下的所有文件到ffmpeg_dir下
        for item in os.listdir(bin_dir):
            src = os.path.join(bin_dir, item)
            dst = os.path.join(ffmpeg_dir, item)
            if os.path.isfile(src):
                os.rename(src, dst)
        # 解压完成后删除原压缩包

        shutil.rmtree(os.path.join(ffmpeg_dir, filename.split('.')[0]))
        os.remove(tar_path)
        logger.info(f"✅ 已成功下载并解压 ffmpeg 到 {ffmpeg_dir}")

    def _play_worker(self, source):
        """播放线程：从队列读取数据并直接喂给 ffplay 实现真正的边下边播"""
        self.stop_event.clear()
        # 启动 ffplay 子进程，直接从 stdin 读取 FLAC 数据流
        self.ffmpeg_proc = subprocess.Popen([
            'ffplay', 
            '-i', 'pipe:0',
            '-autoexit',
            '-nodisp',
            '-loglevel', 'quiet'
        ], stdin=subprocess.PIPE, bufsize=0)
        try:
            # 流式写入数据
            for chunk in self.create_stream_generator(source, self.buffer_size):
                if not self.is_playing:
                    break
                self.ffmpeg_proc.stdin.write(chunk)
                self.ffmpeg_proc.stdin.flush()
            
            # 完成写入
            self.ffmpeg_proc.stdin.close()
            
            # 等待播放完成
            if self.is_playing:
                self.ffmpeg_proc.wait()
                logger.info("播放完成")
        except Exception as e:
            logger.error(f"播放出错: {e}")
            self.safe_stop()
            

    def play(self, source: str, join=False):
        """开始边下边播（非阻塞模式）"""
        # 首先停止当前播放（如果有）
        if self.safe_stop():
            time.sleep(1)
        if join:
            self._play_worker(source)
        else:
            threading.Thread(target=self._play_worker, args=(source,), daemon=True).start()
        return
        
    @property
    def is_playing(self):
        return not self.stop_event.is_set()

    def safe_stop(self):
        """停止播放和下载"""
        # 设置停止事件
        if not self.is_playing:
            logger.info("当前未在播放音乐，无需停止")
            return False

        logger.info("停止播放音乐...")
        self.stop_event.set()

        # 安全终止ffmpeg进程
        if self.ffmpeg_proc:
            try:
                if self.ffmpeg_proc.poll() is None:
                    self.ffmpeg_proc.terminate()
                    # 添加超时，避免永久阻塞
                    try:
                        self.ffmpeg_proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        logger.warning("ffmpeg进程终止超时")
            except Exception as e:
                logger.error(f"终止ffmpeg进程时出错: {e}")
            finally:
                # 确保清除进程引用
                self.ffmpeg_proc = None
        # 清除正在播放音乐的标志位
        logger.info("音乐播放已停止，资源已清理")
        return True

    def create_stream_generator(self, source, chunk_size=8192):
        """创建统一的流式生成器"""
        if isinstance(source, str) and source.startswith(('http://', 'https://')):
            # 网络流
                response = requests.get(source, stream=True)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=chunk_size):
                    yield chunk
                response.close()        
        else:
            # 本地文件
            with open(source, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

audio_player = FlacStreamPlayer()

if __name__ == '__main__':
    audio_player.play(r'assets\story\audio\草船借箭.wav', join=True)
