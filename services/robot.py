from services.brain_service import RobotBrainService
from services.robot_tts import RobotTTS
from common import logger
from common.config import cfg
from services.robot_state import RobotState
import os
from services.robot_state import RobotState, RobotAction
from infra.audio import audio_player
class Robot:

    def __init__(self):
        stt_type = cfg.get('stt', 'type')
        if stt_type == 'self_realtime_stt':
            from services.realtime_stt.self_realtime_stt import SelfRealtimeSTT
            self.rl_stt = SelfRealtimeSTT()
        else:
            from services.realtime_stt.fast_realtime_stt import FastRealtimeSTT
            self.rl_stt = FastRealtimeSTT()

        self.robot_brain = RobotBrainService(
            llm_api=cfg.get('llm', 'ollama_api_url'), 
            model_name=cfg.get('llm', 'llm_mode')
        )
        self.tts = RobotTTS(cfg.get('tts', 'paddle_server_ip'), 
            cfg.getint('tts', 'paddle_server_port'))
        

    def run(self):
        while RobotState.running:
            self.tts.wait_tts_finish()
            logger.info('请说话')
            user_input = self.rl_stt.start_recording()
            logger.info(f'用户说: {user_input}')
            if not user_input:
                logger.info('user_input为None，继续下一轮循环')
                continue
            for answer in self.robot_brain.ask(user_input):
                self._handle_action(answer['action_type'], answer['content'])

    def _handle_action(self, action_type, content):
        if action_type == RobotAction.PRE_ANSWER:
            logger.info(f'预回复: {content}')
            self.tts.input_text(content)
        elif action_type == RobotAction.REGULAR_ANSWER:
            logger.info(f'机器人说: {content}')
            self.tts.input_text(content)
        elif action_type == RobotAction.PLAY_AUDIO_IMMEDIATE:
            logger.info(f'立即播放音频: {content}')
            audio_player.play(content)
        elif action_type == RobotAction.PLAY_AUDIO_WHEN_FINAL:
            logger.info(f'最终动作指令播放音频: {content}')
            self.tts.wait_tts_finish()
            audio_player.play(content)
        elif action_type == RobotAction.STOP_AUDIO:
            logger.info('停止播放音频')
            audio_player.safe_stop()
