# turn_detector.py
import os
import numpy as np
import onnxruntime as ort
from transformers import WhisperFeatureExtractor

# 默认模型路径，与 inference.py 保持一致
ONNX_MODEL_PATH = "./assets/model/smart-turn-v3.1.onnx"

class TurnDetector:
    def __init__(self, model_path=ONNX_MODEL_PATH):
        """
        初始化模型 session 和特征提取器
        """
        self.model_path = model_path
        print(f"Loading Turn Detector model from {self.model_path}...")
        
        # 初始化 Feature Extractor
        self.feature_extractor = WhisperFeatureExtractor(chunk_length=8)
        
        # 初始化 ONNX Session
        so = ort.SessionOptions()
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        so.inter_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        try:
            self.session = ort.InferenceSession(self.model_path, sess_options=so)
            print("Turn Detector model loaded successfully.")
        except Exception as e:
            print(f"Error loading Turn Detector model: {e}")
            self.session = None
        # 用 1 秒静音初始化模型，让 ONNX 预热并避免首次调用阻塞
        silence = np.zeros(16000, dtype=np.float32)
        dummy_bytes = (silence * 32768).astype(np.int16).tobytes()
        self.predict(dummy_bytes)

    def _bytes_to_float32(self, audio_bytes):
        """将 int16 字节流转换为 float32 numpy 数组"""
        int16_data = np.frombuffer(audio_bytes, dtype=np.int16)
        return int16_data.astype(np.float32) / 32768.0

    def truncate_audio_to_last_n_seconds(self, audio_array, n_seconds=8, sample_rate=16000):
        """截取最后 N 秒音频用于推理"""
        max_samples = n_seconds * sample_rate
        if len(audio_array) > max_samples:
            return audio_array[-max_samples:]
        elif len(audio_array) < max_samples:
            padding = max_samples - len(audio_array)
            return np.pad(audio_array, (padding, 0), mode='constant', constant_values=0)
        return audio_array

    def predict(self, audio_bytes):
        """
        输入音频字节流，返回预测结果
        Returns:
            is_complete (bool): 是否说完
            probability (float): 完成的概率
        """
        if self.session is None:
            # 如果模型没加载成功，默认返回 False，依赖原始的静音超时逻辑
            return False, 0.0

        audio_array = self._bytes_to_float32(audio_bytes)
        
        # 预处理：截取最后 8 秒
        processed_audio = self.truncate_audio_to_last_n_seconds(audio_array, n_seconds=8)

        # 提取特征
        inputs = self.feature_extractor(
            processed_audio,
            sampling_rate=16000,
            return_tensors="np",
            padding="max_length",
            max_length=8 * 16000,
            truncation=True,
            do_normalize=True,
        )

        input_features = inputs.input_features.squeeze(0).astype(np.float32)
        input_features = np.expand_dims(input_features, axis=0)

        # 推理
        outputs = self.session.run(None, {"input_features": input_features})
        probability = outputs[0][0].item()
        
        # 阈值判定 (0.5)
        is_complete = probability > 0.5
        
        return is_complete, probability