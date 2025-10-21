import asyncio
from typing import Any, Dict, List
from services.mcptools import get_tools
from functools import reduce
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from services.history_chat_service import history_chat
import json
from common import logger

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


class RobotBrainService:
    def __init__(self, llm_api, model_name) -> None:
        llm = ChatOllama(model=model_name, base_url=llm_api, temperature=0.7)
        self.tools = get_tools()
        tools = json.dumps({x.name: x.tools_info() for x in self.tools}, indent=4, ensure_ascii=False)
        logger.info(f'已注册mcp工具：{tools}')
        tools = reduce(lambda x,y: x + y, [x.get_tool_functions() for x in self.tools])
        self.agent = create_react_agent(llm, tools)
        self._sp = self.__system_prompt()
        
    def __system_prompt(self) -> str:
        usages = '\n'.join([f'【{x.name}使用流程】\n{x.usage()}' for x in self.tools if x.usage()])
        sp=f'''
你是一个会熟练使用工具tools的多功能agent，能够根据用户需求灵活选取合适的工具完成任务。
当前你具备音乐播放相关功能，未来将逐步扩展更多功能（如聊新闻、播放课程等）。
{usages}
【通用要求】
- 必须根据问题灵活选取已有的工具，可能需要调用多个工具才能完成任务；
- 每次都要考虑上下文之间的关系，不能忽略任何信息；
- 同样的事情每次都要调用工具，**绝对不能直接返回结果**；
- 随着功能扩展，要学会适配新工具的使用方法和流程。
- 如果工具出现报错，请你回复用户并说明问题，不要直接返回错误信息，并让用户重新尝试询问
    '''
        return sp


    def __extract_steps_and_final(self, agent_response: Dict[str, Any]) -> Dict[str, Any]:
        messages = agent_response.get("messages", [])
        steps: List[str] = []
        final_answer = None

        for message in messages:
            # 兼容对象/字典
            addl = getattr(message, "tool_calls", None)
            print(message)
            if addl:
                tool_name = addl[0]["name"]
                tool_args = addl[0]["args"]
                steps.append(f"调用工具: {tool_name}({tool_args})")
                continue

            mtype = getattr(message, "type", None)
            if mtype == "tool":
                tool_name = getattr(message, "name", "")
                tool_result = getattr(message, "content", "")
                steps.append(f"{tool_name} 的结果是: {tool_result}")
            elif mtype == "ai":
                final_answer = getattr(message, "content", None)

        return steps, final_answer

    def ask(self, question: str):
        history_chats = history_chat.get_history()
        if history_chats:
            history_chats = ';'.join(map(lambda x: f'用户问了{x["user_question"]},回复为{x["robot_answer"]}', history_chats))
            formatted_question = f"之前{history_chats}...现在接着问的是：{question} /nothink"
        else:
            formatted_question = question + "/nothink"
        
        message = [{"role": "system", "content": self._sp},
            {"role": "user", "content": formatted_question}]
        logger.info(f'ask: {message}')
        
        try:
            agent_response = LOOP.run_until_complete(self.agent.ainvoke({"messages": message}))
            steps, final_answer = self.__extract_steps_and_final(agent_response)
            logger.info(f'steps: {steps}')
            if '</think>' in final_answer:
                final_answer = final_answer.split('</think>')[-1].strip()
            history_chat.save_chat(question, final_answer)            
            return final_answer
        except Exception as e:
            logger.error(f'ask error: {e}')
            return None


