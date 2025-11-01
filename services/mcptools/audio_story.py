from pydantic import Field
from langchain.tools import tool, ToolRuntime
import pandas as pd
from infra.text_similarity import text_similarity
import re
from .base import ToolBase
from common import logger
from services.robot_state import RobotAction

class AudioStoryManager:
    TitleSimilarityThreshold = 0.99  # 标题相似度阈值
    ContentSimilarityThreshold = 0.95 # 内容完全相似度阈值
    ContentPossiblySimilarityThreshold = 0.9  # 内容疑似相似度阈值

    def __init__(self, audio_csv):
        self.audio_df = pd.read_csv(audio_csv, header=None, names=['title', 'content', 'audio_path'])
        # 批量编码后拆成1D list再赋值
        self.audio_df['title_embedding'] = self.audio_df['title'].apply(
            lambda x: text_similarity.encode([x])[0]
        )
        self.audio_df['content_embedding'] = self.audio_df['content'].apply(
            lambda x: text_similarity.encode([x])[0]
        )
    def get_stories_info(self):
        records = self.audio_df[['title', 'content']].to_dict(orient='records')
        data = '\n'.join([f"标题：{item['title']}，简介：{item['content']}" for item in records])
        return data

    def _compare_similarity(self, input_text, embeddings):
        title_embedding = text_similarity.encode([input_text])
        similarities = text_similarity.similarity(title_embedding, embeddings)
        max_similarity_idx = int(similarities[0].argmax())
        max_similarity_score = similarities[0][max_similarity_idx].item()
        return max_similarity_idx, max_similarity_score

    def find_similar_story(self, title, content):
        title = re.sub(r'[《》"]', '', title)
        content = re.sub(r'[《》"]', '', content)

        # 获取标题上最相似的行索引
        max_similarity_idx, max_similarity_score = self._compare_similarity(title, self.audio_df['title_embedding'].tolist())
        if max_similarity_score >= self.TitleSimilarityThreshold:
            # 找到高度相似的标题
            matched_row = self.audio_df.iloc[max_similarity_idx]
            title, audio_path = matched_row['title'], matched_row['audio_path']
            logger.info(f"找到故事：{title} (相似度: {max_similarity_score:.4f})")
            return title, audio_path

        max_similarity_idx, max_similarity_score = self._compare_similarity(content, self.audio_df['title_embedding'].tolist())
        if max_similarity_score >= self.ContentSimilarityThreshold:
            # 找到高度相似的标题
            matched_row = self.audio_df.iloc[max_similarity_idx]
            title, audio_path = matched_row['title'], matched_row['audio_path']
            logger.info(f"找到故事：{title} (相似度: {max_similarity_score:.4f})")
            return title, audio_path
        elif max_similarity_score >= self.ContentPossiblySimilarityThreshold:
            # 找到疑似相似的标题
            matched_row = self.audio_df.iloc[max_similarity_idx]
            title, audio_path = matched_row['title'], matched_row['audio_path']
            logger.info(f"找到疑似故事：{title} (相似度: {max_similarity_score:.4f})")
            return title, None

        logger.info(f"未找到相似的故事")
        return None, None

audio_story_manager = AudioStoryManager('assets/story/db/db_story.csv')

class AudioStoryMcpTool(ToolBase):
    def __init__(self):
        super().__init__('讲故事')

    def usage(self):
        return "讲故事工具，用于根据标题或内容查找本地的故事,如果找到相似的标题或内容，会返回故事标题。包含以下故事：\n" + audio_story_manager.get_stories_info()

    @tool(description='根据标题或内容查找本地的故事')
    def find_story(runtime: ToolRuntime, 
            title: str = Field(default="", description="故事标题"), 
            content: str = Field(default="", description="故事内容")) -> str:
        """根据标题或内容查找相似的故事"""
        if not isinstance(content, str):
            content = ''
        if not isinstance(title, str):
            title = ''
        title, audio_path = audio_story_manager.find_similar_story(title, content)
        if title:
            if audio_path:
                RobotAction.action_when_final(RobotAction.PLAY_AUDIO_WHEN_FINAL, audio_path, runtime.store)
                return f"找到故事《{title}》，告诉用户马上开始播放。"
            return f"找到疑似故事《{title}》，请让用户确认是否是您要找的故事。"
        return "提示用户未找到相似的故事。"


    

        
            
