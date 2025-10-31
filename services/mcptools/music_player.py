import requests
import urllib.parse
import re
from langchain.tools import tool
from common import logger
from .base import ToolBase
from typing import Literal
from pydantic import Field
from infra.audio import audio_player
from langgraph.config import get_stream_writer
from services.robot_state import RobotAction


class MusicPlayerTool(ToolBase):
    def __init__(self):
        
        super().__init__(name='音乐播放器')

    def usage(self) -> Literal[str|None]:
        return '''1.用户输入：‘我想听xxx’或者’xxx‘或者’换一个xxx‘（我想听几个字可以省略，xxx为歌曲名，工具使用链路为search_song_id→get_song_url）
2.用户输入：‘我想听xxx的歌’或者‘我想听xxx’或者‘换一个xxx的歌’（我想听几个字可以省略，xxx为人名，工具使用链路为search_singer_id→get_songs_by_singer获取歌曲列表给用户选择，进入下一轮对话，下一轮对话有歌曲名回到步骤1）
3.用户输入：‘xxx有些什么歌？’（xxx为人名，回到步骤2）
4.用户输入：‘xxx的yyy‘或者’xxx yyy‘（我想听几个字可以省略，xxx为人名，yyy为歌曲名，工具使用链路为search_song_id→get_song_url）
5.用户输入：‘我想听歌词xxx的歌’或者‘xxx是什么歌’（xxx为歌词内容，工具使用链路为lyrics_to_song_name→search_song_id→get_song_url）
根据工具调用返回的结果综合回复，比如工具返回歌曲列表，引导用户进行选择；如果确认工具返回播放链接调用成功，回复用户播放xxx成功，否则需要提醒用户没能正确播放
如果是停止播放，需要调用stop_music工具'''


    @tool(description="有歌曲名字的情况下（或者用户选择了某首歌），根据歌曲名称搜索歌曲ID,(如果已经通过对话获取了用户想听的歌曲名字，先使用这个工具获取歌曲ID，再使用get_song_url工具获取歌曲链接)")
    def search_song_id(song_name: str = Field(..., description="歌曲名称")) -> str:
        """根据歌曲名称搜索歌曲ID"""
        logger.info(f"搜索歌曲ID: '{song_name}'")
        
        try:
            encoded_song_name = urllib.parse.quote(song_name)
            search_url = f"https://api.vkeys.cn/v2/music/tencent/search/song?word={encoded_song_name}"
            logger.info(f"正在搜索 URL: {search_url}")
            
            search_response = requests.get(search_url, timeout=15)
            search_response.raise_for_status()
            search_data = search_response.json()

            song_list = search_data.get('data', [])
            
            if isinstance(song_list, list) and song_list:
                # 返回第一个匹配的歌曲ID
                first_song = song_list[0]
                song_id = first_song.get('id')
                song_mid = first_song.get('mid')
                song_name = first_song.get('song')
                singer = first_song.get('singer')
                
                logger.info(f"找到歌曲: '{song_name}' by {singer}, ID: {song_id}, MID: {song_mid}")
                return f"歌曲 '{song_name}' 的ID是: {song_id}, MID是: {song_mid}"
            else:
                logger.warning(f"未找到歌曲: '{song_name}'")
                return f"未找到歌曲: '{song_name}'"

        except Exception as e:
            logger.error(f"搜索歌曲ID时发生错误: {e}", exc_info=True)
            return f"错误：搜索歌曲ID时发生网络或解析错误: {e}"

    @tool(description="根据search_song_id的结果，有歌曲ID的情况下，根据歌曲ID搜索歌曲链接并播放")
    def get_song_url(song_mid: str = Field(..., description="歌曲MID")) -> str:
        """根据歌曲ID搜索歌曲链接并播放"""
        logger.info(f"获取歌曲链接，MID: '{song_mid}'")
        
        try:
            get_url_api = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={song_mid}"
            logger.info(f"正在获取播放链接 URL: {get_url_api}")

            url_response = requests.get(get_url_api, timeout=15)
            url_response.raise_for_status()
            url_data = url_response.json()

            data = url_data.get('data', {})
            song_name = data.get('song')
            song_url = data.get('url')

            if song_url:
                logger.info(f"成功获取歌曲 '{song_name}' 的播放链接")
                try:
                    RobotAction.action_immediate(RobotAction.PLAY_AUDIO, song_url)
                    return f"即将歌曲 '{song_name}' 的播放链接: {song_url}"
                except Exception as e:
                    logger.error(f"无法播放歌曲 '{song_name}': {e}", exc_info=True)
                    return f"歌曲 '{song_name}' 的播放链接: {song_url}\n错误：无法播放歌曲: {e}"
            else:
                logger.error(f"未能为 mid '{song_mid}' 获取到有效的播放链接")
                return "错误：未能从API获取到有效的播放链接"

        except Exception as e:
            logger.error(f"获取播放链接时发生错误: {e}, song_mid: {song_mid}", exc_info=True)
            return f"错误：获取播放链接时发生网络或解析错误: {e}"

    # 百度千帆 AI 搜索 API 配置
    API_KEY = "bce-v3/ALTAK-rTSowOKEosFuKCKBvu6Rq/8bcca13ea79cc98570ca9ea40c5e8e70a4aacc87"
    BAIDU_API_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"

    def call_baidu_ai_search(self, search_query: str):
        """
        调用百度千帆 AI 搜索 API。
        :param search_query: 搜索查询词 (例如: "窗外的麻雀 歌名")
        :return: (dict) 成功时返回 API 响应的 JSON 字典, (str) 失败时返回错误信息
        """
        headers = {
            'Authorization': f'Bearer {self.API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
          "messages": [
            {
              "content": search_query,
              "role": "user"
            }
          ],
          "search_source": "baidu_search_v2",
          "resource_type_filter": [{"type": "web", "top_k": 5}]
        }
        
        logger.info(f"Sending to Baidu API with content: {search_query}")
        
        try:
            response = requests.post(self.BAIDU_API_URL, headers=headers, json=data)
            
            if response.status_code == 200:
                response_json = response.json()
                return response_json, None 
                
            else: # HTTP 错误
                if response.status_code in [401, 403, 429]:
                     logger.warning(f"Received {response.status_code}, triggering Error_search_engine_SV")
                     return None, "Error_search_engine_SV"
                
                logger.error(f"HTTP Error {response.status_code}: {response.text}")
                return None, f"Error: HTTP {response.status_code} - {response.text}"
                
        except requests.exceptions.RequestException as e:
            logger.critical(f"Network Error during Baidu API call: {e}")
            return None, f"Network Error: {e}"
    
    def parse_song_from_title(self, title: str) -> str:
        """
        辅助函数：尝试从搜索结果标题中解析歌名。
        例如："周杰伦 - 七里香 (Live)" -> "七里香"
        """
        if not title:
            return ""
        
        song_name = title
        if ' - ' in title:
            song_name = title.split(' - ')[-1] # 取 "七里香 (Live)"
        
        # 移除 (Live), (DJ版) 等
        song_name = song_name.split(' (')[0] 
        song_name = song_name.split(' [')[0]
        
        return song_name.strip("《》")
    
    @tool(description="用户输入歌词内容，想要查找对应的歌曲名时使用此工具。输入歌词内容，返回匹配到的歌曲名")
    def lyrics_to_song_name(lyrics: str = Field(..., description="歌词内容")) -> str:
        """
        根据歌词内容搜索歌曲名称
        """
        logger.info(f"根据歌词搜索歌曲名: '{lyrics}'")
        
        try:
            # 构建搜索关键词
            search_keyword = f"{lyrics} 歌名"
            
            # 调用百度AI搜索
            music_tool = MusicPlayerTool()
            response_json, error_msg = music_tool.call_baidu_ai_search(search_keyword)
            
            if error_msg:
                logger.warning(f"百度搜索失败。返回错误: {error_msg}")
                return error_msg
            
            final_song = None
            result_text = response_json.get("result") # 获取 AI 总结
    
            # 1. 优先使用 'result' (AI 总结)
            if result_text:
                logger.info(f"使用AI生成的'result'字段: {result_text}")
                final_song = result_text
    
            # 2. 'result' 失败，降级到 'references' (原始搜索结果)
            else:
                logger.warning("'result'字段缺失或为空。回退到解析'references'。")
                references = response_json.get("references")
                if not references:
                    logger.error("'result'和'references'都缺失。")
                    return "错误: 百度API未返回结果或引用。"
                
                # 只看第一个搜索结果
                ref_one = references[0]
                content = ref_one.get('content', '') + ref_one.get('title', '')
                
                # 优先在第一个结果中查找 "《歌名》"
                match = re.search(r"《([^》]+)》", content) 
                if match:
                    song_name = match.group(1).strip()
                    if "专辑" not in content and len(song_name) < 20: 
                        final_song = song_name
                        logger.info(f"回退方案: 在第一个引用中找到'《{final_song}》'")
                
                # 如果第一个结果中没有 《》，则解析第一个结果的标题
                if not final_song:
                    first_title = ref_one.get('title', '')
                    logger.info(f"回退方案: 在第一个引用中未找到'《...》'。解析标题: '{first_title}'")
                    final_song = music_tool.parse_song_from_title(first_title)
        
            if not final_song:
                logger.error(f"无法从AI结果或回退方案中解析歌曲名。响应: {response_json}")
                return "错误: 无法解析歌曲名"
    
            final_result = final_song.strip("《》\"'。， ")
            logger.info(f"成功匹配歌曲。返回: {final_result}")
            return f"根据歌词匹配到的歌曲是: {final_result}"
    
        except Exception as e:
            logger.critical(f"lyrics_to_song_name工具中未处理的异常: {e}", exc_info=True)
            return f"服务器错误: {str(e)}"

    @tool(description="用户只提及歌手名字的情况下，根据歌手名搜索歌手ID，为get_songs_by_singer做准备，完成之后一定要调用get_songs_by_singer")
    def search_singer_id(singer_name: str = Field(..., description="歌手名称")) -> str:
        """根据歌手名搜索歌手ID"""
        logger.info(f"搜索歌手ID: '{singer_name}'")
        
        try:
            encoded_singer_name = urllib.parse.quote(singer_name)
            search_url = f"https://api.vkeys.cn/v2/music/tencent/search/singer?word={encoded_singer_name}"
            logger.info(f"正在搜索 URL: {search_url}")
            
            search_response = requests.get(search_url, timeout=15)
            search_response.raise_for_status()
            search_data = search_response.json()

            singer_list = search_data.get('data', [])
            
            if isinstance(singer_list, list) and singer_list:
                # 返回第一个匹配的歌手ID
                first_singer = singer_list[0]
                singer_id = first_singer.get('singerID')
                singer_mid = first_singer.get('singerMID')
                singer_name = first_singer.get('singerName')
                
                logger.info(f"找到歌手: '{singer_name}', ID: {singer_id}, MID: {singer_mid}")
                return f"歌手 '{singer_name}' 的ID是: {singer_id}, MID是: {singer_mid}"
            else:
                logger.warning(f"未找到歌手: '{singer_name}'")
                return f"未找到歌手: '{singer_name}'"

        except Exception as e:
            logger.error(f"搜索歌手ID时发生错误: {e}", exc_info=True)
            return f"错误：搜索歌手ID时发生网络或解析错误: {e}"

    @tool(description="search_singer_id的后置步骤，根据search_singer_id的搜索结果，用歌手ID搜索其歌曲列表，并让用户选择想听的歌曲")
    def get_songs_by_singer(singer_mid: str = Field(..., description="歌手MID")) -> str:
        """根据歌手ID搜索其歌曲列表并让用户选择想听的歌曲"""
        logger.info(f"获取歌手ID {singer_mid} 的歌曲列表")
        
        try:
            song_list_url = f"https://api.vkeys.cn/v2/music/tencent/singer/songlist?mid={singer_mid}"
            logger.info(f"正在获取歌手歌曲列表 URL: {song_list_url}")
            
            song_list_response = requests.get(song_list_url, timeout=15)
            song_list_response.raise_for_status()
            song_list_data = song_list_response.json()

            song_list = song_list_data.get('data', [])
            
            if isinstance(song_list, list) and song_list:
                # 获取歌手名称
                singer_name = song_list[0].get('singer', '未知歌手')
                
                # 提取所有歌曲名称
                song_names = []
                name_mid_map = []
                for i, song in enumerate(song_list[:10], 1):  # 限制显示前10首歌曲
                    song_name = song.get('song', '未知歌曲')
                    song_mid = song.get('mid', '未知MID')
                    song_names.append(f"{i}. {song_name}")
                    name_mid_map.append((f"{i}. {song_name}", song_mid))
                
                logger.info(f"成功获取歌手 '{singer_name}' 的歌曲列表")
                
                # 构建回复消息，询问用户想听哪首歌
                song_list_message = "\n".join(song_names)
                id_message = "\n".join([f"{name} (MID: {mid})" for name, mid in name_mid_map])
                if len(song_list) > 10:
                    song_list_message += f"\n... 还有 {len(song_list) - 10} 首歌曲未显示"
                
                return f"{id_message}\n请你一字不差的返回后面的话:找到歌手 '{singer_name}' 的歌曲列表，请告诉我您想听哪首歌的名称：\n{song_list_message}"
            else:
                logger.warning(f"未能获取歌手ID {singer_mid} 的歌曲列表")
                return f"未能获取歌手ID {singer_mid} 的歌曲列表"

        except Exception as e:
            logger.error(f"获取歌手歌曲列表时发生错误: {e}", exc_info=True)
            return f"错误：获取歌手歌曲列表时发生网络或解析错误: {e}"

    @tool(description='用户说“停止播放”等类似的话调用此工具')
    def stop_music() -> str:
        """停止播放音乐"""
        RobotAction.action_immediate(RobotAction.STOP_AUDIO)
        return "音乐播放已停止"




if __name__ == "__main__":
    logger.info("启动音乐播放器服务 (Music Player Server) ...")
    # run(transport="stdio")