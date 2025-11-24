import json
import threading
from typing import Dict, Any, List
from brain import LLM_Ollama
from tools import list_all_tools, call_tool_by_name, expose_tools_as_service
from logger import logger
from utils.tts import PaddleTTS

# 初始化PaddleTTS实例
tts = PaddleTTS(server_ip='172.30.3.7', server_port=8092)
# tts.tts("您好，请问我有什么可以帮您的吗？")
class AgentFramework:
    """
    Agent框架主类，采用流式并行架构优化响应速度
    """
    def __init__(self):
        # 初始化两个LLM实例
        self.llm_a = LLM_Ollama(model="qwen3:8b")
        self.llm_b = LLM_Ollama(model="qwen3:14b")
        
        self.llm_a.messages = []
        self.llm_b.messages = []
        
        # 工具信息
        self.tools_info = list_all_tools()
        self.tools_service_info = expose_tools_as_service()
        
        # TTS 互斥锁，防止A和B的语音重叠
        self.tts_lock = threading.Lock()
        
        # 初始化提示词
        self._init_system_prompts()

    def _init_system_prompts(self):
        """
        初始化系统提示词，针对流式+并行逻辑优化
        """
        # 模型A Prompt：极致简化，只做分类和填充语生成
        # 0: 代表无需工具，直接回答
        # 1: 代表需要工具，生成一句自然的转场语（如：好的，我帮您查一下...）
        model_a_system_prompt = """
        你是一个快速反应的对话决策中心。你的任务是判断用户的请求是否需要调用外部工具。
        可用的工具列表：
        {tools_list}
        
        请严格遵守以下输出格式（不要输出JSON，只输出纯文本）：
        
        情况1：如果用户问题可以直接回答（如闲聊、常识），请以 "0:" 开头，后接回答内容。
        示例：0:你好呀！今天心情看起来不错，有什么我可以陪你聊的吗？
        
        情况2：如果用户问题需要查询工具才能回答（如查时间、查天气、搜索），请以 "1:" 开头，后接**一句话回复** **稍微长一点、自然且礼貌的过渡语，但是不能胡编乱造，不要超出对话涉及的文本知识范围**。这句话的作用是告诉用户你正在努力处理，请不要使用“好的”、“稍等”这种太短的词，要像真人客服一样。
        示例：1:好的，没问题，我正在为您连接实时数据库查询最新的天气情况，请您稍候片刻。
        示例：1:收到，我马上帮您检索相关的新闻资讯，正在搜索并整理数据中，请稍等。
        
        注意：必须以 "0:" 或 "1:" 开头。
        """.format(tools_list="\n".join([f"- {tool['name']}: {tool['description']}" for tool in self.tools_info]))        
        # 模型B Prompt：保持原有的工具规划能力，负责干活
        model_b_system_prompt = """
        你是一个智能工具调度专家。
        可用的工具详细信息如下：
        {tools_detail}
        
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
        **请不要使用 JSON！请不要使用 JSON！**
        直接输出你要对用户说的自然语言内容。不要带任何前缀，直接说话。
        
        """.format(tools_detail=json.dumps(self.tools_service_info, ensure_ascii=False, indent=2))
        
        self.llm_a.messages.append({"role": "system", "content": model_a_system_prompt})
        self.llm_b.messages.append({"role": "system", "content": model_b_system_prompt})
        logger.info(f"模型A系统提示词: {model_a_system_prompt}")
        logger.info(f"模型B系统提示词: {model_b_system_prompt}")

    def safe_tts(self, content: str):
        """
        线程安全的TTS调用，确保语音不冲突
        """
        if not content:
            return
        with self.tts_lock:
            logger.info(f"执行TTS播放: {content}")
            try:
                tts.tts(content)
            except Exception as e:
                logger.error(f"TTS播放失败: {e}")

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """辅助JSON解析"""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                return json.loads(response[start_idx:end_idx])
            return json.loads(response)
        except Exception:
            return {"error": "Invalid JSON", "raw": response}

    def _run_model_b_logic(self, user_query: str, model_b_name: str = "qwen3:14b"):
        """
        模型B的执行逻辑，将在子线程中运行
        """
        logger.info(">>> [子线程] 模型B开始运行工具调用流程...")
        
        # 模型B上下文管理
        # 注意：这里简单处理，实际生产中可能需要更复杂的上下文合并
        self.llm_b.messages.append({"role": "user", "content": user_query})
        
        max_turns = 5 # 防止死循环
        current_turn = 0
        flag=False
        while current_turn < max_turns:
            
            current_turn += 1
            # 获取模型B决策
            model_b_response = self.llm_b.return_text("", model_b_name)
            if model_b_response.startswith("{"):
                parsed_res = self.parse_json_response(model_b_response)
            else:
                parsed_res = model_b_response
                flag=True
            
            if "error" in parsed_res:
                logger.error(f"[模型B] 解析错误: {parsed_res}")
                self.safe_tts("抱歉，处理数据时出现了一些问题。")
                return

            # 情况1：任务完成
            if flag:
                final_content = parsed_res
                logger.info(f"-> [模型B] 最终输出: {final_content}")
                # B运行完后，直接送入TTS
                self.safe_tts(final_content)
                self.llm_b.messages.append({
                        "role": "assistant", 
                        "content": f"{final_content}"
                    })
                # self.llm_a.messages.append({
                #         "role": "assistant", 
                #         "content": f"{final_content}"
                #     })
                return

            # 情况2：调用工具
            if parsed_res.get("action") == "call_tool":
                tool_name = parsed_res.get("name")
                params = parsed_res.get("params", {})
                
                logger.info(f"-> [模型B] 调用工具: {tool_name} | 参数: {params}")
                
                try:
                    tool_result = call_tool_by_name(tool_name, **params)
                    result_str = str(tool_result)
                    logger.info(f"   工具结果: {result_str}")
                    
                    # 将结果回传给模型B
                    self.llm_b.messages.append({
                        "role": "assistant", 
                        "content": f"工具调用结果:\n工具: {tool_name}\n结果: {result_str}"
                    })
                except Exception as e:
                    err_msg = f"工具调用失败: {str(e)}"
                    logger.error(err_msg)
                    self.llm_b.messages.append({"role": "assistant", "content": err_msg})
            else:
                logger.warning("[模型B] 未知操作，退出循环")
                break

    def process_user_query(self, user_query: str, model_a_name: str = "qwen3:8b", model_b_name: str = "qwen3:14b"):
        """
        主处理函数：模型A流式输出 + 触发模型B线程
        """
        logger.info(f"收到用户请求: {user_query}")
        
        # 状态标记
        decision_type = None # 0 或 1
        buffer = ""          # 用于在流式中检测 "0:" 或 "1:"
        full_a_response = "" # 记录A的完整回复
        
        model_b_thread = None

        # 请求模型A流式输出
        stream_generator = self.llm_a.stream_text(user_query, model_a_name)
        logger.info("[步骤1] 模型A 流式响应中...")
        
        try:
            for chunk in stream_generator:
                full_a_response += chunk
                
                # 阶段1：检测决策类型 (0: 或 1:)
                if decision_type is None:
                    buffer += chunk
                    # 只要缓冲区足够长或包含冒号，就开始判断
                    if ":" in buffer or len(buffer) > 4:
                        if "0:" in buffer:
                            decision_type = 0
                            # 掐头，保留后面的内容
                            content_start = buffer.find("0:") + 2
                            buffer = buffer[content_start:] 
                            logger.info("=> 决策: 直接回答 (0)")
                        elif "1:" in buffer:
                            decision_type = 1
                            content_start = buffer.find("1:") + 2
                            buffer = buffer[content_start:]
                            logger.info("=> 决策: 需要工具 (1)")
                            
                            # 1. 立即启动模型 B 线程 (开始干活)
                            model_b_thread = threading.Thread(
                                target=self._run_model_b_logic, 
                                args=(user_query, model_b_name)
                            )
                            model_b_thread.daemon = True
                            model_b_thread.start()
                        else:
                            logger.warning("未检测到标准前缀，默认按直接回答处理")
                            decision_type = 0
                
                # 阶段2：根据决策处理剩余流
                else:
                    # 这里简单处理：将内容累积在buffer中，或者你可以更激进地每句做一次TTS
                    buffer += chunk

            # 流结束后的收尾工作
            final_a_content = buffer.strip()
            logger.info(f"模型A输出结束，内容: {final_a_content}")
            
            if decision_type == 0:
                # 直接回答：可以直接在主线程播，也可以扔进线程
                self.safe_tts(final_a_content)
                
            elif decision_type == 1:
                # === 优化开始 ===
                
                # 1. 播放过渡语 (放入独立线程，不再阻塞主控流程)
                # 由于 safe_tts 有锁 (self.tts_lock)，这里是线程安全的
                threading.Thread(
                    target=self.safe_tts, 
                    args=(final_a_content,)
                ).start()

                # 2. 主线程现在的状态：
                # - 模型A语音：正在后台播放
                # - 模型B逻辑：正在后台思考
                # - 主线程：空闲
                
                # 你可以选择在这里 join 等待 B 结束 (保持 CLI 交互整洁)
                if model_b_thread and model_b_thread.is_alive():
                    logger.info("主线程等待模型B处理完成...")
                    model_b_thread.join()
                

        except Exception as e:
            logger.error(f"处理流程异常: {e}")
            self.safe_tts("抱歉，系统出现了一个错误。")

if __name__ == "__main__":
    # 注册测试工具
    from tools import tool
    from datetime import datetime
    
    @tool(name="get_current_time", description="获取当前精确时间")
    def get_current_time() -> str:
        # 模拟一个耗时操作，体现流式并行的优势
        import time
        time.sleep(2) 
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    agent = AgentFramework()
    print("\n=== 高速流式Agent启动 (输入 'quit' 退出) ===\n")
    
    while True:
        q = input("User: ")
        if q.lower() in ["quit", "exit", "退出"]:
            break
        # 运行处理流程
        agent.process_user_query(q)
        print("\n" + "-"*30 + "\n")