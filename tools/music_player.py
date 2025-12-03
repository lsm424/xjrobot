import requests
import urllib.parse
import re
from logger import logger
from tools import tool
from utils.audio import audio_player

@tool(name="search_song_then_play", description="""一步完成搜索歌曲并播放的功能，根据歌曲名称搜索并直接播放
                                  输入：歌曲名称，例如 晴天，如果有指定歌手（或者根据聊天用户聊了歌手名），需要输入歌手名
                                  回复要求：回复需要自然拟人，如果成功回复 "正在播放xxx，请您欣赏" 类似的话；如果失败按照报错进行解释性回复""")
def search_song_then_play(song_name: str, singer_name: str = None) -> str:
    """根据歌曲名称搜索歌曲并直接播放"""
    logger.info(f"搜索并播放歌曲: '{song_name}'")
    
    try:
        # 步骤1：搜索歌曲ID
        logger.info(f"第一步：搜索歌曲ID: '{song_name}'")
        encoded_song_name = urllib.parse.quote(song_name)
        search_url = f"https://api.vkeys.cn/music/tencent/search/song?keyword={encoded_song_name}"
        logger.info(f"正在搜索 URL: {search_url}")
        
        search_response = requests.get(search_url, timeout=15)
        search_response.raise_for_status()
        search_data = search_response.json()

        song_list = search_data.get('data', [])['list']
        
        if not (isinstance(song_list, list) and song_list):
            logger.warning(f"未找到歌曲: '{song_name}'")
            return f"未找到歌曲: '{song_name}'"
        
        # 获取匹配歌曲的信息
        for song in song_list:
            found_song_name = song.get('title')
            singer = song.get('singer')
            if singer_name and singer_name in singer:
                first_song = song
                break
        else:
            first_song = song_list[0]
        song_id = first_song.get('songID')
        song_mid = first_song.get('songMID')
        found_song_name = first_song.get('title')
        singer = first_song.get('singer')
        
        logger.info(f"找到歌曲: '{found_song_name}' by {singer}, ID: {song_id}, MID: {song_mid}")
        
        # 步骤2：获取播放链接并播放
        logger.info(f"第二步：获取歌曲链接并播放，MID: '{song_mid}'")
        get_url_api = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={song_mid}"
        # get_url_api = f"https://api.vkeys.cn/music/tencent/song/link?mid={song_mid}"
        logger.info(f"正在获取播放链接 URL: {get_url_api}")

        url_response = requests.get(get_url_api, timeout=15)
        # logger.info(f"获取播放链接响应状态码: {url_response.status_code} {url_response.text}")
        url_response.raise_for_status()
        url_data = url_response.json()

        data = url_data.get('data', {})
        final_song_name = data.get('song')
        song_url = data.get('url')

        if not song_url:
            logger.error(f"未能为歌曲 '{found_song_name}' 获取到有效的播放链接")
            return f"错误：未能从API获取到歌曲 '{found_song_name}' 的有效播放链接"
        
        logger.info(f"成功获取歌曲 '{final_song_name}' 的播放链接")
        
        # 播放歌曲
        try:
            audio_player.play(song_url)
            return f"正在播放歌曲 '{final_song_name}'，歌手：{singer}"
        except Exception as e:
            logger.error(f"无法播放歌曲 '{final_song_name}': {e}", exc_info=True)
            return f"已找到歌曲 '{final_song_name}'，但播放失败: {e}"

    except Exception as e:
        logger.error(f"搜索并播放歌曲时发生错误: {e}", exc_info=True)
        return f"错误：执行过程中发生网络或解析错误: {e}"

# 百度千帆 AI 搜索 API 配置
API_KEY = "bce-v3/ALTAK-rTSowOKEosFuKCKBvu6Rq/8bcca13ea79cc98570ca9ea40c5e8e70a4aacc87"
BAIDU_API_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"

def call_baidu_ai_search(search_query: str):
    """
    调用百度千帆 AI 搜索 API。
    :param search_query: 搜索查询词 (例如: "窗外的麻雀 歌名")
    :return: (dict) 成功时返回 API 响应的 JSON 字典, (str) 失败时返回错误信息
    """
    headers = {
        'Authorization': f'Bearer {API_KEY}',
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
        response = requests.post(BAIDU_API_URL, headers=headers, json=data)
        
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

def parse_song_from_title( title: str) -> str:
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

@tool(name="lyrics_to_song_name", description="""用户输入歌词内容，想要查找对应的歌曲名时使用此工具。
                                  输入：歌词内容
                                  回复要求：回复需要自然拟人，如果成功回复 "这首歌的歌名是xxx，请您欣赏" 类似的话；如果失败按照报错进行解释性回复""")
def lyrics_to_song_name(lyrics: str) -> str:
    """
    根据歌词内容搜索歌曲名称
    """
    logger.info(f"根据歌词搜索歌曲名: '{lyrics}'")
    
    try:
        # 构建搜索关键词
        search_keyword = f"{lyrics} 歌名"
        
        # 调用百度AI搜索
        response_json, error_msg = call_baidu_ai_search(search_keyword)
        
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

@tool(name="get_songs_by_singer", description="""根据歌手名搜索其歌曲列表，根据列表结果让用户选择想听的歌曲
                                  输入：歌手名
                                  回复要求：回复需要自然拟人，如果成功回复 "歌手xxx的歌曲列表有..." 类似的话；如果失败按照报错进行解释性回复""")
def get_songs_by_singer(singer_name: str) -> str:
    """根据歌手ID搜索其歌曲列表并让用户选择想听的歌曲"""
    logger.info(f"获取歌手 {singer_name} 的歌曲列表")
    
    try:
        # song_list_url = f"https://api.vkeys.cn/v2/music/tencent/singer/songlist?mid={singer_mid}"
        song_list_url = f"https://api.vkeys.cn/music/tencent/search/song?keyword={singer_name}"
        logger.info(f"正在获取歌手歌曲列表 URL: {song_list_url}")
        
        song_list_response = requests.get(song_list_url, timeout=15)
        song_list_response.raise_for_status()
        song_list_data = song_list_response.json()

        song_list = song_list_data.get('data', [])['list']
        
        if isinstance(song_list, list) and song_list:
            # 获取歌手名称
            singer_name = song_list[0].get('singer', '未知歌手')
            
            # 提取所有歌曲名称
            song_names = []
            # name_mid_map = []
            for song in song_list[:10]:  # 限制显示前10首歌曲
                song_name = song.get('title', '未知歌曲')
                # song_mid = song.get('songMID', '未知MID')
                song_names.append(f"《{song_name}》")
                # name_mid_map.append((f"{i}. {song_name}", song_mid))
            
            logger.info(f"成功获取歌手 '{singer_name}' 的歌曲列表")
            
            # 构建回复消息，询问用户想听哪首歌
            song_list_message = "\n".join(song_names)
            # id_message = "\n".join([f"{name} (MID: {mid})" for name, mid in name_mid_map])
            if len(song_list) > 10:
                song_list_message += f"\n... 还有 {len(song_list) - 10} 首歌曲未显示"
            return song_list_message
            # return f"{id_message}\n找到歌手 '{singer_name}' 的歌曲列表，请告诉我您想听哪首歌的名称：\n{song_list_message}"
        else:
            logger.warning(f"未能获取歌手 {singer_name} 的歌曲列表")
            return f"未能获取歌手 {singer_name} 的歌曲列表"

    except Exception as e:
        logger.error(f"获取歌手歌曲列表时发生错误: {e}", exc_info=True)
        return f"错误：获取歌手歌曲列表时发生网络或解析错误: {e}"

@tool(name="stop_music", description="""用户说“停止播放音乐、停止播放、停止音乐播放”等类似的话一定调用此工具
                                  回复要求：回复需要自然拟人，如果成功回复 "音乐播放已停止，您还有什么需要帮助的吗" 类似的话；如果失败按照报错进行解释性回复""")
def stop_music() -> str:
    """停止播放音乐"""
    audio_player.safe_stop()
    return "音乐播放已停止"

if __name__ == "__main__":
    logger.info("启动音乐播放器服务 (Music Player Server) ...")
    # run(transport="stdio")