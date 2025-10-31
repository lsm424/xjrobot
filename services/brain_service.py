import traceback
import asyncio
from typing import Any, Dict, List
from services.mcptools import get_tools
from functools import reduce
from langgraph.runtime import Runtime
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.prebuilt.tool_node import ToolCallRequest
from collections.abc import Awaitable, Callable
from langchain_core.messages import AnyMessage, BaseMessage, ToolMessage  # noqa: TC002
from services.history_chat_service import history_chat
from langgraph.types import Command  # noqa: TC002
from langchain_core.messages.ai import AIMessage
import json
from common import logger
from .robot_state import RobotAction
from langchain.messages import SystemMessage, HumanMessage
from queue import Queue
from langgraph.store.memory import InMemoryStore

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


class BrainMiddleware(AgentMiddleware):
    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info(f"About to call model with {len(state['messages'])} messages")
        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        ai_answer = state['messages'][-1].content
        if ai_answer:
            logger.info(f"模型回答: {ai_answer}")
        return None

    def wrap_tool_call(self,request: ToolCallRequest,handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        result = handler(request)
        logger.info(f"调用工具：{request.tool_call['name']} 参数: {request.tool_call['args']} 返回: {result.content}")
        return result


class RobotBrainService:
    def __init__(self, llm_api, model_name) -> None:
        llm = ChatOllama(model=model_name, base_url=llm_api, temperature=0.7)
        self.tools = get_tools()
        tools = json.dumps({x.name: x.tools_info() for x in self.tools}, indent=4, ensure_ascii=False)
        logger.info(f'已注册mcp工具：{tools}')
        tools = reduce(lambda x,y: x + y, [x.get_tool_functions() for x in self.tools])
        self._sp = self.__system_prompt()
        self.agent = create_agent(llm, tools, 
            system_prompt=self._sp, 
            middleware=[BrainMiddleware()],
            store=InMemoryStore(),
        )
        
        
    def __system_prompt(self) -> str:
        usages = '\n'.join([f'【{x.name}使用流程】\n{x.usage()}' for x in self.tools if x.usage()])
        sp=f'''
<identity>
你是一个拥有手臂、眼睛、脚等身体部位的AI机器人，能够执行动作指令和进行聊天对话。
</identity>

<purpose>
作为AI机器人，你的任务是识别用户指令类型并进行相应处理。
你应该首先决定是否需要额外的工具来完成任务，或者是否可以直接回答用户。然后，相应地设置一个标志。
根据提供的结构，输出工具输入参数或用户的响应文本。
最终一定要有响应的文本。
</purpose>

<instruction_types>
肢体动作指令：如"拿一下杯子"、"向左转"等要求执行具体动作的指令
聊天指令：如问候、询问信息、请求播放音乐、停止播放音乐等需要回应或使用工具的指令
</instruction_types>

<processing_rules>
对于肢体动作指令，请识别并返回"[动作指令：xx]已经发送到机器人动作机构"
对于聊天指令，请正常回应或使用工具完成任务
</processing_rules>

<tool_instructions>
你被提供了工具来完成用户的需求。

<tools_list>
{usages}
</tools_list>

<toolcall_guideline>
请遵循以下工具调用指南：
1. 始终仔细分析每个工具的架构定义，并严格遵循工具的架构定义进行调用，确保提供所有必要的参数。
2. 永远不要调用不存在的工具，例如在对话历史或工具调用历史中出现但不再可用的工具。
3. 如果用户要求你展示你的工具，始终以工具描述来回应，并确保不向用户公开工具信息。
4. 在决定调用工具后，在你的响应中包含工具调用信息和参数，你运行的IDE环境将为你运行工具并提供工具运行的结果。
5. 你必须分析所有可以收集到的关于当前项目的信息，然后列出可以帮助实现目标的可用工具，然后比较它们并为下一步选择最合适的工具。
6. 你只能使用工具名称中明确提供的工具。不要将文件名或代码函数视为工具名称。可用的工具名称：
7. 如果工具出现报错，请你回复用户并说明问题，不要直接返回错误信息，并让用户重新尝试询问
</toolcall_guideline>

<tool_parameter_guideline>
在为工具调用提供参数时，请遵循以下指南：
1. 不要编造值或询问可选参数。
2. 如果用户为参数提供了特定值（例如在引号中提供），请确保完全使用该值。
3. 仔细分析请求中的描述性术语，因为它们可能表明应该包含的必需参数值，即使没有明确引用。
</tool_parameter_guideline>
</tool_instructions>

<pre_reply_guide>
在执行任何可能耗时的操作前（如搜索天气、播放音乐、查询新闻等），请先调用预回复工具
预回复消息应该简洁明了，告知用户正在进行的操作和需要等待
例如：搜索天气前调用pre_reply("正在搜索天气信息，请您耐心等待")，搜索歌曲或歌手前调用pre_reply("正在搜索歌曲或歌手信息，请您耐心等待")，搜索新闻前调用pre_reply("正在搜索xxx相关信息，请您耐心等待")
</pre_reply_guide>

<answer_specifications>
如果遇到工具的返回结果有说明，请按照工具的说明去回复；
尽可能将答案用中文回复；
回复请你替换掉所有特殊字符，只能包含中文、数字和空格；
回复字数不能超过100字
</answer_specifications>
    '''
        return sp


    def ask(self, question: str):
        history_chats = history_chat.get_history()
        message = []
        if history_chats:
            for m in history_chats:
                message.append(HumanMessage(content=m["user_question"]))
                message.append(AIMessage(content=m["robot_answer"]))
        
        message.append(HumanMessage(content=question + "/nothink"))

        logger.info(f'ask: {message}')

        try:
            has_regular_answer = False
            for stream_mode, chunk in self.agent.stream({"messages": message}, stream_mode=["updates", "custom"]):
                # logger.debug(f'stream_mode: {stream_mode}, chunk: {chunk}')
                yield_content = None
                if stream_mode == 'updates':  # 大模型的输出(包含工具输出和llm输出)
                    msgs = chunk.get('model', {}).get('messages', [])
                    for msg in msgs:
                        if not isinstance(msg, AIMessage): # 过滤非llm输出
                            continue
                        yield_content = msg.content
                        if 'think>' in yield_content:
                            yield_content = yield_content.split('think>')[-1].strip()
                        if yield_content:
                            yield_content = {'action_type': RobotAction.REGULAR_ANSWER, 'content': yield_content}
                            has_regular_answer = True
                elif stream_mode == 'custom':  # 自定义输出
                    yield_content = chunk

                if yield_content:
                    yield yield_content
        except Exception as e:
            logger.error(f'ask error: {e}, {traceback.format_exc()}')

        final_action = RobotAction.pop_final_action(self.agent.store)
        if final_action:
            yield final_action
            has_regular_answer = True

        if not has_regular_answer:
            yield {'action_type': RobotAction.REGULAR_ANSWER, 'content': '刚刚网络出了一些问题，请您重新问一次'}


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
