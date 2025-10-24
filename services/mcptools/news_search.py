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
        return '''1.用户输入：'搜索xxx新闻'或者'xxx的新闻'或者'xxx新闻'（xxx为关键词）- 使用关键词搜索工具
2.用户输入：'最新的新闻'或者'最近有什么新闻'或者'新闻' - 使用最新新闻工具获取最新新闻
3.用户输入：一个可能需要联网查询解决的问题，例如‘xxx最近怎么样’或者‘xxx的最新动态’或者‘xxx的情况’（xxx为人名或者其他名词）- 使用关键词搜索工具
根据工具调用返回的新闻列表结果综合回复，简单整理后回复用户，不要过长，控制在100字内'''
    
    # 添加请求头，模拟浏览器
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Connection': 'keep-alive'
    }
    
    # 必应搜索前缀
    BING_SEARCH_PREFIX = 'https://cn.bing.com/search?q='
    
    @tool(description="根据关键词搜索最新资讯，返回新闻列表，包含标题、来源和摘要。当用户提及具体某个事情或特定关键词时使用此工具。")
    def search_news_by_keyword(keyword: str = Field(..., description="搜索关键词。你需要对回答进行归纳总结，控制在100字内")) -> str:
        """根据关键词搜索最新新闻"""
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
    
    @tool(description="获取最新新闻列表。当用户只是想听听新闻，看看最新有什么新闻时使用此工具。你需要对回答进行归纳总结，控制在100字内")
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
                
                # 随机选择一条作为推荐
                random_news = random.choice(data["items"])
                formatted_news.append(f"推荐阅读：{random_news.get('title', '未知标题')}")
                
                return "总结概括一下后面的新闻列表\n" + "\n".join(formatted_news)
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