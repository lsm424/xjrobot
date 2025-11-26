import requests
from bs4 import BeautifulSoup
from tools import tool
from logger import logger

# 天气代码 https://dev.qweather.com/docs/resource/icons/#weather-icons
WEATHER_CODE_MAP = {
    "100": "晴",
    "101": "多云",
    "102": "少云",
    "103": "晴间多云",
    "104": "阴",
    "150": "晴",
    "151": "多云",
    "152": "少云",
    "153": "晴间多云",
    "300": "阵雨",
    "301": "强阵雨",
    "302": "雷阵雨",
    "303": "强雷阵雨",
    "304": "雷阵雨伴有冰雹",
    "305": "小雨",
    "306": "中雨",
    "307": "大雨",
    "308": "极端降雨",
    "309": "毛毛雨/细雨",
    "310": "暴雨",
    "311": "大暴雨",
    "312": "特大暴雨",
    "313": "冻雨",
    "314": "小到中雨",
    "315": "中到大雨",
    "316": "大到暴雨",
    "317": "暴雨到大暴雨",
    "318": "大暴雨到特大暴雨",
    "350": "阵雨",
    "351": "强阵雨",
    "399": "雨",
    "400": "小雪",
    "401": "中雪",
    "402": "大雪",
    "403": "暴雪",
    "404": "雨夹雪",
    "405": "雨雪天气",
    "406": "阵雨夹雪",
    "407": "阵雪",
    "408": "小到中雪",
    "409": "中到大雪",
    "410": "大到暴雪",
    "456": "阵雨夹雪",
    "457": "阵雪",
    "499": "雪",
    "500": "薄雾",
    "501": "雾",
    "502": "霾",
    "503": "扬沙",
    "504": "浮尘",
    "507": "沙尘暴",
    "508": "强沙尘暴",
    "509": "浓雾",
    "510": "强浓雾",
    "511": "中度霾",
    "512": "重度霾",
    "513": "严重霾",
    "514": "大雾",
    "515": "特强浓雾",
    "900": "热",
    "901": "冷",
    "999": "未知",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    )
}

def fetch_city_info(location, api_key, api_host):
    """
    获取城市信息
    """
    url = f"https://{api_host}/geo/v2/city/lookup?key={api_key}&location={location}&lang=zh"
    response = requests.get(url, headers=HEADERS).json()
    if response.get("error") is not None:
        logger.error(
            f"获取天气失败，原因：{response.get('error', {}).get('detail')}"
        )
        return None
    return response.get("location", [])[0] if response.get("location") else None

def fetch_weather_page(url):
    """
    获取天气页面
    """
    response = requests.get(url, headers=HEADERS)
    return BeautifulSoup(response.text, "html.parser") if response.ok else None

def parse_weather_info(soup):
    """
    解析天气信息
    """
    city_name = soup.select_one("h1.c-submenu__location").get_text(strip=True)

    current_abstract = soup.select_one(".c-city-weather-current .current-abstract")
    current_abstract = (
        current_abstract.get_text(strip=True) if current_abstract else "未知"
    )

    current_basic = {}
    for item in soup.select(
        ".c-city-weather-current .current-basic .current-basic___item"
    ):
        parts = item.get_text(strip=True, separator=" ").split(" ")
        if len(parts) == 2:
            key, value = parts[1], parts[0]
            current_basic[key] = value

    temps_list = []
    for row in soup.select(".city-forecast-tabs__row")[:7]:  # 取前7天的数据
        date = row.select_one(".date-bg .date").get_text(strip=True)
        weather_code = (
            row.select_one(".date-bg .icon")["src"].split("/")[-1].split(".")[0]
        )
        weather = WEATHER_CODE_MAP.get(weather_code, "未知")
        temps = [span.get_text(strip=True) for span in row.select(".tmp-cont .temp")]
        high_temp, low_temp = (temps[0], temps[-1]) if len(temps) >= 2 else (None, None)
        temps_list.append((date, weather, high_temp, low_temp))

    return city_name, current_abstract, current_basic, temps_list
    
@tool(name="get_weather", description="""获取指定地点的天气信息，如果不提供地点则使用默认城市长沙
                                  输入：地点名，例如杭州/长沙
                                  回复要求：拿到天气结果之后需要进行总结才能回复，需要精简回答，减少生成时间""")
def get_weather(location=None):
    """
    获取指定地点的天气信息
    
    Args:
        location: 地点名，例如杭州。可选参数，如果不提供则使用默认城市长沙
    
    Returns:
        str: 天气信息的文本描述，包含当前天气和未来7天预报
    """
    # 固定API配置
    api_host = "nn5khvawk9.re.qweatherapi.com"
    api_key = "de51f3690e764d3d859312e4e53230b1"
    default_location = "长沙"
    
    logger.info(f"获取天气信息，地点: '{location or default_location}'")
    
    try:
        # 优先使用用户提供的location参数，否则使用默认位置
        target_location = location if location else default_location
        
        # 获取城市信息
        city_info = fetch_city_info(target_location, api_key, api_host)
        if not city_info:
            return f"未找到相关的城市: {target_location}，请确认地点是否正确"
        
        # 获取天气页面
        soup = fetch_weather_page(city_info["fxLink"])
        if not soup:
            return "请求失败，无法获取天气数据"
        
        # 解析天气信息
        city_name, current_abstract, current_basic, temps_list = parse_weather_info(soup)
        
        # 构建天气报告
        weather_report = f"您查询的位置是：{city_name}\n\n当前天气: {current_abstract}\n"
        
        # 添加有效的当前天气参数
        if current_basic:
            weather_report += "详细参数：\n"
            for key, value in current_basic.items():
                if value != "0":  # 过滤无效值
                    # 替换温度符号
                    if '°' in value:
                        value = value.replace('°', '摄氏度')
                    weather_report += f"  · {key}: {value}\n"
        
        # 添加7天预报
        weather_report += "\n未来7天预报：\n"
        for date, weather, high, low in temps_list:
            # 替换温度符号
            if high and '°' in high:
                high = high.replace('°', '摄氏度')
            if low and '°' in low:
                low = low.replace('°', '摄氏度')
            weather_report += f"{date}: {weather}，气温 {low}~{high}\n"
        
        return weather_report
        
    except Exception as e:
        logger.error(f"获取天气信息时发生错误: {e}", exc_info=True)
        return f"错误：获取天气信息时发生错误: {e}"

if __name__ == "__main__":
    logger.info("启动天气查询服务 (Weather Query Server) ...")
    # 测试天气查询功能
    try:
        result = get_weather("北京")
        logger.info(f"天气查询测试结果: {result[:100]}...")
    except Exception as e:
        logger.error(f"天气查询测试失败: {e}")
