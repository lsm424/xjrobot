import logging
import requests
import webbrowser
import urllib.parse
import re
from langchain.tools import tool
from common import logger
from .base import ToolBase
from typing import Literal
from pydantic import Field
import subprocess
import threading
import queue
import time
from services.robot_state import RobotState

class FlacStreamPlayer:
    """
    在线解析 FLAC 链接，边下边播
    使用 ffmpeg 解码并播放
    """
    def __init__(self, buffer_size: int = 1024 * 64):
        self.buffer_size = buffer_size
        self.download_queue = queue.Queue(maxsize=200)  # 限制缓存大小
        self.stop_event = threading.Event()
        self.temp_file = None
        self.ffmpeg_proc = None

    def _download_worker(self):
        """后台下载线程：持续下载 FLAC 数据并写入队列"""
        try:
            with requests.get(self.url, stream=True, timeout=10) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=self.buffer_size):
                    if self.stop_event.is_set():
                        break
                    if chunk:
                        self.download_queue.put(chunk)
        except Exception as e:
            logger.error(f"下载出错: {e}")
        finally:
            # 发送结束标记
            self.download_queue.put(None)

    def _play_worker(self):
        """播放线程：从队列读取数据并直接喂给 ffplay 实现真正的边下边播"""
        ffmpeg_proc = None  # 使用局部变量存储进程引用
        try:
            # 启动 ffplay 子进程，直接从 stdin 读取 FLAC 数据流
            cmd = ['ffplay', '-nodisp', '-autoexit', '-i', '-']
            ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL
            )
            
            # 更新实例变量
            self.ffmpeg_proc = ffmpeg_proc

            # 直接将下载的数据块写入 ffplay 的 stdin，实现边下边播
            while not self.stop_event.is_set():
                try:
                    chunk = self.download_queue.get(timeout=1)
                    if chunk is None:  # 下载结束
                        break
                    if ffmpeg_proc.stdin and not self.stop_event.is_set():
                        try:
                            ffmpeg_proc.stdin.write(chunk)
                            ffmpeg_proc.stdin.flush()  # 确保数据立即发送到 ffplay
                        except BrokenPipeError:
                            logger.warning("管道已关闭，停止写入数据")
                            break
                    # print(f"已播放数据块大小: {len(chunk)}")
                except queue.Empty:
                    continue
                except Exception as e:
                    if not self.stop_event.is_set():
                        logger.error(f"播放数据块时出错: {e}")
            
            # 安全关闭 stdin，通知 ffplay 输入已结束
            try:
                if ffmpeg_proc.stdin:
                    ffmpeg_proc.stdin.close()
            except:
                pass

            # 等待 ffmpeg 结束
            try:
                if ffmpeg_proc:
                    ffmpeg_proc.wait(timeout=2)  # 添加超时避免永久阻塞
            except subprocess.TimeoutExpired:
                logger.warning("ffmpeg进程等待超时，强制终止")
                try:
                    ffmpeg_proc.terminate()
                except:
                    pass
        except Exception as e:
            logger.error(f"播放出错: {e}")
        finally:
            # 确保进程引用被清除
            self.ffmpeg_proc = None
            # 清空队列，避免下次播放时使用旧数据
            try:
                while not self.download_queue.empty():
                    self.download_queue.get_nowait()
            except:
                pass

    def play(self, flac_url: str):
        """开始边下边播（非阻塞模式）"""
        logger.info("开始边下边播 FLAC...")
        # 首先停止当前播放（如果有）
        if RobotState.is_playing_music:
            logger.info("检测到正在播放音乐，先停止当前播放")
            self.stop()
        
        # 完全重置所有状态
        self.url = flac_url
        self.stop_event.clear()  # 重置停止事件
        # 清空队列，确保没有旧数据
        try:
            while not self.download_queue.empty():
                self.download_queue.get_nowait()
        except:
            pass
        
        # 设置正在播放音乐的标志位
        RobotState.is_playing_music = True
        
        # 启动下载和播放线程
        dl_thread = threading.Thread(target=self._download_worker, daemon=True)
        play_thread = threading.Thread(target=self._play_worker, daemon=True)
        
        dl_thread.start()
        play_thread.start()
        
        # 创建一个监控线程来处理播放完成后的清理工作
        monitor_thread = threading.Thread(target=self._monitor_playback, 
                                        args=(dl_thread, play_thread), 
                                        daemon=True)
        monitor_thread.start()
        
        # 立即返回，不阻塞主线程
        logger.info("音乐开始播放，主线程继续执行其他任务")
        return
        
    def _monitor_playback(self, dl_thread, play_thread):
        """监控播放过程并在完成后清理资源"""
        try:
            # 等待下载和播放线程结束
            while not self.stop_event.is_set():
                if not dl_thread.is_alive() and self.download_queue.empty():
                    break
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"监控播放过程中出错: {e}")
        finally:
            # 确保资源被正确清理
            self.stop()
            try:
                dl_thread.join(timeout=2)
                play_thread.join(timeout=2)
            except:
                pass
            logger.info("播放结束，资源已清理")
    
    def stop(self):
        """停止播放和下载"""
        logger.info("停止播放音乐...")
        # 设置停止事件
        self.stop_event.set()
        
        # 安全终止ffmpeg进程
        if self.ffmpeg_proc:
            try:
                if self.ffmpeg_proc.poll() is None:
                    self.ffmpeg_proc.terminate()
                    # 添加超时，避免永久阻塞
                    try:
                        self.ffmpeg_proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        logger.warning("ffmpeg进程终止超时")
            except Exception as e:
                logger.error(f"终止ffmpeg进程时出错: {e}")
            finally:
                # 确保清除进程引用
                self.ffmpeg_proc = None
        
        # 清空队列，避免旧数据影响下次播放
        try:
            while not self.download_queue.empty():
                try:
                    self.download_queue.get_nowait()
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"清空队列时出错: {e}")
        
        # 清除正在播放音乐的标志位
        RobotState.is_playing_music = False
        logger.info("音乐播放已停止，资源已清理")


player = FlacStreamPlayer()
class MusicPlayerTool(ToolBase):
    def __init__(self):
        
        super().__init__(name='音乐播放器')

    def usage(self) -> Literal[str|None]:
        return '''1.用户输入：‘我想听xxx’或者’xxx‘或者’换一个xxx‘（我想听几个字可以省略，xxx为歌曲名，工具使用链路为search_song_id→get_song_url）
2.用户输入：‘我想听xxx的歌’或者‘我想听xxx’或者‘换一个xxx的歌’（我想听几个字可以省略，xxx为人名，工具使用链路为search_singer_id→get_songs_by_singer获取歌曲列表给用户选择，进入下一轮对话，下一轮对话有歌曲名回到步骤1）
3.用户输入：‘xxx有些什么歌？’（xxx为人名，回到步骤2）
4.用户输入：‘xxx的yyy‘或者’xxx yyy‘（我想听几个字可以省略，xxx为人名，yyy为歌曲名，工具使用链路为search_song_id→get_song_url）
5.用户输入：‘我想听歌词xxx的歌’或者‘xxx是什么歌’（xxx为歌词内容，工具使用链路为lyrics_to_song_name→search_song_id→get_song_url）
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
                    player.play(song_url)
                    success_message = f"操作成功，正在播放 '{song_name}'。"
                    logger.info(success_message)
                    return f"歌曲 '{song_name}' 的播放链接: {song_url}\n{success_message}"
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
                
                return f"{id_message}\n(请你一字不差的返回后面的话)找到歌手 '{singer_name}' 的歌曲列表，请告诉我您想听哪首歌的名称：\n{song_list_message}"
            else:
                logger.warning(f"未能获取歌手ID {singer_mid} 的歌曲列表")
                return f"未能获取歌手ID {singer_mid} 的歌曲列表"

        except Exception as e:
            logger.error(f"获取歌手歌曲列表时发生错误: {e}", exc_info=True)
            return f"错误：获取歌手歌曲列表时发生网络或解析错误: {e}"

    @tool(description='当在播放歌曲时，用户说“停止播放”等类似的话调用此工具')
    def stop_music() -> str:
        """停止播放音乐"""
        if not RobotState.is_playing_music:
            return "当前没有正在播放的音乐"
        player.stop()
        return "音乐播放已停止"




if __name__ == "__main__":
    logger.info("启动音乐播放器服务 (Music Player Server) ...")
    # run(transport="stdio")