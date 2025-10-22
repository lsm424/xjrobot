import logging
import requests
import webbrowser
import urllib.parse
from langchain.tools import tool
from common import logger
from .base import ToolBase
from typing import Literal
from pydantic import Field

class MusicPlayerTool(ToolBase):
    def __init__(self):
        super().__init__(name='音乐播放器')

    def usage(self) -> Literal[str|None]:
        return '''1.用户输入：‘我想听xxx’或者’xxx‘或者’换一个xxx‘（我想听几个字可以省略，xxx为歌曲名，工具使用链路为search_song_id→get_song_url）
2.用户输入：‘我想听xxx的歌’或者‘我想听xxx’或者‘换一个xxx的歌’（我想听几个字可以省略，xxx为人名，工具使用链路为search_singer_id→get_songs_by_singer获取歌曲列表给用户选择，进入下一轮对话，下一轮对话有歌曲名回到步骤1）
3.用户输入：‘xxx有些什么歌？’（xxx为人名，回到步骤2）
4.用户输入：‘xxx的yyy‘或者’xxx yyy‘（我想听几个字可以省略，xxx为人名，yyy为歌曲名，工具使用链路为search_song_id→get_song_url）
根据工具调用返回的结果综合回复，比如工具返回歌曲列表，引导用户进行选择；如果确认工具返回播放链接调用成功，回复用户播放xxx成功，否则需要提醒用户没能正确播放'''


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
                
                # 在浏览器中打开链接进行播放
                try:
                    webbrowser.open(song_url)
                    success_message = f"操作成功，已尝试在浏览器中播放 '{song_name}'。"
                    logger.info(success_message)
                    return f"歌曲 '{song_name}' 的播放链接: {song_url}\n{success_message}"
                except Exception as e:
                    logger.error(f"无法打开浏览器: {e}", exc_info=True)
                    return f"歌曲 '{song_name}' 的播放链接: {song_url}\n错误：无法打开浏览器进行播放: {e}"
            else:
                logger.error(f"未能为 mid '{song_mid}' 获取到有效的播放链接")
                return "错误：未能从API获取到有效的播放链接"

        except Exception as e:
            logger.error(f"获取播放链接时发生错误: {e}, song_mid: {song_mid}", exc_info=True)
            return f"错误：获取播放链接时发生网络或解析错误: {e}"

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
                
                return f"{id_message}\n(请你一字不差的返回后面的话)找到歌手 '{singer_name}' 的歌曲列表，请告诉我您想听哪首歌的名称：\n{song_list_message}"
            else:
                logger.warning(f"未能获取歌手ID {singer_mid} 的歌曲列表")
                return f"未能获取歌手ID {singer_mid} 的歌曲列表"

        except Exception as e:
            logger.error(f"获取歌手歌曲列表时发生错误: {e}", exc_info=True)
            return f"错误：获取歌手歌曲列表时发生网络或解析错误: {e}"

if __name__ == "__main__":
    logger.info("启动音乐播放器服务 (Music Player Server) ...")
    # run(transport="stdio")