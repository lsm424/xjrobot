from openai import OpenAI
import base64

# 初始化OpenAI客户端，使用现有的base_url
client = OpenAI(
    base_url="http://47.108.93.204:11435/v1",
    api_key="ollama"
)

# 辅助函数：将图像文件转换为base64编码
def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def test_qwen3vl_vision():
    """测试qwen3vl模型的图像理解功能"""
    print("\n=== 测试qwen3vl图像理解功能 ===")
    try:
        # 读取测试图像文件并转换为base64
        base64_image = image_to_base64("test.jpg")
        
        response = client.chat.completions.create(
            model="qwen3-vl:8b",
            messages=[
                {"role": "system", "content": "你是一个有帮助的助手，擅长理解图像内容。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "/no_think\n请描述这张图片的内容。"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.7
        )
        # print(response.choices[0].message)
        print(f"图像理解结果: {response.choices[0].message.content}")
        print("图像理解测试成功！")
    except Exception as e:
        print(f"图像理解测试失败: {e}")


if __name__ == "__main__":
    # 运行所有测试
    # test_qwen3vl_text()
    test_qwen3vl_vision()
    # test_qwen3vl_stream()
