import time
from agent_framework import AgentFramework

def test_agent_framework():
    # 初始化Brain和AgentFramework
    agent = AgentFramework()
    
    print("测试1: 测试直接回答内容 (0: 格式)")
    start_time = time.time()
    # 这个问题应该直接回答，不需要工具
    user_query = "你好，今天天气怎么样？"
    print(f"用户问题: {user_query}")
    print("流式输出:")
    
    for chunk in agent.process_user_query_stream(user_query):
        print(chunk, end="", flush=True)
    
    print(f"\n\n处理时间: {time.time() - start_time:.2f} 秒\n")
    
    print("测试2: 测试需要工具的情况 (1: 格式)")
    start_time = time.time()
    # 这个问题应该触发工具调用
    user_query = "请帮我计算123456789乘以987654321的结果"
    print(f"用户问题: {user_query}")
    print("流式输出:")
    
    for chunk in agent.process_user_query_stream(user_query):
        print(chunk, end="", flush=True)
    
    print(f"\n\n处理时间: {time.time() - start_time:.2f} 秒\n")
    
    print("测试3: 测试中文TTS分段功能")
    start_time = time.time()
    # 这个问题应该产生较长的中文回答，测试TTS分段
    user_query = "请详细描述人工智能的发展历史和未来趋势"
    print(f"用户问题: {user_query}")
    print("流式输出及TTS分段:")
    
    for chunk in agent.process_user_query_stream(user_query):
        print(chunk, end="", flush=True)
    
    print(f"\n\n处理时间: {time.time() - start_time:.2f} 秒")

if __name__ == "__main__":
    test_agent_framework()