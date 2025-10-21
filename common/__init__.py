# import logging
# import colorlog
import loguru
import os

if not os.path.exists('assets'):
    os.makedirs('assets')

logger = loguru.logger
