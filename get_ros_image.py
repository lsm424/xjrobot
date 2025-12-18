import rospy
import cv2
import sys
# 这里的路径根据你的 ROS 版本修改（如 /opt/ros/noetic/...）
sys.path.append('/opt/ros/noetic/lib/python3/dist-packages')
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

def save_single_image():
    # 1. 初始化节点
    rospy.init_node('image_saver', anonymous=True)
    
    # 2. 创建 CvBridge 实例
    bridge = CvBridge()
    
    topic_name = "/camera/color/image_raw"
    rospy.loginfo(f"正在等待话题 {topic_name} 的数据...")

    try:
        # 3. 等待并接收一帧图片数据 (timeout=None 表示无限等待)
        data = rospy.wait_for_message(topic_name, Image, timeout=10.0)
        rospy.loginfo("已接收到图片，正在处理...")

        # 4. 将 ROS Image 消息转换成 OpenCV 格式
        # 如果是彩色图用 bgr8，如果是黑白图用 mono8
        cv_image = bridge.imgmsg_to_cv2(data, desired_encoding="bgr8")

        # 5. 保存图片到本地
        file_name = "captured_image.jpg"
        cv2.imwrite(file_name, cv_image)
        rospy.loginfo(f"图片已成功保存为: {file_name}")

    except rospy.ROSException as e:
        rospy.logerr("等待超时，未接收到图片数据。")
    except CvBridgeError as e:
        rospy.logerr(f"CvBridge 转换失败: {e}")
    except Exception as e:
        rospy.logerr(f"发生错误: {e}")

    # 执行完毕后会自动退出，不需要 rospy.spin()
    rospy.loginfo("程序执行完毕，正在退出...")

if __name__ == '__main__':
    save_single_image()