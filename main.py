from agent_framework import AgentFramework
# import json
from logger import logger
# from utils.audio import audio_player
from utils import asr  # 导入我们修改后的 asr 模块

agent = AgentFramework(config_path="config.ini")
logger.info("=== Agent Framework 演示 ===")
# audio_input=asr.recognize_speech(host="172.30.3.7", port=10095)
audio_input=asr.recognize_speech(host="47.108.93.204", port=10095)
# 尝试播放启动音，如果文件不存在则忽略
try:
    # audio_player.play_file('./assets/system_start.wav')
    agent.tts_client.add_text("您好，请问有什么可以帮您的吗？")
    if agent.tts_client:
            agent.tts_client.wait_until_done()
except Exception:
    pass
while True:
    logger.info("\n--- 等待指令 ---")
    user_query = audio_input.start()
    # user_query = input()
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