import statistics
import threading
from langgraph.config import get_stream_writer
from langgraph.store.memory import InMemoryStore

class RobotState:
    running = True
    stt_tts_sema = threading.Semaphore(1)


class RobotAction:
    PRE_ANSWER = 'pre_answer'                       # 预回复
    REGULAR_ANSWER = 'regular_answer'               # 机器人普通回复
    PLAY_AUDIO_IMMEDIATE = 'play_audio_immediate'   # 立即播放音频
    PLAY_AUDIO_WHEN_FINAL = 'play_audio_when_final' # 最终动作指令播放音频
    STOP_AUDIO = 'stop_audio'                       # 停止播放音频

    def __setattr__(self, name, value):
        raise AttributeError("value is read-only")

    @staticmethod
    def action_immediate(action_type: str, content: str = None):
        """
            立即发送动作指令
        """
        get_stream_writer()({
            "action_type": action_type,
            "content": content
        })
    
    @staticmethod
    def action_when_final(action_type: str, content: str, store: InMemoryStore):
        """
            最终动作指令
        """
        store.put('action', 'final_action', {
            "action_type": action_type,
            "content": content
        })

    @staticmethod
    def pop_final_action(store: InMemoryStore) -> dict[str, str]:
        """
            获取最终动作指令
        """
        final_action = store.get('action', 'final_action')
        if final_action:
            final_action = final_action.value
            store.delete('action', 'final_action')
            return final_action
        return None