import time
import json
import requests
import random
from bs4 import BeautifulSoup
import re
import urllib.parse
from datetime import datetime
from langchain.tools import tool
from common import logger
from .base import ToolBase
from typing import Literal
from pydantic import Field

class NewsSearchTool(ToolBase):
    def __init__(self):
        super().__init__(name='新闻搜索')
    
    def usage(self) -> Literal[str|None]:
        return '''新闻搜索工具使用指南：
        # 功能说明
        该工具用于搜索新闻内容和获取最新新闻列表。调用工具后，请根据返回结果总结回答用户问题。
        # 调用场景与对应方法
        1. 当用户询问特定主题的新闻时，例如：
           - "搜索科技新闻"
           - "体育的新闻"
           - "人工智能新闻"
           请使用：search_news_by_keyword_and_abstract(关键词)  
        2. 当用户仅想了解最新新闻概览时，例如：
           - "最新的新闻"
           - "最近有什么新闻"
           - "新闻摘要"
           请使用：get_paper_news()   
        3. 当用户询问特定事物的最新情况时，例如：
           - "华为最近怎么样"
           - "苹果的最新动态"
           - "xxx在哪天？"，提取关键词为“xxx 时间”
           请使用：search_news_by_keyword_and_abstract(查询词)
        4. 当历史聊天和搜索记录无法解答用户的问题时，例如：
           - 用户紧接着前面的内容询问，但是你回答不出来，或者历史搜索没有相关内容
           请使用：search_news_by_keyword_and_abstract(用户的问题)
        # 输出要求
        - 调用工具后，请将搜索结果总结为简洁回答
        - 回答控制在100字以内
        - 必须包含明确的回复内容，不要仅返回工具结果
        '''
    
    # 添加请求头，模拟浏览器
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Connection': 'keep-alive'
    }
    
    # 必应搜索前缀
    BING_SEARCH_PREFIX = 'https://cn.bing.com/search?q='
    
    def clean_text(text):
        """清理文本，去除URL链接和Unicode符号，保留主要中文文本"""
        # 去除URL链接
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        # 去除Unicode符号，保留中文、英文、数字和常用标点
        text = re.sub(r'[\u0000-\u001f\u007f-\u009f\u2000-\u206f\u2100-\u214f\u2460-\u24ff\u3000-\u303f]+', '', text)
        # 去除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        # 去除多余的标点符号
        text = re.sub(r'([,，.。!?！？;:：；""'"'"'])\1+', '\1', text)
        return text.strip()
    
    @tool(description="【搜索特定主题新闻】根据关键词搜索相关最新新闻。当用户询问特定主题、人物或事件的新闻时使用此工具。要对返回内容进行总结，控制在100字以内。")
    def search_news_by_keyword_and_abstract(keyword: str = Field(..., description="搜索关键词")) -> str:
        """根据关键词搜索最新新闻并总结"""
        logger.info(f"搜索新闻关键词: '{keyword}'")
        
        try:
            # 构建搜索URL
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"{NewsSearchTool.BING_SEARCH_PREFIX}{encoded_keyword}"
            logger.info(f"正在搜索 URL: {search_url}")
            
            # 发送请求获取搜索结果
            response = requests.get(search_url, headers=NewsSearchTool.HEADERS, timeout=30)
            response.raise_for_status()
            # 解析搜索结果
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取新闻结果
            news_list = []
            # 增加调试输出
            logger.info(f"响应状态码: {response.status_code}")
            logger.info(f"响应内容长度: {len(response.text)} 字符")
            
            # 优化选择器策略，优先使用.b_algo容器
            # 策略1: 优先查找.b_algo容器，这是必应搜索结果的主要容器
            result_containers = list(soup.select('div.b_algo'))  # 转换为列表以便后续操作
            logger.info(f"主选择器找到 {len(result_containers)} 个.b_algo容器")
            
            # 策略2: 如果策略1找到的容器较少，补充其他可能的容器
            # if len(result_containers) < 5:
            additional_containers = soup.select('div.b_ans, li.b_algo')
            for container in additional_containers:
                if container not in result_containers:
                    result_containers.append(container)
            logger.info(f"补充后共找到 {len(result_containers)} 个容器")
            
            # 策略3: 如果仍未找到足够的容器，使用更通用的选择器
            # if len(result_containers) < 3:
            result_containers = list(soup.find_all(['div', 'li'], class_=re.compile(r'news|ans|algo|result', re.I)))
            logger.info(f"备用选择器找到 {len(result_containers)} 个容器")
            
            # 限制最多返回10条新闻
            seen_links = set()  # 用于去重
            seen_titles = set()  # 用于去重标题
            
            for container in result_containers:
                
                try:
                    # 优化标题提取逻辑
                    # 1. 优先查找容器内的h2标签中的a链接（必应搜索结果的标准格式）
                    h2_element = container.find('h2')
                    if h2_element:
                        link_element = h2_element.find('a', href=re.compile(r'^http'))
                    else:
                        # 2. 如果没有h2标签，查找容器内的其他a链接
                        link_element = container.find('a', href=re.compile(r'^http'))
                    
                    if not link_element:
                        continue
                    
                    link = link_element.get('href')
                    if not link or link in seen_links:
                        continue
                    
                    # 提取并清理标题
                    title = link_element.get_text(strip=True)
                    # 清理标题文本
                    cleaned_title = NewsSearchTool.clean_text(title)
                    
                    if not cleaned_title or len(cleaned_title) < 5 or cleaned_title in seen_titles:
                        continue
                    
                    # 获取摘要 - 优化提取逻辑
                    abstract = ''
                    
                    # 方式1: 查找.b_caption类（必应搜索结果的标准摘要容器）
                    caption_element = container.find('div', class_='b_caption')
                    if caption_element:
                        # 在摘要容器中查找p标签或直接获取文本
                        p_element = caption_element.find('p')
                        if p_element:
                            abstract = p_element.get_text(strip=True)[:200]
                        else:
                            abstract = caption_element.get_text(strip=True)[:200]
                    else:
                        # 方式2: 查找p标签
                        abstract_element = container.find('p')
                        if abstract_element:
                            abstract = abstract_element.get_text(strip=True)[:200]
                        # 方式3: 查找特定class的div标签
                        elif not abstract:
                            abstract_elements = container.find_all('div', recursive=False)
                            for div in abstract_elements:
                                # 避免使用包含链接或脚本的div
                                if not div.find('a') and not div.find('script'):
                                    div_text = div.get_text(strip=True)
                                    if len(div_text) > 20 and len(div_text) < 500:  # 合理长度的文本更可能是摘要
                                        abstract = div_text[:200]
                                        break
                    
                    # 清理摘要文本
                    cleaned_abstract = NewsSearchTool.clean_text(abstract)
                    
                    # 构建新闻条目
                    news_item = {
                        'title': cleaned_title,
                        'abstract': cleaned_abstract
                    }
                    
                    news_list.append(news_item)
                    seen_links.add(link)
                    seen_titles.add(cleaned_title)
                except Exception as e:
                    logger.error(f"解析单个新闻项时出错：{e}")
                    continue
            
            # 格式化返回结果，便于用户阅读
            formatted_news = []
            for item in news_list:
                formatted_news.append(f"·标题：{item['title']}")
                if item['abstract']:
                    formatted_news.append(f"摘要：{item['abstract']}")
                # formatted_news.append("\n")
            
            if formatted_news:
                return "请你根据用户问题，总结概括一下后面的新闻内容，今天日期是" + datetime.now().strftime("%Y-%m-%d") + "\n".join(formatted_news[:-1])  # 去掉最后一个分隔符
            else:
                return "未找到相关新闻"
                
        except Exception as e:
            logger.error(f"搜索新闻时发生错误：{e}", exc_info=True)
            return f"错误：搜索新闻时发生网络或解析错误: {e}"
    
    @tool(description="【获取最新新闻概览】获取最新的综合新闻列表。当用户仅想了解当前有哪些热点新闻时使用此工具。要对返回内容进行总结，总结为用户可理解的内容。")
    def get_paper_news() -> str:
        """获取最新新闻列表"""
        logger.info("获取最新新闻")
        
        try:
            # 澎湃新闻的API接口
            api_url = "https://newsnow.busiyi.world/api/s?id=thepaper"
            headers = {"User-Agent": "Mozilla/5.0"}
            
            logger.info(f"正在获取新闻，API URL: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if "items" in data and data["items"]:
                # 格式化新闻列表
                formatted_news = []
                for idx, news_item in enumerate(data["items"][:10], 1):  # 只取前10条新闻
                    formatted_news.append(f"{idx}. 标题：{news_item.get('title', '未知标题')}")
                    formatted_news.append("")
                
                # # 随机选择一条作为推荐
                # random_news = random.choice(data["items"])
                # formatted_news.append(f"推荐阅读：{random_news.get('title', '未知标题')}")
                
                return "请你根据用户问题，总结概括一下后面的新闻列表，今天日期是" + datetime.now().strftime("%Y-%m-%d") + "\n" + "\n".join(formatted_news)
            else:
                return "未获取到新闻数据"
                
        except Exception as e:
            logger.error(f"获取新闻失败: {e}", exc_info=True)
            return f"错误：获取新闻时发生网络或解析错误: {e}"
    
    # # 保留原有的search_news方法以便兼容现有调用
    # @tool(description="根据关键词搜索最新新闻，返回新闻列表，包含标题、来源、时间和摘要")
    # def search_news(keyword: str = Field(..., description="搜索关键词，不指定时搜索热门新闻")) -> str:
    #     """根据关键词搜索最新新闻"""
    #     # 如果没有指定关键词，默认调用澎湃新闻工具
    #     if not keyword or keyword in ['最新的新闻', '最近有什么新闻', '热门新闻', '新闻', '澎湃新闻']:
    #         return NewsSearchTool.get_paper_news()
    #     # 否则使用关键词搜索
    #     return NewsSearchTool.search_news_by_keyword(keyword)

if __name__ == "__main__":
    logger.info("新闻搜索工具 (News Search Tool) ...")
    # 可以在这里添加测试代码
    # news_tool = NewsSearchTool()
    # print(news_tool.search_news("最新科技新闻"))

