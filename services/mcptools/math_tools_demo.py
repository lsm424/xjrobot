from mcp.server.fastmcp import FastMCP
import logging
from langchain.tools import tool
from common import logger
from .base import ToolBase
from pydantic import Field

# 创建 FastMCP 实例
logger.info(f'--------------------------------------------')

class MathTool(ToolBase):
    def __init__(self) -> None:
        super().__init__(name='数学计算器')

    def usage(self):
        return '''1.涉及数学表达式计算时，使用evaluate_expression工具
根据工具调用返回的结果综合回复，比如工具返回计算结果，回复用户yyy的计算结果为xxx'''

    @tool(description='计算给定的算式，符合标准的数学表达式，需要将用户输入转换为标准python字符串数学表达式格式')
    def any_express(s: str = Field(..., description="待计算的数学表达式")) -> float:
        """计算给定的算式，符合标准的数学表达式"""
        logger.info("The eval method is called: s=%s", s)
        return eval(s)


if __name__ == "__main__":
    logger.info("Start math server through MCP")  # 记录服务启动日志
    # mcp.run(transport="stdio")  # 启动服务并使用标准输入输出通信
