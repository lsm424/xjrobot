import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import io
from common import logger
import pygame


threshold=2
silence_duration=2
samplerate=8000

class AudioTool:
    def __init__(self):
        pygame.mixer.init()
    
    def play_wav(self, wav_path):
        # 初始化pygame的mixer模块
        pygame.mixer.init()
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