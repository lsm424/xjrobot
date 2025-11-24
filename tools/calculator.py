from tools import tool
from typing import Union

@tool(name="add", description="加法运算工具，计算两个数的和")
def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    计算两个数的和
    
    Args:
        a: 第一个数
        b: 第二个数
    
    Returns:
        两个数的和
    """
    return a + b

@tool(name="subtract", description="减法运算工具，计算两个数的差")
def subtract(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    计算两个数的差
    
    Args:
        a: 被减数
        b: 减数
    
    Returns:
        两个数的差
    """
    return a - b

@tool(name="multiply", description="乘法运算工具，计算两个数的积")
def multiply(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    计算两个数的积
    
    Args:
        a: 第一个乘数
        b: 第二个乘数
    
    Returns:
        两个数的积
    """
    return a * b

@tool(name="divide", description="除法运算工具，计算两个数的商")
def divide(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    计算两个数的商
    
    Args:
        a: 被除数
        b: 除数
    
    Returns:
        两个数的商
    
    Raises:
        ValueError: 当除数为零时抛出异常
    """
    if b == 0:
        raise ValueError("除数不能为零")
    return a / b

@tool(name='complex_calculate', description='输入给定字符串数学计算式，计算数学结果')
def complex_calculate(expression: str) -> Union[int, float]:
    """
    计算给定字符串数学计算式的结果
    
    Args:
        expression: 数学计算式，例如 "2 + 3 * 4"
    
    Returns:
        计算结果
    
    Raises:
        ValueError: 当表达式格式错误或包含无效操作时抛出异常
    """
    try:
        return eval(expression)
    except Exception as e:
        raise ValueError(f"表达式格式错误或包含无效操作: {e}")
