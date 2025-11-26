from tools import tool
@tool(name='robot_vision', description='''模拟机器人视觉功能，用于分析图像，并返回描述性文本。
                                  回复要求：回复需要自然拟人，如果成功 分析图像，返回描述性文本；如果失败按照报错进行解释性回复''')
def robot_vision() -> str:
    return '模拟机器人视觉功能，用于分析图像，并返回描述性文本。'
