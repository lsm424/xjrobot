from tools import tool
@tool(name='robot_action', description='''模拟机器人动作功能，用于执行指定的动作。
                                  回复要求：回复需要自然拟人，如果成功 执行动作指令，返回执行结果；如果失败按照报错进行解释性回复''')
def robot_action() -> str:
    return '模拟机器人动作功能，用于执行指定的动作。'
