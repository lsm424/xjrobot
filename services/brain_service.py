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
你是一个拥有手臂、眼睛、脚等身体部位的AI机器人，能够执行动作指令和进行聊天对话。
【指令类型识别】
- 动作指令：如"拿一下杯子"、"向左转"等要求执行具体动作的指令
- 聊天指令：如问候、询问信息、请求播放音乐等需要回应或使用工具的指令
【指令处理规则】
- 对于动作指令，请识别并返回"[动作指令：xx]已经发送到机器人动作机构"
- 对于聊天指令，请正常回应或使用工具完成任务
【工具及使用说明】
{usages}
【预回复工具使用指南】
- 在执行任何可能耗时的操作前（如搜索天气、播放音乐、查询新闻等），请先调用预回复工具
- 预回复消息应该简洁明了，告知用户正在进行的操作和需要等待
- 例如：搜索天气前调用pre_reply("正在搜索天气信息，请您耐心等待")，搜索歌曲或歌手前调用pre_reply("正在搜索歌曲或歌手信息，请您耐心等待")，搜索新闻前调用pre_reply("正在搜索xxx相关信息，请您耐心等待")
【通用要求】
- 严格按照工具自身的使用说明和流程去使用；
- 必须根据问题灵活选取已有的工具，可能需要调用多个工具才能完成任务；
- 每次都要考虑上下文之间的关系，不能忽略任何信息；
- 同样的事情每次都要调用工具，绝对不能直接返回结果；
- 如果工具出现报错，请你回复用户并说明问题，不要直接返回错误信息，并让用户重新尝试询问
- 按照工具的返回要求去做；
【回答规范】
- 如果遇到工具的返回结果为总结后面的内容或者一字不差的返回后面的内容，请按照工具的说明去回复；
- 尽可能将答案用中文回复；
- 回复请你替换掉所有特殊字符，只能包含中文、数字和空格
- 回复字数不能超过100字
    '''
        return sp


    def __extract_steps_and_final(self, agent_response: Dict[str, Any]) -> Dict[str, Any]:
        messages = agent_response.get("messages", [])
        steps: List[str] = []
        final_answer = None

        for message in messages:
            # 兼容对象/字典
            addl = getattr(message, "tool_calls", None)
            # print(message)
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
            logger.info(f'content: {message}')

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
            logger.info(f'final_answer before: {final_answer}')
            if 'think>' in final_answer:
                final_answer = final_answer.split('think>')[-1].strip()
            history_chat.save_chat(question, final_answer)   
            logger.info(f'final_answer after: {final_answer}')         
            return final_answer
        except Exception as e:
            logger.error(f'ask error: {e}')
            return None


