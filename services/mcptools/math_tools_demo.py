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
        return '''1.用户输入：涉及加法运算时，使用add_numbers工具
2.用户输入：涉及减法运算时，使用subtract_numbers工具  
3.用户输入：涉及乘法运算时，使用multiply_numbers工具
4.用户输入：涉及复杂数学表达式时，使用evaluate_expression工具'''
    
    @tool(description='如果运算符为#，使用该函数对两个数操作 two numbers,减法操作，返回第一个数减去第二个数的结果')
    def sub(a: int = Field(..., description="被减数"), b: int = Field(..., description="减数")) -> int:
        logger.info("The sub method is called: a=%d, b=%d", a, b)
        return a - b

    @tool(description='如果运算符为@，使用该函数对两个数操作 two numbers,乘法操作，返回第一个数乘以第二个数的结果')
    def mul(a: int = Field(..., description="被乘数"), b: int = Field(..., description="乘数")) -> int:
        logger.info("The mul method is called: a=%d, b=%d", a, b)
        return a * b

    @tool(description='如果运算符为&，使用该函数对两个数操作 two numbers,加法操作，返回第一个数加上第二个数的结果')
    def add(a: int = Field(..., description="被加数"), b: int = Field(..., description="加数")) -> int:
        logger.info("The add method is called: a=%d, b=%d", a, b)
        return a + b

    @tool(description='计算给定的算式，符合标准的数学表达式')
    def any_express(s: str = Field(..., description="待计算的数学表达式")) -> float:
        """计算给定的算式，符合标准的数学表达式"""
        logger.info("The eval method is called: s=%s", s)
        return eval(s)


if __name__ == "__main__":
    logger.info("Start math server through MCP")  # 记录服务启动日志
    # mcp.run(transport="stdio")  # 启动服务并使用标准输入输出通信
