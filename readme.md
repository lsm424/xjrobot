# Multi-Agent 框架使用说明

一个多智能体协作框架，支持工具调用、语音播报和异步任务处理。

## 核心特性

- **双角色架构**：_dispatcher_ 负责意图识别与路由，_worker_ 执行具体任务
- **工具调用**：支持 LLM 自动选择并调用外部工具
- **流式响应**：实时输出决策过程，支持语音合成（TTS）
- **配置驱动**：通过 INI 文件灵活配置 Agent 和模型参数
- **线程安全**：TTS 队列化，避免并发冲突

---

## 快速开始

### 1. 安装依赖
python=3.12.0
```bash
pip install -r requirements.txt
```

### 2. 准备配置文件 `config.ini`

```ini
[General]
tts_ip = 127.0.0.1
tts_port = 8092

[Dispatcher]
model_name = qwen3:8b
description = 你是一个快速反应的对话决策中心...

[Worker.search_agent]
agent_id = 1
description = 负责网络搜索和实时信息查询
model_name = qwen3:8b
tools = search_tool, fetch_url

[Worker.code_agent]
agent_id = 2
description = 负责代码执行和计算
model_name = qwen3:8b
tools = execute_python, file_manager
```

### 3. 初始化并运行

```python
# 初始化框架
framework = AgentFramework(config_path="config.ini")

# 处理用户查询（自动完成意图识别 → 调度 → 执行 → 语音播报）
framework.process_user_query("今天北京天气怎么样？")
```

---

## API 说明

### 创建 Agent（动态）

```python
# 无需重启，运行时动态注册
framework.create_agent(
    agent_id=3,
    name="analysis_agent",
    description="负责数据分析",
    model_name="qwen3:8b",
    tools=["data_visualizer"]
)
```

### 直接查询

```python
# 自动选择 Agent 并执行
framework.process_user_query("查询最新的AI新闻")
```

---

## 配置字段说明

| 模块 | 字段 | 说明 |
|------|------|------|
| **Dispatcher** | `model_name` | 路由决策模型 |
|                | `description` | 系统提示词 |
| **Worker** | `agent_id` | 唯一标识（用于调度） |
|            | `model_name` | 执行模型 |
|            | `tools` | 工具列表，逗号分隔 |
| **General** | `tts_*` | 语音服务地址（可选） |

---

## 输出格式

**Dispatcher 决策格式**：`use_tool:agent_id:回复文本`  
- `use_tool`: `0` 直接回答，`1` 调用工具
- `agent_id`: 目标 Worker ID

---

## 注意事项

1. **工具函数**需在 `tools` 模块中预先定义，参考 `tools/tools_readme.md`
2. TTS 服务为可选功能，未配置时静默跳过语音播报
3. Worker 执行超时未设置，需注意长任务阻塞
4. 所有 Agent 共享相同的 LLM 客户端接口

---
