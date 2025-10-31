from .base import ToolBase
from common import logger
from services.robot_state import RobotAction
from langgraph.config import get_stream_writer
from langgraph.types import Command
from langchain_core.messages import AnyMessage, BaseMessage, ToolMessage  # noqa: TC002
from langchain.tools import tool, ToolRuntime

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
    def pre_reply(message: str, runtime: ToolRuntime) -> str:
        """
        向用户发送预回复消息，提示即将进行的操作
        
        Args:
            message: 预回复消息内容，例如"正在搜索xxx的信息，请您耐心等待"
            
        Returns:
            str: 预回复状态信息
        """
        # logger.info(f"预回复消息: {message}")
        RobotAction.action_immediate(RobotAction.PRE_ANSWER, message)
        return "预回复消息播报成功"
        