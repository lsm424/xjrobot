from abc import ABC, abstractmethod
from typing import Literal
from langchain_core.tools.structured import StructuredTool

StructuredTool.__str__ = lambda x: f'{x.name}, {x.description}'

# 定义抽象类
class ToolBase(ABC):
    def __init__(self, name=''):
        self.name = name

    @abstractmethod
    def usage(self) -> Literal[str|None]:
        """
        用于描述工具包的使用方法/流程
        """
        pass

    def get_tool_functions(self) -> list[StructuredTool]:
        """
            自动获取所有被 @tool 装饰的方法（通过 description 属性判断）
        """
        tool_funcs = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, 'description'):
                tool_funcs.append(attr)
        return tool_funcs

    def tools_info(self) -> str:
        """
        用于描述工具包的所有工具
        """
        return [str(x) for x in self.get_tool_functions()]