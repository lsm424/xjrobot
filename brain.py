from datetime import datetime
from openai import OpenAI
from logger import logger
base_url = "http://47.108.93.204:11435/v1"
# tool_base_url = "http://47.108.93.204:11435/v1"
# tool_base_url = "http://47.108.93.204:18000/v1"
class LLM_Ollama:
    def __init__(self, base_url=base_url, api_key="ollama", temperature=0.9, top_k=1, max_tokens=5012, model="qwen3:14b"):
        """
        初始化本地对话助手，用户选择模型
        """
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model
        self.messages = [{"role": "system", "content": "你是一个有帮助的助手。"}]

    def return_text(self, user_text, llm_model):
        """
        输入用户文本，返回助手回复文本，并更新上下文
        """
        if user_text != "":
          user_text = '/no_think\n'+user_text
          self.messages.append({"role": "user", "content": user_text})
        # else:
        # # user_text = user_text
        #   user_text = '/no_think请你根据前一次工具结果继续完成用户的请求\n'+''
        #   self.messages.append({"role": "assistant", "content": user_text})
        # user_text = '/no_think\n'+user_text
        # self.messages.append({"role": "user", "content": user_text})
        logger.info(f'messages 长度 ：{len(self.messages)}')
        if len(self.messages) > 20:
            # 保留第0条系统提示词，截取最近19条用户/助手对话
            self.messages = [self.messages[0]] + self.messages[-19:]
        logger.info(f'模型接收的输入: {self.messages[1:]}')
        try:
            dt = datetime.now()  # 取当前时间:2024-11-19 14:34:54 350897
            logger.info(f'请求时间: {dt.strftime("%Y-%m-%d %H:%M:%S %f")}')
            response = self.client.chat.completions.create(
                model=llm_model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            assistant_reply = response.choices[0].message.content.strip()
            dt = datetime.now()  # 取当前时间:2024-11-19 14:34:54 350897
            logger.info(f'回复生成结束时间: {dt.strftime("%Y-%m-%d %H:%M:%S %f")}')
            # logger.info(f'回复内容: {assistant_reply}')
            assistant_reply=assistant_reply.split('</think>')[-1].strip()
            a = assistant_reply.split('\n')
            if a[0]==a[-1]:
                assistant_reply = a[0]
            self.messages.append({"role": "assistant", "content": assistant_reply})
            for i,msg in enumerate(self.messages):
                if msg['role'] == 'assistant':
                    if len(msg['content']) > 200 :
                        self.messages[i]['content'] = msg['content'][:100]+'...'+msg['content'][-100:]
            return assistant_reply
        except Exception as e:
            return f"[错误] 请求失败：{e}"
    
    def stream_text(self, user_text, llm_model):
        """
        输入用户文本，以流式方式返回助手回复文本，并更新上下文
        """
        user_text = '/no_think\n'+user_text
        self.messages.append({"role": "user", "content": user_text})
        logger.info(f'messages 长度 ：{len(self.messages)}')
        
        if len(self.messages) > 20:
            # 保留第0条系统提示词，截取最近19条用户/助手对话
            self.messages = [self.messages[0]] + self.messages[-19:]
        logger.info(f'模型接收的输入: {self.messages[1:]}')
        full_reply = ""
        try:
            dt = datetime.now()
            logger.info(f'流式请求时间: {dt.strftime("%Y-%m-%d %H:%M:%S %f")}')
            
            # 使用stream=True参数获取流式响应
            stream = self.client.chat.completions.create(
                model=llm_model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            # 逐块生成响应
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content is not None and chunk.choices[0].delta.content != '':
                    content = chunk.choices[0].delta.content
                    full_reply += content
                    yield content
            
            dt = datetime.now()
            logger.info(f'流式回复结束时间: {dt.strftime("%Y-%m-%d %H:%M:%S %f")}')
            
            # 处理完整回复并更新上下文
            if '</think>' in full_reply:
                think_end = full_reply.rfind('</think>')
                full_reply = full_reply[think_end+len('</think>'):]
            
            self.messages.append({"role": "assistant", "content": full_reply})
            
        except Exception as e:
            error_message = f"[错误] 流式请求失败：{e}"
            yield error_message
''''''
if __name__ == '__main__':
    input_text = '生成500字的故事'
    llm = LLM_Ollama()
    # a=''''''
    # input_text = [{'role':'system','content':a},
    #     {'role':'user','content':'我想听周杰伦的歌'}]
    # 测试普通输出方式
    # print("\n普通输出方式:")
    # answer = llm.return_text(input_text,"qwen3:14b")
    # answer = llm.client.chat.completions.create(
    #             model="qwen3:14b",
    #             messages=input_text
    #         )
    # print(answer)
    
    # 测试流式输出方式
    print("\n流式输出方式:")
    for chunk in llm.stream_text("再生成一个300字的故事", "qwen3:14b"):
        print(chunk, end='/n', flush=True)
    print("\n")
    
    # # 测试14b模型的流式输出
    # print("\n使用14b模型的流式输出:")
    # for chunk in llm.stream_text("简单介绍一下AI", "qwen3:14b"):
    #     print(chunk, end='', flush=True)
    # print("\n")
