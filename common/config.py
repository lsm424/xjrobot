# -*- coding: utf-8 -*-
'''
@File    :   config.py
@Time    :   2025/10/13 09:19:01
@Author  :   wadesmli 
@Version :   1.0
@Desc    :   None
'''

import configparser
import os

cfg = configparser.ConfigParser()
cfg.read(os.path.join('.', 'config.ini'), encoding="utf-8")
