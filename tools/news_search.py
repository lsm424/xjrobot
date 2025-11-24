import json
import requests
import re
from tools import tool
from logger import logger

# 全局变量和常量定义
    
# 添加请求头，模拟浏览器
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Connection': 'keep-alive'
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
]

# 必应搜索前缀
BING_SEARCH_PREFIX = 'https://cn.bing.com/search?q='
# BING_SEARCH_PREFIX = 'https://so.douyin.com/s?search_entrance=aweme&enter_method=normal_search&keyword='

# 百度千帆AppBuilder API Key
QIANFAN_API_KEY = "bce-v3/ALTAK-rTSowOKEosFuKCKBvu6Rq/8bcca13ea79cc98570ca9ea40c5e8e70a4aacc87"

def clean_text(text):
    """清理文本，去除URL链接和Unicode符号，保留主要中文文本"""
    # 去除URL链接
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    # 去除Unicode符号，保留中文、英文、数字和常用标点
    text = re.sub(r'[\u0000-\u001f\u007f-\u009f\u2000-\u206f\u2100-\u214f\u2460-\u24ff\u3000-\u303f]+', '', text)
    # 去除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    # 去除多余的标点符号
    text = re.sub(r'([,，.。!?！？;:：；""\'\'\'])\1+', '\1', text)
    return text.strip()
    
def qianfan_ai_search(api_key, keyword, top_k=10, time_filter="month", target_sites=None):
    """
    调用百度千帆AppBuilder AI搜索接口，根据关键词返回含title和content的结果列表
    """
    # 1. 接口基础配置
    api_url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # 2. 构造请求体参数
    request_body = {
        "messages": [{"role": "user", "content": keyword}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": min(top_k, 50)}],
        "search_recency_filter": time_filter
    }

    # 3. 若指定目标站点，添加site过滤
    if target_sites and isinstance(target_sites, list) and len(target_sites) <= 20:
        request_body["search_filter"] = {
            "match": {"site": target_sites}
        }

    try:
        # 4. 发送POST请求
        response = requests.post(
            url=api_url,
            headers=headers,
            data=json.dumps(request_body),
            timeout=15
        )
        response.raise_for_status()

        # 5. 解析响应结果
        response_data = response.json()
        logger.info(f"百度千帆API响应: {response_data}")
        references = response_data.get("references", [])

        # 6. 过滤结果：仅保留title和content，排除空值
        result_list = []
        for ref in references:
            title = ref.get("title", "无标题").strip()
            content = ref.get("content", "无摘要").strip()
            # 仅添加非空结果
            if title != "无标题" or content != "无摘要":
                result_list.append({"title": title, "content": content})

        return result_list

    # 7. 异常处理
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP请求错误：{str(e)}"
        if response.text:
            try:
                err_data = json.loads(response.text)
                error_msg += f"（错误码：{err_data.get('code')}，详情：{err_data.get('message')}）"
            except:
                pass
        logger.error(error_msg)
        return []
    except requests.exceptions.ConnectionError:
        logger.error("错误：网络连接失败，请检查网络状态")
        return []
    except requests.exceptions.Timeout:
        logger.error("错误：请求超时，请稍后重试")
        return []
    except Exception as e:
        logger.error(f"未知错误：{str(e)}")
        return []
    
@tool(name="search_news_by_keyword_and_abstract", description="【搜索特定主题新闻】根据关键词搜索相关最新新闻。当用户询问特定主题、人物或事件的新闻时使用此工具。拿到结果之后需要对新闻进行精简总结，**100字以内**")
def search_news_by_keyword_and_abstract(keyword=None):
    """
    根据关键词搜索最新新闻并总结
    
    Args:
        keyword: 搜索关键词
    
    Returns:
        str: 新闻搜索结果摘要
    """
    logger.info(f"搜索新闻关键词: '{keyword}'")
    
    try:
        # 使用百度千帆AppBuilder AI搜索接口
        search_results = qianfan_ai_search(
            api_key=QIANFAN_API_KEY,
            keyword=keyword.strip() if keyword else "",
            top_k=5,  # 返回10条结果
            time_filter="month"  # 仅搜索近30天的内容
        )
        
        # 格式化返回结果，便于用户阅读
        formatted_news = []
        for item in search_results:
            formatted_news.append(f"·标题：{item['title']}")
            if item['content']:
                formatted_news.append(f"摘要：{item['content']}")
        
        if formatted_news:
            return "\n".join(formatted_news[:10])  # 限制返回数量
        else:
            return "未找到相关新闻"
            
    except Exception as e:
        logger.error(f"搜索新闻时发生错误：{e}", exc_info=True)
        return f"错误：搜索新闻时发生网络或解析错误: {e}"
    
@tool(name="get_paper_news", description="【获取最新新闻概览】获取最新的综合新闻列表。当用户仅想了解当前有哪些热点新闻时使用此工具。拿到结果之后需要对新闻进行精简总结，100字以内")
def get_paper_news():
    """
    获取最新新闻列表
    
    Returns:
        str: 最新新闻列表摘要
    """
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
            
            return "\n".join(formatted_news)
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
    # 测试代码示例
    print("测试搜索新闻功能:")
    result = search_news_by_keyword_and_abstract("科技新闻")
    print(result)
    
    print("\n测试获取最新新闻:")
    latest_news = get_paper_news()
    print(latest_news)

