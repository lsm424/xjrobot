from .base import ToolBase
from langchain_core.tools import tool
from common import logger
from services.robot_state import RobotState

class PreReplyTool(ToolBase):
    def __init__(self):
        super().__init__(name="预回复工具")

    def usage(self) -> str:
        """
        预回复工具用于在执行耗时操作前，提前向用户说明即将进行的操作，减少等待感
        使用场景：当需要调用耗时工具（如搜索信息、播放音乐等）前，可以先调用此工具进行预回复
        """
        return "当需要执行耗时操作时，先调用pre_reply函数给出提示信息"

    @tool(description="预回复工具，用于在执行耗时操作前，提前向用户说明即将进行的操作,例如'正在搜索xxx的信息，请您耐心等待'")
    def pre_reply(message: str) -> str:
        """
        向用户发送预回复消息，提示即将进行的操作
        
        Args:
            message: 预回复消息内容，例如"正在搜索xxx的信息，请您耐心等待"
            
        Returns:
            str: 预回复状态信息
        """
        logger.info(f"预回复消息: {message}")
        
        # 检查是否有可用的TTS客户端
        if hasattr(RobotState, 'tts_client') and RobotState.tts_client:
            try:
                # 使用TTS客户端播报预回复消息
                RobotState.tts_client.input_text(message)
                return "预回复消息播报成功"
            except Exception as e:
                logger.error(f"预回复消息播报失败: {e}")
                return "预回复消息播报失败"
        else:
            logger.warning("TTS客户端未初始化，无法播报预回复消息")
            return "TTS客户端未初始化"