import json
import threading
import configparser
from typing import Dict, Any, List, Optional
# queue 已经不需要在 framework 里显式使用了，除非用于其他目的
# import queue 

from brain import LLM_Ollama
from tools import list_all_tools_simple, call_tool_by_name, expose_tools_as_service, get_tool_output_description
from logger import logger
from utils.tts import CosyTTS
from utils import TextSplitter 

# --- 辅助类：单个工作Agent的抽象 ---
class WorkerAgent:
    """
    代表一个具备特定工具和能力的执行Agent (原模型B/C/D的逻辑封装)
    """
    def __init__(self, agent_id: int, name: str, description: str, model_name: str, tool_names: List[str]):
        self.id = agent_id
        self.name = name
        self.description = description
        self.model_name = model_name
        
        # 初始化LLM
        self.llm = LLM_Ollama(model=model_name)
        self.llm.messages = []
        
        # 工具处理
        self.tool_names = tool_names
        self.tools_info = list_all_tools_simple(tool_names)
        self.tools_service = expose_tools_as_service(tool_names)
        
        # 初始化系统Prompt
        self._init_system_prompt()

    def _init_system_prompt(self):
        base_prompt = '''
        你的任务是根据用户请求调用工具或直接回答。
        *** 非常重要：输出格式规则 ***
        模式 A - 需要调用工具时：
        请输出标准的 JSON 格式，格式如下：
        {{
            "action": "call_tool",
            "name": "工具名称",
            "params": {{ "参数名": "参数值" }}
        }}
        模式 B - 已获得工具结果或直接回答时：
        **请不要使用 JSON！** 直接输出你要对用户说的自然语言内容。
        '''
        system_prompt = f"""
        你是 {self.name} (ID: {self.id})
        描述: {self.description}
        可用工具服务: {self.tools_service}
        {base_prompt}
        """
        self.llm.messages.append({"role": "system", "content": system_prompt})

    def run_task(self, user_query: str, callback_func=None):
        """
        执行具体的任务循环 (工具调用 -> 思考 -> 回答)
        """
        logger.info(f"[{self.name}] 开始处理任务...")
        self.llm.messages.append({"role": "user", "content": '/no_think\n'+user_query})
        
        max_turns = 5
        current_turn = 0
        
        while current_turn < max_turns:
            current_turn += 1
            response = self.llm.return_text("", self.model_name)
            
            # 尝试解析JSON
            parsed_res = self._parse_json(response)
            
            # 情况1：直接回答（非JSON或解析失败视为直接回答）
            if "action" not in parsed_res:
                final_content = response if isinstance(parsed_res, dict) else parsed_res
                logger.info(f"[{self.name}] 最终输出: {final_content}")
                
                self.llm.messages.append({"role": "assistant", "content": final_content})
                
                if callback_func:
                    callback_func(final_content)
                return final_content

            # 情况2：调用工具
            tool_name = parsed_res.get("name")
            params = parsed_res.get("params", {})
            logger.info(f"[{self.name}] 调用工具: {tool_name}")
            
            try:
                tool_result = call_tool_by_name(tool_name, **params)
                tool_utput_desc = get_tool_output_description(tool_name)
                result_str = str(tool_result)
                self.llm.messages.append({
                    "role": "assistant", 
                    "content": f"工具调用结果:\n工具: {tool_name}\n结果: {result_str}\n{tool_utput_desc}/no_think"
                })
            except Exception as e:
                logger.error(f"工具调用失败: {e}")
                self.llm.messages.append({"role": "assistant", "content": f"工具调用失败: {str(e)}"})

    def _parse_json(self, content: str) -> Dict:
        try:
            # 简单的提取逻辑，适配可能存在的Markdown包裹
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(content[start:end])
            return json.loads(content) 
        except:
            return {"raw": content} 

# --- 主框架类 ---
class AgentFramework:
    def __init__(self, config_path: str = None):
        self.workers: Dict[int, WorkerAgent] = {} 
        self.dispatcher_llm: Optional[LLM_Ollama] = None
        self.dispatcher_model_name = "qwen3:8b"
        
        # --- TTS 改造部分 ---
        self.tts_client = None
        # 注意：这里不再需要 self.tts_queue，因为逻辑已移交 test_tts 内部处理
        
        self.system_prompt = None
        # 加载配置
        if config_path:
            self.load_config(config_path)
        logger.info(f"system_prompt: {self.dispatcher_llm.messages[0]['content']}")
        

    def load_config(self, config_path: str):
        """从配置文件加载设置和Agents"""
        logger.info(f"正在加载配置文件: {config_path}")
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding='utf-8')
        
        # 1. 初始化TTS
        if cfg.has_section("General"):
            ip = cfg.get("General", "tts_ip", fallback="127.0.0.1")
            port = cfg.getint("General", "tts_port", fallback=8092)
            # 初始化即启动后台线程
            self.tts_client = CosyTTS(server_ip=ip, server_port=port)
            
        # 2. 初始化 Dispatcher
        if cfg.has_section("Dispatcher"):
            self.dispatcher_model_name = cfg.get("Dispatcher", "model_name", fallback="qwen3:8b")
            self.system_prompt = cfg.get("Dispatcher", "description", 
                fallback="你是一个快速反应的对话决策中心...")
            
        # 3. 初始化 Workers
        for section in cfg.sections():
            if section.startswith("Worker."):
                agent_name = section.split(".")[1]
                agent_id = cfg.getint(section, "agent_id")
                desc = cfg.get(section, "description")
                model = cfg.get(section, "model_name")
                tools_str = cfg.get(section, "tools", fallback="")
                tools = [t.strip() for t in tools_str.split(",") if t.strip()]
                self.create_agent(agent_id, agent_name, desc, model, tools)

        # 4. 配置完成后，初始化Dispatcher Prompt
        self._init_dispatcher()

    def create_agent(self, agent_id: int, name: str, description: str, model_name: str, tools: List[str]):
        """
        【API接口】手动创建并注册一个Agent
        """
        worker = WorkerAgent(agent_id, name, description, model_name, tools)
        self.workers[agent_id] = worker
        logger.info(f"Agent已注册: [{agent_id}] {name}")
        logger.info(f"{name}.prompt: {worker.llm.messages[0]['content']}")
        self._init_dispatcher()

    def _init_dispatcher(self):
        """初始化或刷新分发者（Router）"""
        self.dispatcher_llm = LLM_Ollama(model=self.dispatcher_model_name)
        self.dispatcher_llm.messages = []
        
        agents_desc_text = ""
        for aid, worker in self.workers.items():
            agents_desc_text += f"""
            - Agent ID: {aid} ({worker.name})
              描述: {worker.description}
              内置工具: {', '.join([tool['name'] for tool in worker.tools_info])}
            """
            
        system_prompt = f"""
        {self.system_prompt}
        
        可用的agent列表：
        {agents_desc_text}
        
        **请严格遵守以下输出格式（纯文本）：**
        输出格式严格为：use_tool:agent_id:回复文本
        示例- 0:0:你好呀！很高兴为你服务。
        示例- 1:0:好的，我这就为您播放xxx的... 
        示例- 1:1:正在调用xxx查看... 
        示例- 1:2:正在...

        查询新闻、信息、歌曲之类的时候一定是要使用工具的
        回复文本根据实际用户问题和agent的功能，保持自然的过渡，更像人与人之间的交流，但不应该胡编乱造。

        注意：
        use_tool 必须为 0 或 1。0表示闲聊，1表示需要工具。
        agent_id 必须在 [{','.join(map(str, self.workers.keys()))}] 中选择。
        """
        self.dispatcher_llm.messages.append({"role": "system", "content": system_prompt})

    def safe_tts(self, content: str):
        """
        线程安全的 TTS 请求发送
        """
        if not self.tts_client or not content: 
            return
            
        # 完全重构：直接将文本交给 TTS 客户端，内部处理分段、队列和播放
        # 这个操作是瞬间完成的，不会阻塞
        self.tts_client.add_text(content)

    def process_user_query(self, user_query: str, target_workers: List[int] = None):
        """
        【API接口】处理用户请求
        """
        logger.info(f"收到请求: {user_query}")
        
        stream = self.dispatcher_llm.stream_text(user_query, self.dispatcher_model_name)
        buffer = ""
        decision_made = False
        worker_thread = None 
        
        for chunk in stream:
            buffer += chunk
            if not decision_made and len(buffer) > 5:
                # ... (保留原有的解析逻辑) ...
                try:
                    parts = buffer.split(":")
                    if len(parts) >= 3:
                        use_tool_str = parts[0].strip()
                        agent_id_str = parts[1].strip()
                        # 简单的鲁棒性处理
                        if not (use_tool_str.isdigit() and agent_id_str.isdigit()):
                             if len(parts) > 3: # 尝试移位解析
                                use_tool_str = parts[1].strip()
                                agent_id_str = parts[2].strip()

                        if use_tool_str.isdigit() and agent_id_str.isdigit():
                            use_tool = int(use_tool_str)
                            agent_id = int(agent_id_str)
                            
                            prefix_signature = f"{use_tool_str}:{agent_id_str}:"
                            content_start_idx = buffer.find(prefix_signature)
                            
                            if content_start_idx != -1:
                                content_start_idx += len(prefix_signature)
                                transition_text = buffer[content_start_idx:] 
                                decision_made = True
                                
                                logger.info(f"决策: Tool={use_tool}, Agent={agent_id}")
                                worker_thread = self._dispatch_worker(agent_id, user_query, use_tool)
                                buffer = transition_text
                except ValueError:
                    pass 
        
        final_text = buffer.strip()
        
        # 1. 播放过渡语
        if final_text:
            logger.info(f"主控回复: {final_text}")
            self.safe_tts(final_text)

        # 2. 等待 Agent 工作完成
        if worker_thread and worker_thread.is_alive():
            logger.info("主线程等待 Worker 处理完成...")
            worker_thread.join()
            logger.info("Worker 任务结束。")
        
        # 3. 可选：等待语音播放完毕 (如果业务需要在这里阻塞等待说完再接收下一个用户请求)
        # 如果希望完全异步，可以注释掉下面这行
        if self.tts_client:
             self.tts_client.wait_until_done()
             logger.info("本轮语音播放完毕。")

    def _dispatch_worker(self, agent_id: int, query: str, use_tool: int):
        """内部方法：根据ID调度Worker，并返回线程对象"""
        if use_tool == 0:
            return None 

        worker = self.workers.get(agent_id)
        if not worker:
            logger.error(f"未找到ID为 {agent_id} 的Agent")
            return None

        def run():
            # Worker运行完后，通过回调调用TTS
            worker.run_task(query, callback_func=self.safe_tts)

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()
        return t