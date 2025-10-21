from abc import ABC, abstractmethod
from typing import Literal
from langchain_core.tools.structured import StructuredTool
from common import logger

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
        # logger.info(f"开始查找{self.name}的工具函数...")
        for attr_name in dir(self):
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue
            attr = getattr(self, attr_name)
            # logger.info(f"检查属性: {attr_name}, 是否有description: {hasattr(attr, 'description')}")
            if hasattr(attr, 'description'):
                logger.info(f"找到工具函数: {attr_name}, description: {attr.description}")
                tool_funcs.append(attr)
        logger.info(f"{self.name}找到{len(tool_funcs)}个工具函数")
        return tool_funcs


    def tools_info(self) -> str:
        """
        用于描述工具包的所有工具
        """
        return [str(x) for x in self.get_tool_functions()]