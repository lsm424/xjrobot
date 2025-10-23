from .base import ToolBase
from .music_player import MusicPlayerTool
from .math_tools_demo import MathTool
from .get_weather import WeatherTool
from .news_search import NewsSearchTool
from .pre_reply import PreReplyTool  # 添加预回复工具导入

# 注册工具
def get_tools() -> list[ToolBase]:
    return [MusicPlayerTool(), MathTool(), WeatherTool(), NewsSearchTool(), PreReplyTool()]  # 添加预回复工具