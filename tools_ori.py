import inspect
import json
from typing import Callable, Dict, List, Any, Optional

class ToolRegistry:
    """工具注册中心，统一管理所有被@tool修饰的函数"""
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        """注册一个工具函数"""
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        params = []
        for param_name, param in sig.parameters.items():
            param_info = {
                "name": param_name,
                "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                "default": param.default if param.default != inspect.Parameter.empty else None
            }
            params.append(param_info)

        return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else "Any"

        tool_info = {
            "name": tool_name,
            "description": description or func.__doc__ or "No description provided",
            "parameters": params,
            "return_type": return_type,
            "function": func
        }
        self._tools[tool_name] = tool_info
        return func

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取工具信息"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有已注册的工具"""
        return list(self._tools.values())

    def call_tool(self, name: str, *args, **kwargs) -> Any:
        """调用指定名称的工具函数"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        return tool["function"](*args, **kwargs)

    def expose_as_service(self) -> Dict[str, Any]:
        """将工具暴露为服务格式，供外部调用"""
        service_info = {
            "tools": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                    "return_type": tool["return_type"]
                }
                for tool in self._tools.values()
            ]
        }
        return service_info


# 全局工具注册实例
_tool_registry = ToolRegistry()


def tool(name: Optional[str] = None, description: Optional[str] = None):
    """
    工具装饰器，用于将函数注册为可管理、可调用的工具
    用法：
        @tool(name="my_tool", description="这是一个示例工具")
        def my_function(x: int, y: int) -> int:
            return x + y
    """
    def decorator(func: Callable) -> Callable:
        _tool_registry.register(func, name=name, description=description)
        return func
    return decorator


# 工具注册与暴露服务的快捷函数
def register_tool(func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> Callable:
    """手动注册工具函数"""
    return _tool_registry.register(func, name=name, description=description)


def get_tool_info(name: str) -> Optional[Dict[str, Any]]:
    """获取指定工具的信息"""
    return _tool_registry.get_tool(name)


def list_all_tools() -> List[Dict[str, Any]]:
    """列出所有已注册的工具"""
    return _tool_registry.list_tools()


def call_tool_by_name(name: str, *args, **kwargs) -> Any:
    """根据名称调用工具函数"""
    return _tool_registry.call_tool(name, *args, **kwargs)


def expose_tools_as_service() -> Dict[str, Any]:
    """将当前所有工具暴露为服务格式"""
    return _tool_registry.expose_as_service()
if __name__ == "__main__":
    # 测试装饰器注册
    @tool(name="add", description="两数相加")
    def add(a: int, b: int) -> int:
        return a + b

    @tool(description="拼接字符串")
    def concat(x: str, y: str = "default") -> str:
        return x + y

    # 测试手动注册
    def multiply(x: float, y: float) -> float:
        return x * y
    register_tool(multiply, name="multiply", description="两数相乘")

    # 测试列出所有工具
    tools = list_all_tools()
    print("已注册的工具：")
    for t in tools:
        print(f"  - {t['name']}: {t['description']}")

    # 测试调用工具
    print("\n调用测试：")
    print("add(3, 5) =", call_tool_by_name("add", 3, 5))
    print("concat('hello') =", call_tool_by_name("concat", "hello"))
    print("multiply(2.5, 4) =", call_tool_by_name("multiply", 2.5, 4))

    # 测试服务暴露
    service = expose_tools_as_service()
    print("\n服务格式：")
    print(json.dumps(service, ensure_ascii=False, indent=2))
