import loguru
import os
# 确保日志文件夹存在
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
logger = loguru.logger
# 配置logger
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