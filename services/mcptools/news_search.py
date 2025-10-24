import time
import json
import requests
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
        return '''1.用户输入：'搜索xxx新闻'或者'xxx的新闻'或者'xxx新闻'（xxx为关键词）
2.用户输入：'最新的新闻'或者'最近有什么新闻'（不指定关键词时，搜索热门新闻）
根据工具调用返回的结果综合回复，简单整理后回复用户，说一条新闻即可'''
    
    # 添加请求头，模拟浏览器
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Connection': 'keep-alive'
    }
    
    # 必应搜索前缀
    BING_SEARCH_PREFIX = 'https://cn.bing.com/search?q='
    
    @tool(description="根据关键词搜索最新新闻，返回新闻列表，包含标题、来源、时间和摘要")
    def search_news(keyword: str = Field(..., description="搜索关键词，不指定时搜索热门新闻")) -> str:
        """根据关键词搜索最新新闻"""
        logger.info(f"搜索新闻关键词: '{keyword}'")
        
        try:
            # 记录总耗时开始
            total_start_time = time.time()
            
            # 记录搜索耗时开始
            search_start_time = time.time()
            
            # 构建搜索URL
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"{NewsSearchTool.BING_SEARCH_PREFIX}{encoded_keyword}"
            logger.info(f"正在搜索 URL: {search_url}")
            
            # 发送请求获取搜索结果
            response = requests.get(search_url, headers=NewsSearchTool.HEADERS, timeout=30)
            response.raise_for_status()
            
            # 记录搜索耗时结束
            search_end_time = time.time()
            search_time = int((search_end_time - search_start_time) * 1000)  # 转换为毫秒
            
            # 解析搜索结果
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取新闻结果
            news_list = []
            # 增加调试输出
            logger.info(f"响应状态码: {response.status_code}")
            logger.info(f"响应内容长度: {len(response.text)} 字符")
            
            # 尝试多种选择器策略以适应必应搜索的实际HTML结构
            # 策略1: 查找新闻特定的容器
            result_containers = soup.select('div.news-card, div.news-item, div.b_ans, div.b_algo')
            
            # 策略2: 如果策略1失败，查找所有包含链接的结果项
            if not result_containers:
                result_containers = soup.find_all(['div', 'li'], class_=re.compile(r'news|ans|algo|result', re.I))
                logger.info(f"备用选择器找到 {len(result_containers)} 个容器")
            
            # 策略3: 如果仍未找到，查找所有带有href属性的a标签的父容器
            if not result_containers:
                link_elements = soup.find_all('a', href=re.compile(r'^http'))
                result_containers = list(set([link.parent for link in link_elements]))
                logger.info(f"链接父容器选择器找到 {len(result_containers)} 个容器")
                
            # 限制最多返回10条新闻
            count = 0
            seen_links = set()  # 用于去重
            
            for container in result_containers:
                if count >= 10:
                    break
                
                try:
                    # 尝试不同的方式获取链接和标题
                    link_element = container.find('a', href=re.compile(r'^http'))
                    if not link_element:
                        continue
                    
                    link = link_element.get('href')
                    if not link or link in seen_links:
                        continue
                    
                    title = link_element.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    # 获取摘要 - 尝试多种方式
                    abstract = ''
                    # 方式1: 查找p标签
                    abstract_element = container.find('p')
                    # 方式2: 查找特定class的span标签
                    if not abstract_element:
                        abstract_element = container.find('span', class_=re.compile(r'abstract|snippet|desc', re.I))
                    # 方式3: 查找div标签中的文本
                    if not abstract_element:
                        abstract_elements = container.find_all('div', recursive=False)
                        if len(abstract_elements) > 1:
                            # 尝试第二个div作为摘要
                            abstract = abstract_elements[1].get_text(strip=True)[:200]
                    
                    if abstract_element:
                        abstract = abstract_element.get_text(strip=True)[:200]  # 限制摘要长度
                    
                    # 方式1: 查找cite标签
                    source_element = container.find('cite')
                    # 方式2: 查找特定class的span标签
                    if not source_element:
                        source_element = container.find('span', class_=re.compile(r'source|site', re.I))
                    # 构建新闻条目
                    news_item = {
                        'id': count + 1,
                        'title': f"{title}",
                        'abstract': abstract
                    }
                    
                    news_list.append(news_item)
                    seen_links.add(link)
                    count += 1
                except Exception as e:
                    logger.error(f"解析单个新闻项时出错：{e}")
                    continue
            
            # 格式化返回结果，便于用户阅读
            formatted_news = []
            for item in news_list:
                formatted_news.append(f"标题：{item['title']}")
                if item['abstract']:
                    formatted_news.append(f"摘要：{item['abstract']}")
                formatted_news.append("---")
            
            if formatted_news:
                return "搜索到以下新闻：\n" + "\n".join(formatted_news[:-1])  # 去掉最后一个分隔符
            else:
                return "未找到相关新闻"
                
        except Exception as e:
            logger.error(f"搜索新闻时发生错误：{e}", exc_info=True)
            return f"错误：搜索新闻时发生网络或解析错误: {e}"

if __name__ == "__main__":
    logger.info("新闻搜索工具 (News Search Tool) ...")
    # 可以在这里添加测试代码
    # news_tool = NewsSearchTool()
    # print(news_tool.search_news("最新科技新闻"))