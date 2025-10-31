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
        self.download_queue = queue.Queue(maxsize=200)  # 限制缓存大小
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

    def _download_worker(self, resource_uri):
        """后台下载线程：持续下载 FLAC 数据并写入队列"""
        try:
            if resource_uri.startswith('http'):
                with requests.get(resource_uri, stream=True, timeout=10) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_content(chunk_size=self.buffer_size):
                        if not self.is_playing:
                            break
                        if chunk:
                            self.download_queue.put(chunk)
            elif os.path.exists(resource_uri):
                # 本地文件：分块读取并推送到队列
                with open(resource_uri, 'rb') as f:
                    while self.is_playing:
                        chunk = f.read(self.buffer_size)
                        if not chunk:
                            break
                        self.download_queue.put(chunk)
            else:
                logger.error(f"不支持的资源类型: {resource_uri}")
        except Exception as e:
            logger.error(f"下载出错: {e}")
        finally:
            # 发送结束标记
            self.download_queue.put(None)

    def _play_worker(self):
        """播放线程：从队列读取数据并直接喂给 ffplay 实现真正的边下边播"""
        ffmpeg_proc = None  # 使用局部变量存储进程引用
        try:
            # 启动 ffplay 子进程，直接从 stdin 读取 FLAC 数据流
            cmd = ['ffplay', '-nodisp', '-autoexit', '-i', '-']
            ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL
            )
            
            # 更新实例变量
            self.ffmpeg_proc = ffmpeg_proc

            # 直接将下载的数据块写入 ffplay 的 stdin，实现边下边播
            while self.is_playing:
                try:
                    chunk = self.download_queue.get(timeout=1)
                    if chunk is None:  # 下载结束
                        break
                    if ffmpeg_proc.stdin and self.is_playing:
                        try:
                            ffmpeg_proc.stdin.write(chunk)
                            ffmpeg_proc.stdin.flush()  # 确保数据立即发送到 ffplay
                        except BrokenPipeError:
                            logger.warning("管道已关闭，停止写入数据")
                            break
                    # print(f"已播放数据块大小: {len(chunk)}")
                except queue.Empty:
                    continue
                except Exception as e:
                    if self.is_playing:
                        logger.error(f"播放数据块时出错: {e}")
            
            # 安全关闭 stdin，通知 ffplay 输入已结束
            try:
                if ffmpeg_proc.stdin:
                    ffmpeg_proc.stdin.close()
            except:
                pass

            # 等待 ffmpeg 结束
            try:
                if ffmpeg_proc:
                    ffmpeg_proc.wait(timeout=2)  # 添加超时避免永久阻塞
            except subprocess.TimeoutExpired:
                logger.warning("ffmpeg进程等待超时，强制终止")
                try:
                    ffmpeg_proc.terminate()
                except:
                    pass
        except Exception as e:
            logger.error(f"播放出错: {e}")
        finally:
            # 确保进程引用被清除
            self.ffmpeg_proc = None
            # 清空队列，避免下次播放时使用旧数据
            try:
                while not self.download_queue.empty():
                    self.download_queue.get_nowait()
            except:
                pass

    def play(self, resource: str):
        """开始边下边播（非阻塞模式）"""
        logger.info(f"播放: {resource}")
        # 首先停止当前播放（如果有）
        if self.safe_stop():
            time.sleep(1)

        # 完全重置所有状态
        self.stop_event.clear()  # 重置停止事件
        # 清空队列，确保没有旧数据
        try:
            while not self.download_queue.empty():
                self.download_queue.get_nowait()
        except:
            pass
                
        # 启动下载和播放线程
        dl_thread = threading.Thread(target=self._download_worker, args=(resource,), daemon=True)
        play_thread = threading.Thread(target=self._play_worker, daemon=True)

        dl_thread.start()
        play_thread.start()
        
        # 创建一个监控线程来处理播放完成后的清理工作
        threading.Thread(target=self._monitor_playback, 
                    args=(dl_thread, play_thread), daemon=True).start()

        # 立即返回，不阻塞主线程
        logger.info("音乐开始播放，主线程继续执行其他任务")
        return
        
    def _monitor_playback(self, dl_thread, play_thread):
        """监控播放过程并在完成后清理资源"""
        try:
            # 等待下载和播放线程结束
            while self.is_playing:
                if not dl_thread.is_alive() and self.download_queue.empty():
                    break
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"监控播放过程中出错: {e}")
        finally:
            # 确保资源被正确清理
            self.safe_stop()
            try:
                dl_thread.join(timeout=2)
                play_thread.join(timeout=2)
            except:
                pass
            logger.info("播放结束，资源已清理")
    
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
        
        # 清空队列，避免旧数据影响下次播放
        try:
            while not self.download_queue.empty():
                try:
                    self.download_queue.get_nowait()
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"清空队列时出错: {e}")
        
        # 清除正在播放音乐的标志位
        logger.info("音乐播放已停止，资源已清理")
        return True

audio_player = FlacStreamPlayer()
