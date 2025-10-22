from .base import ToolBase
from .music_player import MusicPlayerTool
from .math_tools_demo import MathTool
from .get_weather import WeatherTool
from .news_search import NewsSearchTool
# 注册工具
def get_tools() -> list[ToolBase]:
    return [MusicPlayerTool(), MathTool(), WeatherTool(), NewsSearchTool()]