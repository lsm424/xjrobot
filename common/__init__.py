# import logging
# import colorlog
import loguru
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HOME'] = 'assets/model_dir'

if not os.path.exists('assets'):
    os.makedirs('assets')

logger = loguru.logger
