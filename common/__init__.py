import logging
import colorlog
import loguru
import os

if not os.path.exists('assets'):
    os.makedirs('assets')

# console_handler = colorlog.StreamHandler()
# console_handler.setLevel(logging.INFO)  
# console_handler.setFormatter(colorlog.ColoredFormatter(
#     "%(log_color)s%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
#     datefmt=None,
#     reset=True,
#     log_colors={
#         'DEBUG':    'cyan',
#         'INFO':     'green',
#         'WARNING':  'yellow',
#         'ERROR':    'red',
#         'CRITICAL': 'red,bg_white',
#     },
#     secondary_log_colors={},
#     style='%'
# ))

# file_handler = logging.FileHandler("xjrobot.log", encoding="utf-8")
# file_handler.setLevel(logging.DEBUG)  # 确保文件能输出 DEBUG 及以上级别
# file_handler.setFormatter(logging.Formatter(
#     "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
# ))

# logging.basicConfig(
#     level=logging.INFO,
#     handlers=[file_handler, console_handler]
# )
# logger = logging.getLogger(__name__)
logger = loguru.logger
