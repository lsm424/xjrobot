from agent_framework import AgentFramework
import json
from logger import logger
from utils.audio import audio_player
from utils import asr  # 导入我们修改后的 asr 模块

agent = AgentFramework(config_path="config.ini")
logger.info("=== Agent Framework 演示 ===")

# 尝试播放启动音，如果文件不存在则忽略
try:
    audio_player.play_file('./assets/system_start.wav')
except Exception:
    pass

while True:
    logger.info("\n--- 等待指令 ---")
    
    user_query = asr.recognize_speech(host="172.30.3.7", port=10095)
    # ============================

    if not user_query:
        logger.warning("未检测到语音或识别失败，请重试。")
        continue

    logger.info(f"识别到的内容: {user_query}")
        
    if user_query.strip() == "":
        continue

    # 调用 Agent 处理
    try:
        agent.process_user_query(user_query)
    except Exception as e:
        logger.error(f"处理出错: {e}")