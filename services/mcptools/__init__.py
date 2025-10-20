from .base import ToolBase
from .music_player import MusicPlayerTool
from .math_tools_demo import MathTool

def get_tools() -> list[ToolBase]:
    return [MusicPlayerTool(), MathTool()]