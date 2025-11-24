import json
from typing import Dict, Any, List
from brain import LLM_Ollama
from tools import list_all_tools, call_tool_by_name, expose_tools_as_service
from logger import logger
from utils.tts import PaddleTTS

# 初始化PaddleTTS实例
tts = PaddleTTS(server_ip = '172.30.3.7', server_port = 8092)

class AgentFramework:
    """
    Agent框架主类，协调模型A和模型B，以及工具调用流程
    """
    def __init__(self):
        # 初始化两个LLM实例，分别作为模型A和模型B
        self.llm_a = LLM_Ollama(model="qwen3:8b")
        self.llm_b = LLM_Ollama(model="qwen3:14b")
        # 清空默认消息，使用我们自定义的system prompt
        self.llm_a.messages = []
        self.llm_b.messages = []
        # 获取所有可用工具信息
        self.tools_info = list_all_tools()
        self.tools_service_info = expose_tools_as_service()
        # 初始化模型A和模型B的系统提示词
        self._init_system_prompts()
    
    def _init_system_prompts(self):
        """
        初始化模型A和模型B的系统提示词
        """
        # 模型A的system prompt - 判断任务是否需要使用工具
        model_a_system_prompt = """
        你是一个智能决策与调度中心，你的任务是分析用户的请求，并决定是直接回答还是需要调用工具来完成任务。
        你的回复表达及口吻需要更加自然、拟人，给用户以陪伴的感觉。
        可用的工具列表如下：
        {tools_list}
        
        请根据用户的问题，做出以下判断：
        1. 如果用户的问题可以直接通过对话回答，不需要调用任何工具，则直接生成回答。
        2. 如果用户的问题需要调用工具才能完成，请判断需要使用工具。
        
        请按照以下JSON格式输出你的决策和输出：
        {{
            "decision": "直接回答" 或 "需要工具",
            "content": "如果decision是'直接回答'，这里填写你的回答内容；如果decision是'需要工具'，这里根据用户问题及上下文，生成一段聊天文字回复，减少用户等待时间"
        }}
        
        请确保输出格式严格遵循上述JSON格式，不要包含任何其他无关的文本。
        """.format(tools_list="\n".join([f"- {tool['name']}: {tool['description']}" for tool in self.tools_info]))
        
        # 模型B的system prompt - 工具使用规划与调用
        model_b_system_prompt = """
        你是一个智能工具调度专家，你的任务是根据用户的请求和可用工具，规划工具调用步骤并生成正确的工具调用参数。
        你的回复表达及口吻需要更加自然、拟人，给用户以陪伴的感觉。
        可用的工具详细信息如下：
        {tools_detail}
        
        请根据用户请求和之前的对话历史，决定下一步操作：
        1. 如果需要调用工具，请生成工具调用的JSON格式，包含工具名称和所需参数
        2. 如果工具调用结果已获得，并且可以回答用户问题，请直接回答用户
        3. 如果需要继续调用其他工具，请生成下一个工具调用的JSON格式
        
        请按照以下格式输出：
        
        格式1（调用工具）：
        {{
            "action": "call_tool",
            "name": "工具名称",
            "params": {{
                "参数名1": "参数值1",
                "参数名2": "参数值2"
                // 请根据工具的实际参数要求填写
            }},
            "finish": false
        }}
        
        格式2（直接回答用户）：
        {{
            "action": "direct_answer",
            "content": "你的回答内容",
            "finish": true
        }}
        
        请确保输出格式严格遵循上述JSON格式，不要包含任何其他无关的文本。
        """.format(tools_detail=json.dumps(self.tools_service_info, ensure_ascii=False, indent=2))
        
        # 设置系统提示词
        self.llm_a.messages.append({"role": "system", "content": model_a_system_prompt})
        self.llm_b.messages.append({"role": "system", "content": model_b_system_prompt})
        logger.info("模型A系统提示词:")
        logger.info(model_a_system_prompt)
        logger.info("模型B系统提示词:")
        logger.info(model_b_system_prompt)
    
    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析模型返回的JSON格式响应
        """
        try:
            # 尝试直接解析响应
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            try:
                # 查找第一个{和最后一个}之间的内容
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                    return json.loads(json_str)
                else:
                    raise ValueError("无法在响应中找到有效的JSON格式")
            except Exception:
                # 如果提取也失败，返回错误信息
                return {
                    "error": "无法解析模型响应为JSON格式",
                    "raw_response": response
                }
    
    def process_user_query(self, user_query: str, model_a_name: str = "qwen3:14b", model_b_name: str = "qwen3:14b") -> Dict[str, Any]:
        """
        处理用户查询的主函数，返回JSON格式的结构化数据
        """
        # 初始化结果对象
        result = {
            "success": True,
            "finish": False,
            "content": "",
            "decision": "",
            "reason": "",
            "error": None,
            "tool_calls": []
        }
        
        # 第一步：使用模型A判断是否需要使用工具
        logger.info("[步骤1] 使用模型A分析用户请求...")
        model_a_response = self.llm_a.return_text(user_query, model_a_name)
        logger.info(f"模型A原始响应: {model_a_response}")
        
        # 解析模型A的响应
        parsed_a_response = self.parse_json_response(model_a_response)
        
        # 检查是否存在错误
        if "error" in parsed_a_response:
            result["success"] = False
            result["error"] = parsed_a_response["error"]
            result["content"] = f"处理错误: {parsed_a_response['error']}\n原始响应: {parsed_a_response['raw_response']}"
            return result
        
        # 记录模型A的决策和原因
        result["decision"] = parsed_a_response.get("decision", "")
        result["reason"] = parsed_a_response.get("reason", "")
        
        # 检查任务是否直接完成
        if parsed_a_response.get("decision") == "直接回答":
            logger.info("✓ 任务直接完成，不需要使用工具")
            result["finish"] = True
            result["content"] = parsed_a_response.get("content", "")
            # 调用TTS生成语音
            tts.tts(result["content"])
            return result
        elif parsed_a_response.get("decision") == "需要工具":
            result["content"] = parsed_a_response.get("content", "")
            # 调用TTS生成语音
            tts.tts(result["content"])
            logger.info("✓ 任务需要使用工具")
        
        # 第二步：如果需要使用工具，启动模型B的工具调用流程
        logger.info("[步骤2] 需要使用工具，启动工具调用流程...")
        
        # 初始化模型B的对话历史
        self.llm_b.messages.append({"role": "user", "content": user_query})
        
        # 工具调用循环
        while True:
            # 获取模型B的响应
            model_b_response = self.llm_b.return_text("", model_b_name)
            logger.info(f"模型B原始响应: {model_b_response}")
            
            # 解析模型B的响应
            parsed_b_response = self.parse_json_response(model_b_response)
            
            # 检查是否存在错误
            if "error" in parsed_b_response:
                result["success"] = False
                result["error"] = parsed_b_response["error"]
                result["content"] = f"处理错误: {parsed_b_response['error']}\n原始响应: {parsed_b_response['raw_response']}"
                return result
            
            # 检查任务是否完成
            if parsed_b_response.get("finish", False):
                logger.info("✓ 任务完成")
                result["finish"] = True
                result["content"] = parsed_b_response.get("content", "")
                # 调用TTS生成语音
                tts.tts(result["content"])
                return result
            
            # 调用工具
            if parsed_b_response.get("action") == "call_tool" or parsed_b_response.get("name") != "":
                tool_name = parsed_b_response.get("name")
                tool_params = parsed_b_response.get("params", {})
                
                logger.info(f"[工具调用] 调用工具: {tool_name}，参数: {tool_params}")
                
                # 记录工具调用信息
                tool_call_info = {
                    "name": tool_name,
                    "params": tool_params,
                    "success": True,
                    "result": None,
                    "error": None
                }
                
                try:
                    # 调用工具
                    tool_result = call_tool_by_name(tool_name, **tool_params)
                    tool_result_str = str(tool_result)
                    logger.info(f"工具调用结果: {tool_result_str}")
                    
                    # 更新工具调用信息
                    tool_call_info["result"] = tool_result_str
                    result["tool_calls"].append(tool_call_info)
                    
                    # 将工具调用结果发送给模型B
                    tool_result_message = f"工具调用结果:\n工具名称: {tool_name}\n结果: {tool_result_str}"
                    self.llm_b.messages.append({"role": "assistant", "content": tool_result_message})
                    
                except Exception as e:
                    error_message = f"工具调用失败: {str(e)}"
                    logger.error(error_message)
                    
                    # 更新工具调用信息
                    tool_call_info["success"] = False
                    tool_call_info["error"] = str(e)
                    result["tool_calls"].append(tool_call_info)
                    
                    # 将错误信息发送给模型B
                    self.llm_b.messages.append({"role": "assistant", "content": error_message})
            
            else:
                # 如果不是调用工具的action，返回错误
                unknown_action = parsed_b_response.get('action', 'unknown')
                error_msg = f"未知的操作类型: {unknown_action}"
                result["success"] = False
                result["error"] = error_msg
                result["content"] = error_msg
                return result

# 示例使用
if __name__ == "__main__":
    # 首先注册一些示例工具
    from tools import tool
    
    @tool(name="get_current_time", description="获取当前的时间")
    def get_current_time() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 初始化框架
    agent = AgentFramework()
    
    print("=== Agent Framework 演示 ===")
    print("可用工具:")
    for tool_info in agent.tools_info:
        print(f"- {tool_info['name']}: {tool_info['description']}")

    while True:
        user_query = input("\n请输入您的问题（输入'退出'结束）: ")
        if user_query.lower() == '退出':
            break
        response = agent.process_user_query(user_query)
        # 输出结构化的JSON结果
        print("\n最终结果（JSON格式）:")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        # 同时输出便于阅读的内容
        print(f"\n最终回答内容: {response.get('content', '')}")
        print(f"任务完成状态: {'是' if response.get('task_finish', False) else '否'}")
        if response.get('tool_calls'):
            print(f"工具调用次数: {len(response['tool_calls'])}")
            for i, tool_call in enumerate(response['tool_calls'], 1):
                print(f"  调用 {i}: {tool_call['tool_name']} - {'成功' if tool_call['success'] else '失败'}")
