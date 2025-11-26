# import inspect
# import json
# import os
# import sys
# from typing import Callable, Dict, List, Any, Optional

# class ToolRegistry:
#     """
#     工具注册中心，统一管理所有被@tool修饰的函数
#     """
#     def __init__(self):
#         self._tools: Dict[str, Dict[str, Any]] = {}
#         self._tool_modules: Dict[str, str] = {}  # 记录工具所属模块

#     def register(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
#         """
#         注册一个工具函数
#         """
#         tool_name = name or func.__name__
#         sig = inspect.signature(func)
#         params = []
        
#         for param_name, param in sig.parameters.items():
#             param_info = {
#                 "name": param_name,
#                 "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
#                 "default": param.default if param.default != inspect.Parameter.empty else None
#             }
#             params.append(param_info)

#         return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else "Any"
        
#         # 获取函数所属的模块
#         module_name = func.__module__

#         tool_info = {
#             "name": tool_name,
#             "description": description or func.__doc__ or "No description provided",
#             "parameters": params,
#             "return_type": return_type,
#             "function": func,
#             "module": module_name
#         }
        
#         self._tools[tool_name] = tool_info
#         self._tool_modules[tool_name] = module_name
        
#         return func

#     def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
#         """
#         根据名称获取工具信息
#         """
#         return self._tools.get(name)

#     def list_tools(self) -> List[Dict[str, Any]]:
#         """
#         列出所有已注册的工具
#         """
#         return list(self._tools.values())

#     def call_tool(self, name: str, *args, **kwargs) -> Any:
#         """
#         调用指定名称的工具函数
#         """
#         tool = self.get_tool(name)
#         if not tool:
#             raise ValueError(f"Tool '{name}' not found")
#         return tool["function"](*args, **kwargs)

#     def expose_as_service(self) -> Dict[str, Any]:
#         """
#         将工具暴露为服务格式，供外部调用
#         """
#         service_info = {
#             "tools": [
#                 {
#                     "name": tool["name"],
#                     "description": tool["description"],
#                     "parameters": tool["parameters"],
#                     "return_type": tool["return_type"],
#                     "module": tool.get("module", "unknown")
#                 }
#                 for tool in self._tools.values()
#             ]
#         }
#         return service_info
    
#     def load_tools_from_directory(self, directory: str):
#         """
#         从指定目录加载所有工具模块
#         """
#         # 确保目录在Python路径中
#         if directory not in sys.path:
#             sys.path.insert(0, directory)
        
#         # 遍历目录中的所有.py文件
#         for filename in os.listdir(directory):
#             if filename.endswith('.py') and filename != '__init__.py':
#                 module_name = filename[:-3]  # 去掉.py扩展名
#                 try:
#                     # 导入模块
#                     module = __import__(module_name)
#                     print(f"已加载工具模块: {module_name}")
#                 except Exception as e:
#                     print(f"加载工具模块 {module_name} 失败: {e}")


# # 全局工具注册实例
# _tool_registry = ToolRegistry()


# def tool(name: Optional[str] = None, description: Optional[str] = None):
#     """
#     工具装饰器，用于将函数注册为可管理、可调用的工具
#     用法：
#         @tool(name="my_tool", description="这是一个示例工具")
#         def my_function(x: int, y: int) -> int:
#             return x + y
#     """
#     def decorator(func: Callable) -> Callable:
#         _tool_registry.register(func, name=name, description=description)
#         return func
#     return decorator


# # 工具注册与暴露服务的快捷函数
# def register_tool(func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> Callable:
#     """
#     手动注册工具函数
#     """
#     return _tool_registry.register(func, name=name, description=description)

# def get_tool_info(name: str) -> Optional[Dict[str, Any]]:
#     """
#     获取指定工具的信息
#     """
#     return _tool_registry.get_tool(name)

# def list_all_tools() -> List[Dict[str, Any]]:
#     """
#     列出所有已注册的工具
#     """
#     return _tool_registry.list_tools()

# def call_tool_by_name(name: str, *args, **kwargs) -> Any:
#     """
#     根据名称调用工具函数
#     """
#     return _tool_registry.call_tool(name, *args, **kwargs)

# def expose_tools_as_service() -> Dict[str, Any]:
#     """
#     将当前所有工具暴露为服务格式
#     """
#     return _tool_registry.expose_as_service()

# # 导出主要的类和函数供外部使用
# __all__ = [
#     'ToolRegistry',
#     'tool',
#     'register_tool',
#     'get_tool_info',
#     'list_all_tools',
#     'call_tool_by_name',
#     'expose_tools_as_service'
# ]

# # 自动加载tools目录下的所有工具模块 - 移到文件末尾避免循环导入
# if __name__ != '__main__':
#     current_dir = os.path.dirname(__file__)
#     _tool_registry.load_tools_from_directory(current_dir)
import inspect
import json
import os
import sys
from typing import Callable, Dict, List, Any, Optional

class ToolRegistry:
    """
    工具注册中心，统一管理所有被@tool修饰的函数
    """
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._tools_simple: Dict[str, Dict[str, Any]] = {}
        self._tool_modules: Dict[str, str] = {}  # 记录工具所属模块

    def register(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        """
        注册一个工具函数
        """
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
        
        # 获取函数所属的模块名称
        module_name = func.__module__

        tool_info = {
            "name": tool_name,
            "description": description or func.__doc__ or "No description provided",
            "parameters": params,
            "return_type": return_type,
            "function": func,
            "module": module_name
        }
        tool_simple_info = {
            "name": tool_name,
            "description": description.split("\n")[0] or func.__doc__ or "No description provided",
        }
        
        self._tools[tool_name] = tool_info
        self._tools_simple[tool_name] = tool_simple_info
        self._tool_modules[tool_name] = module_name
        
        return func

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取工具信息
        """
        return self._tools.get(name)

    def _is_tool_in_modules(self, tool_module: str, target_modules: List[str]) -> bool:
        """
        辅助函数：判断工具的模块是否在目标列表中
        """
        # 1. 预处理目标模块名：去除 .py 后缀
        clean_targets = {m[:-3] if m.endswith('.py') else m for m in target_modules}
        
        # 2. 获取工具模块的最后一部分 (处理 package.module 的情况)
        # 例如: 'tools.calculator' -> 'calculator'
        tool_module_simple = tool_module.split('.')[-1]
        
        # 3. 匹配：既匹配全名，也匹配简名
        # 这样允许用户输入 'tools.calculator' 或者仅仅是 'calculator'
        return (tool_module in clean_targets) or (tool_module_simple in clean_targets)

    def list_tools(self, module_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        列出已注册的工具。
        :param module_names: 可选，指定文件名/模块名列表进行筛选（如 ['calculator.py', 'weather']）
        """
        all_tools = list(self._tools.values())
        
        if not module_names:
            return all_tools
            
        filtered_tools = []
        for tool in all_tools:
            # 获取该工具所属的模块
            t_module = tool.get("module", "")
            if self._is_tool_in_modules(t_module, module_names):
                filtered_tools.append(tool)
                
        return filtered_tools
    
    def list_tools_simple(self, module_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        列出已注册的简单工具。
        :param module_names: 可选，指定文件名/模块名列表进行筛选（如 ['calculator.py', 'weather']）
        """
        all_tools = list(self._tools_simple.values())
        
        if not module_names:
            return all_tools
            
        filtered_tools = []
        for tool in all_tools:
            # 获取该工具所属的模块
            t_module = self._tool_modules.get(tool["name"], "")
            if self._is_tool_in_modules(t_module, module_names):
                filtered_tools.append(tool)
                
        return filtered_tools

    def call_tool(self, name: str, *args, **kwargs) -> Any:
        """
        调用指定名称的工具函数
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        return tool["function"](*args, **kwargs)

    def expose_as_service(self, module_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        将工具暴露为服务格式，供外部调用。
        :param module_names: 可选，指定文件名/模块名列表进行筛选
        """
        # 复用 list_tools 的筛选逻辑
        target_tools = self.list_tools(module_names=module_names)
        
        service_info = {
            "tools": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                    "return_type": tool["return_type"],
                    "module": tool.get("module", "unknown")
                }
                for tool in target_tools
            ]
        }
        return service_info
    
    def load_tools_from_directory(self, directory: str):
        """
        从指定目录加载所有工具模块
        """
        if directory not in sys.path:
            sys.path.insert(0, directory)
        
        for filename in os.listdir(directory):
            if filename.endswith('.py') and filename != '__init__.py':
                module_name = filename[:-3]
                try:
                    module = __import__(module_name)
                    print(f"已加载工具模块: {module_name}") # Optional: 保持静默或打印
                except Exception as e:
                    print(f"加载工具模块 {module_name} 失败: {e}")


# 全局工具注册实例
_tool_registry = ToolRegistry()


def tool(name: Optional[str] = None, description: Optional[str] = None):
    """
    工具装饰器
    """
    def decorator(func: Callable) -> Callable:
        _tool_registry.register(func, name=name, description=description)
        return func
    return decorator


def register_tool(func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> Callable:
    return _tool_registry.register(func, name=name, description=description)

def get_tool_info(name: str) -> Optional[Dict[str, Any]]:
    return _tool_registry.get_tool(name)

# 修改：增加 module_names 参数
def list_all_tools(module_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    列出已注册的工具
    :param module_names: 列表，包含想要筛选的模块名或文件名 (e.g. ['math_tools.py', 'search'])
    """
    return _tool_registry.list_tools(module_names=module_names)

def list_all_tools_simple(module_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    列出已注册的简单工具
    :param module_names: 列表，包含想要筛选的模块名或文件名 (e.g. ['math_tools.py', 'search'])
    """
    return _tool_registry.list_tools_simple(module_names=module_names)

def call_tool_by_name(name: str, *args, **kwargs) -> Any:
    return _tool_registry.call_tool(name, *args, **kwargs)

def get_tool_output_description(name: str) -> Optional[str]:
    """
    获取指定工具的输出描述
    :param name: 工具名称
    :return: 工具的输出描述或 None
    """
    tool_info = _tool_registry.get_tool(name)
    if tool_info and 'description' in tool_info:
        return tool_info['description'].split("\n")[-1]
    return "请你根据工具结果进行拟人化、精简回复"

# 修改：增加 module_names 参数
def expose_tools_as_service(module_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    将工具暴露为服务格式
    :param module_names: 列表，包含想要暴露的模块名或文件名
    """
    return _tool_registry.expose_as_service(module_names=module_names)

__all__ = [
    'ToolRegistry',
    'tool',
    'register_tool',
    'get_tool_info',
    'list_all_tools',
    'call_tool_by_name',
    'expose_tools_as_service',
    'list_all_tools_simple',
    'get_tool_output_description'
]

if __name__ != '__main__':
    current_dir = os.path.dirname(__file__)
    _tool_registry.load_tools_from_directory(current_dir)