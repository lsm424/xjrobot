from tools import tool
import cv2
import base64
from openai import OpenAI

# 初始化OpenAI客户端
client = OpenAI(
    base_url="http://47.108.93.204:11435/v1",
    api_key="ollama"
)

# 辅助函数：将图像文件转换为base64编码
def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# 辅助函数：拍摄照片
def capture_photo():
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        return None
    
    # 拍摄一张照片
    ret, frame = cap.read()
    
    # 释放摄像头
    cap.release()
    
    if not ret:
        return None
    
    # 保存照片
    photo_path = "captured_photo.jpg"
    cv2.imwrite(photo_path, frame)
    
    return photo_path

@tool(name='robot_vision', description='''机器人视觉功能，用于调取摄像头拍摄图片，并返回对图片的描述。
                                  回复要求：回复需要根据用户的提问及视觉描述，自然拟人；如果失败按照报错进行解释性回复''')
def robot_vision() -> str:
    """机器人视觉功能，调取摄像头拍摄图片并返回描述"""
    try:
        # 拍摄照片
        photo_path = capture_photo()
        
        if photo_path is None:
            return "抱歉，无法打开摄像头或拍摄照片失败。"
        
        # 将图像转换为base64
        base64_image = image_to_base64(photo_path)
        
        # 调用qwen3vl模型进行图像描述
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
        
        # 返回图像描述结果
        return response.choices[0].message.content
    
    except Exception as e:
        return f"抱歉，视觉功能出现错误：{str(e)}"
