from datetime import datetime
from openai import OpenAI
from logger import logger
base_url = "http://47.108.93.204:11435/v1"
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
            self.messages.append({"role": "assistant", "content": assistant_reply})
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
    a='''你是一个智能工具调度专家。
        可用的工具详细信息如下：
        {
  "tools": [
    {
      "name": "add",
      "description": "加法运算工具，计算两个数的和",
      "parameters": [
        {
          "name": "a",
          "type": "typing.Union[int, float]",
          "default": null
        },
        {
          "name": "b",
          "type": "typing.Union[int, float]",
          "default": null
        }
      ],
      "return_type": "typing.Union[int, float]",
      "module": "calculator"
    },
    {
      "name": "subtract",
      "description": "减法运算工具，计算两个数的差",
      "parameters": [
        {
          "name": "a",
          "type": "typing.Union[int, float]",
          "default": null
        },
        {
          "name": "b",
          "type": "typing.Union[int, float]",
          "default": null
        }
      ],
      "return_type": "typing.Union[int, float]",
      "module": "calculator"
    },
    {
      "name": "multiply",
      "description": "乘法运算工具，计算两个数的积",
      "parameters": [
        {
          "name": "a",
          "type": "typing.Union[int, float]",
          "default": null
        },
        {
          "name": "b",
          "type": "typing.Union[int, float]",
          "default": null
        }
      ],
      "return_type": "typing.Union[int, float]",
      "module": "calculator"
    },
    {
      "name": "divide",
      "description": "除法运算工具，计算两个数的商",
      "parameters": [
        {
          "name": "a",
          "type": "typing.Union[int, float]",
          "default": null
        },
        {
          "name": "b",
          "type": "typing.Union[int, float]",
          "default": null
        }
      ],
      "return_type": "typing.Union[int, float]",
      "module": "calculator"
    },
    {
      "name": "complex_calculate",
      "description": "输入给定字符串数学计算式，计算数学结果",
      "parameters": [
        {
          "name": "expression",
          "type": "<class 'str'>",
          "default": null
        }
      ],
      "return_type": "typing.Union[int, float]",
      "module": "calculator"
    },
    {
      "name": "get_weather",
      "description": "获取指定地点的天气信息，如果不提供地点则使用默认城市长沙，拿到结果之后需要进行总 结才能回复，需要精简回答，减少生成时间",
      "parameters": [
        {
          "name": "location",
          "type": "Any",
          "default": null
        }
      ],
      "return_type": "Any",
      "module": "get_weather"
    },
    {
      "name": "search_song_then_play",
      "description": "一步完成搜索歌曲并播放的功能，根据歌曲名称搜索并直接播放，如果有指定歌手（或者根 据聊天用户聊了歌手名），需要输入歌手名",
      "parameters": [
        {
          "name": "song_name",
          "type": "<class 'str'>",
          "default": null
        },
        {
          "name": "singer_name",
          "type": "<class 'str'>",
          "default": null
        }
      ],
      "return_type": "<class 'str'>",
      "module": "music_player"
    },
    {
      "name": "lyrics_to_song_name",
      "description": "用户输入歌词内容，想要查找对应的歌曲名时使用此工具。输入歌词内容，返回匹配到的歌 曲名",
      "parameters": [
        {
          "name": "lyrics",
          "type": "<class 'str'>",
          "default": null
        }
      ],
      "return_type": "<class 'str'>",
      "module": "music_player"
    },
    {
      "name": "get_songs_by_singer",
      "description": "用歌手名字搜索其歌曲列表，根据列表结果让用户选择想听的歌曲",
      "parameters": [
        {
          "name": "singer_name",
          "type": "<class 'str'>",
          "default": null
        }
      ],
      "return_type": "<class 'str'>",
      "module": "music_player"
    },
    {
      "name": "stop_music",
      "description": "用户说“停止播放音乐、停止播放、停止音乐播放”等类似的话一定调用此工具",
      "parameters": [],
      "return_type": "<class 'str'>",
      "module": "music_player"
    },
    {
      "name": "search_news_by_keyword_and_abstract",
      "description": "【搜索特定主题新闻】根据关键词搜索相关最新新闻。当用户询问特定主题、人物或事件的 新闻时使用此工具。拿到结果之后需要对新闻进行精简总结，**100字以内**",
      "parameters": [
        {
          "name": "keyword",
          "type": "Any",
          "default": null
        }
      ],
      "return_type": "Any",
      "module": "news_search"
    },
    {
      "name": "get_paper_news",
      "description": "【获取最新新闻概览】获取最新的综合新闻列表。当用户仅想了解当前有哪些热点新闻时使 用此工具。拿到结果之后需要对新闻进行精简总结，100字以内",
      "parameters": [],
      "return_type": "Any",
      "module": "news_search"
    }
  ]
}
        
        你的任务是根据用户请求调用工具或直接回答。
        
        *** 非常重要：输出格式规则 ***
        
        模式 A - 需要调用工具时：
        请输出标准的 JSON 格式，格式如下：
        {
            "action": "call_tool",
            "name": "工具名称",
            "params": { "参数名": "参数值" }
        }
        
        模式 B - 已获得工具结果或直接回答时：
        **请不要使用 JSON！请不要使用 JSON！**
        直接输出你要对用户说的自然语言内容。不要带任何前缀，直接说话。'''
    input_text = [{'role':'system','content':a},
        {'role':'user','content':'我想听周杰伦的歌'}]
    # 测试普通输出方式
    print("\n普通输出方式:")
    # answer = llm.return_text(input_text,"qwen3:14b")
    answer = llm.client.chat.completions.create(
                model="qwen3:14b",
                messages=input_text
            )
    print(answer)
    
    # 测试流式输出方式
    # print("\n流式输出方式:")
    # for chunk in llm.stream_text("再生成一个300字的故事", "qwen3:8b"):
    #     print(chunk, end='', flush=True)
    # print("\n")
    
    # # 测试14b模型的流式输出
    # print("\n使用14b模型的流式输出:")
    # for chunk in llm.stream_text("简单介绍一下AI", "qwen3:14b"):
    #     print(chunk, end='', flush=True)
    # print("\n")
