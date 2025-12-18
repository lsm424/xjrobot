import os
import io
import base64
import subprocess
from PIL import Image
from openai import OpenAI
from tools import tool

# --- 1. 全局配置 ---
VLM_CLIENT = OpenAI(
    base_url="http://47.108.93.204:11435/v1",
    api_key="ollama"
)
VLM_MODEL_NAME = "qwen3-vl:8b"

# --- 2. 辅助函数：图像处理 ---
def compress_image_to_base64(image_path, max_edge=512, quality=75):
    """
    读取图片，按最大边长等比缩放，并转换为base64
    """
    try:
        if not os.path.exists(image_path):
            print(f"错误: 找不到文件 {image_path}")
            return None
            
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            width, height = img.size
            if max(width, height) > max_edge:
                scale = max_edge / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
            
    except Exception as e:
        print(f"图片压缩处理出错: {e}")
        return None

# --- 3. 辅助函数：调用外部脚本采集图像 (已根据你的ROS脚本修改) ---
def call_ros_bridge_to_get_image():
    """
    调用根目录下的 get_ros_image.py 获取图像
    注意：ROS脚本硬编码了保存文件名为 captured_image.jpg
    """
    # === 路径计算 ===
    # tools/mcp_tools.py -> tools/ -> project_root/
    current_file_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(current_file_path))
    
    script_path = os.path.join(project_root, "get_ros_image.py")
    # ROS脚本里写死了叫 captured_image.jpg，所以我们也必须读这个名字
    expected_image_path = os.path.join(project_root, "captured_image.jpg")

    if not os.path.exists(script_path):
        print(f"严重错误: 无法找到脚本 {script_path}")
        return None

    # === 防脏读：先删除旧图片 ===
    if os.path.exists(expected_image_path):
        try:
            os.remove(expected_image_path)
        except OSError:
            pass

    # === 进程调用逻辑 ===
    system_python = "/usr/bin/python3" 
    
    clean_env = {
        "PATH": "/opt/ros/noetic/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "ROS_MASTER_URI": os.environ.get("ROS_MASTER_URI", "http://localhost:11311"),
        "ROS_IP": os.environ.get("ROS_IP", "127.0.0.1"),
        "PYTHONPATH": "/opt/ros/noetic/lib/python3/dist-packages",
        "HOME": os.environ.get("HOME", ""),
        "LD_LIBRARY_PATH": "/opt/ros/noetic/lib"
    }

    try:
        # print(f"DEBUG: 在 {project_root} 目录下运行 ROS 采集脚本...")
        
        # 关键修改：
        # 1. args 里只传脚本路径，不传输出路径（因为ROS脚本不支持参数）
        # 2. cwd=project_root，确保脚本运行时的"当前目录"是项目根目录，这样 captured_image.jpg 才会生成在正确位置
        process = subprocess.Popen(
            [system_python, script_path], 
            cwd=project_root,  # <--- 强制工作目录
            env=clean_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate(timeout=15)

        if process.returncode == 0:
            # 再次确认文件是否真的生成了
            if os.path.exists(expected_image_path):
                return expected_image_path
            else:
                print("ROS脚本运行成功但未找到 captured_image.jpg，请检查脚本保存逻辑。")
                return None
        else:
            print(f"ROS脚本报错:\n{stderr}")
            return None

    except subprocess.TimeoutExpired:
        process.kill()
        print("错误：ROS 采样脚本超时。")
        return None
    except Exception as e:
        print(f"调用子进程失败: {e}")
        return None

# --- 4. MCP Tools 定义 ---

@tool(name='visual_perception', description='''视觉感知工具。
                                        功能：控制机器人拍摄一张当前环境的照片，并使用视觉大模型(VLM)进行分析。
                                        输入参数 query：你想知道关于图片的什么信息？例如“描述这张图片”、“前方有什么障碍物”、“这里有人吗”。
                                        返回结果：视觉模型对当前环境的自然语言描述。''')
def visual_perception(query: str) -> str:
    # 1. 采集
    image_path = call_ros_bridge_to_get_image()
    if not image_path:
        return "执行失败：无法从机器人摄像头获取图像。"

    # 2. 压缩
    base64_image = compress_image_to_base64(image_path, max_edge=512)
    if not base64_image:
        return "执行失败：图像处理失败。"

    # 3. 识别
    try:
        response = VLM_CLIENT.chat.completions.create(
            model=VLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个负责机器人视觉感知的助手，你需要准确、客观地描述你看到的图像内容。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"/no_think\n{query}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.7,
            extra_body={ "options": { "num_ctx": 4096 } }
        )
        return f"视觉感知结果：{response.choices[0].message.content}"

    except Exception as e:
        return f"执行失败：API调用错误 - {str(e)}"
