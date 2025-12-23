
# `@tool` 工具编写规范指南

## 一、框架概述

本框架使用 `@tool` 装饰器将普通 Python 函数注册为智能体可调用的工具。工具注册中心自动管理函数元数据、参数解析和调用生命周期。

---

## 二、基本编写规则

### 1. 最小可用示例

```python
from tools import tool
from logger import logger

@tool(name="demo_tool", description="清晰描述工具功能、输入和输出要求", audioSyncMode=0)
def demo_tool(param1: str, param2: int = 10) -> str:
    """简要说明实现逻辑"""
    logger.info(f"工具执行: {param1}")
    try:
        result = f"处理结果: {param1 * param2}"
        return result
    except Exception as e:
        logger.error(f"工具执行失败: {e}")
        return f"错误: 工具执行失败 - {str(e)}"
```

---

## 三、装饰器参数规范

### `@tool(name, description)`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | 否 | 工具唯一标识，默认为函数名。建议使用英文蛇形命名 |
| `description` | `str` | **是** | **核心配置项**，需包含三部分内容（见下文） |
| `audioSyncMode` | `int` | **否** | **核心配置项**，0为默认，1表示声音与tts同步播放，2表示等待tts播放完毕再开始，此轮对话后续文本并不再转tts |

### `description` 编写模板

```python
description="""【工具功能】一句话说明用途
输入：参数说明，包括是否必填、格式示例（如：歌曲名称，例如 晴天）
回复要求：回复需要自然拟人，成功时回复...；失败时按报错解释性回复"""
```

**必须包含：**
- **功能描述**：清晰说明工具做什么
- **输入说明**：每个参数的含义、格式、示例
- **回复要求**：成功/失败时的回复风格要求

---

## 四、函数签名规范

### 参数定义

```python
# ✅ 推荐：明确的类型注解 + 默认值
@tool(...)
def search_content(
    query: str,              # 必填参数
    limit: int = 10,         # 可选参数，必须给默认值
    source: str = "baidu"    # 枚举类建议用 Literal 类型
) -> str:
    ...

# ❌ 避免：无类型注解或 *args, **kwargs
def bad_tool(*args, **kwargs) -> str:  # 框架无法正确解析参数信息
    ...
```

### 返回值

- **必须**返回 `str` 类型
- 成功时返回自然语言描述的结果
- 失败时返回 `f"错误: {错误信息}"` 格式字符串
- 避免返回 `None`，应转为 `"无结果"`

---

## 五、错误处理最佳实践

### 标准错误处理模板

```python
@tool(name="fetch_data", description="...")
def fetch_data(url: str) -> str:
    logger.info(f"开始获取数据: {url}")
    
    try:
        # 1. 参数验证
        if not url.startswith("http"):
            return "错误: URL格式不正确，需以http开头"
        
        # 2. 核心逻辑
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 3. 结果验证
        data = response.json()
        if not data:
            logger.warning("API返回空数据")
            return "未查询到相关数据"
        
        return f"成功获取 {len(data)} 条记录"
    
    except requests.Timeout:
        logger.error("请求超时")
        return "错误: 网络请求超时，请检查网络连接"
    
    except requests.HTTPError as e:
        logger.error(f"HTTP错误: {e}")
        return f"错误: 服务异常 (状态码: {e.response.status_code})"
    
    except Exception as e:
        logger.critical(f"未预期错误: {e}", exc_info=True)
        return f"服务器内部错误: {str(e)}"
```

---

## 六、日志记录规范

### 必须记录的日志点

```python
logger.info(f"工具[{tool_name}]收到参数: {param}")  # 记录输入
logger.info(f"调用外部API: {api_url}")               # 记录关键调用
logger.warning("异常情况说明")                       # 可预期的异常
logger.error(f"执行失败: {e}")                      # 错误
logger.critical("致命错误", exc_info=True)          # 需要堆栈信息的错误
```

**原则：**
- `info`：记录正常流程和关键参数（注意脱敏）
- `warning`：非阻塞性异常，有降级方案
- `error`：工具执行失败，需返回错误信息
- `critical`：未捕获的异常，记录完整堆栈

---

## 七、命名与组织规范

### 工具命名

```python
# ✅ 推荐：动词 + 名词，蛇形命名
search_song_then_play
lyrics_to_song_name
get_weather_by_city
stop_music

# ❌ 避免：模糊或不一致的命名
tool1
music_func
SearchSong  # 不符合Python风格
```

### 文件组织

```
project/
├── tools/
│   ├── __init__.py           # 可为空，但必须存在
│   ├── music_tools.py        # 音乐相关工具
│   ├── search_tools.py       # 搜索相关工具
│   └── code_tools.py         # 代码执行工具
├── main.py
└── config.ini
```

**自动加载机制**：`tools` 目录下的所有 `.py` 文件（除 `__init__.py`）会被自动导入，装饰器会完成注册。

---

## 八、完整示例：音乐工具

```python
# tools/music_tools.py
import requests
from tools import tool
from logger import logger
from utils.audio import audio_player

@tool(name="play_music", 
      description="""根据歌曲名称播放音乐
输入：歌曲名称（必填），歌手名称（可选，用于精准匹配）
回复要求：回复需要自然拟人，成功时回复"正在播放《XXX》..."；失败时解释原因""")
def play_music(song_name: str, singer: str = None) -> str:
    """搜索并播放指定歌曲"""
    logger.info(f"播放请求: {song_name} - {singer}")
    
    try:
        # 参数校验
        if not song_name or not song_name.strip():
            return "错误: 歌曲名称不能为空"
        
        # 搜索逻辑...
        result = _search_and_play(song_name, singer)
        logger.info(f"播放成功: {result}")
        return f"正在播放《{song_name}》，请您欣赏"
        
    except Exception as e:
        logger.error(f"播放失败: {e}", exc_info=True)
        return f"抱歉，播放失败: {str(e)}"

def _search_and_play(song: str, singer: str) -> bool:
    """辅助函数：真正的搜索播放逻辑"""
    # 实现细节...
    pass
```

---

## 九、高级功能

### 1. 模块筛选

```python
# 只列出 music_tools.py 中的工具
from tools import list_all_tools_simple

music_tools = list_all_tools_simple(module_names=["music_tools.py"])
# 或
music_tools = list_all_tools_simple(module_names=["music_tools"])  # 无需.py
```

### 2. 获取工具输出描述

```python
from tools import get_tool_output_description

desc = get_tool_output_description("play_music")
print(desc)  # 输出: "请你根据工具结果进行拟人化、精简回复"
```

---

## 十、常见错误排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 工具未出现在列表中 | 1. 装饰器未执行<br>2. 文件未加载 | 确保使用 `@tool` 装饰器；检查文件是否在 `tools/` 目录下 |
| 参数类型显示为 `Any` | 缺少类型注解 | 添加参数类型注解，如 `param: str` |
| 调用工具时参数不匹配 | 框架无法解析复杂类型 | 保持参数简单，避免 `*args`, `**kwargs`, 复杂对象 |
| 日志重复输出 | 多次加载模块 | 确保 `if __name__ != '__main__'` 条件正确 |

---

## 十一、注意事项

1. **幂等性**：工具应尽可能设计为幂等，重复调用结果一致
2. **副作用**：有副作用的操作（播放音乐、发送邮件）必须在 `description` 中明确说明
3. **性能**：耗时操作应考虑异步实现（本框架暂不支持原生异步，需自行处理）
4. **安全**：执行代码、文件操作等高风险工具必须做严格的权限和参数校验
5. **状态管理**：框架无内置状态管理，需自行实现（如使用全局变量或数据库）

---

## 十二、测试工具

```python
# test_tools.py
from tools import call_tool_by_name

# 测试单个工具
result = call_tool_by_name("lyrics_to_song_name", "窗外的麻雀")
print(result)
```

---

**记住：好的工具 = 清晰的描述 + 健壮的错误处理 + 完整的日志记录**