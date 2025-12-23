#!/usr/bin/env python3
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from utils.embedding import Embedding_Text
embedding_text = Embedding_Text()

# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer('assets/moka-ai/m3e-base')

class Action_Story:
    def __init__(self, ):
        # 取数据库信息
        self.story_name_list = []
        self.story_description_list = []
        self.story_synonym_embedding_list = []
        self.story_description_embedding_list = []
        self.story_audio_address_list = []

        # wav地址
        self.wav_path = "assets/data/Action_Story/"  # 数据路径
        
        # 取数据库文字信息
        data_path = "assets/data/Action_Story/DB_Story/"  # 数据路径
        file_name = "db_story"  # 文件名
        df_story = pd.read_csv(data_path + file_name + '.csv', header=None,
                               names=["story_name", "story_description", "story_audio_address"])
        self.story_name_list = df_story['story_name'].values.tolist()
        self.story_description_list = df_story['story_description'].values.tolist()
        self.story_audio_address_list = df_story['story_audio_address'].values.tolist()
        # 取同义词库文字信息
        file_name = "db_story_synonym"  # 文件名
        df_story = pd.read_csv(data_path + file_name + '.csv', header=None,
                               names=["story_name", "synonym_name"])
        self.synonym_story_name_list = df_story['story_name'].values.tolist()
        # 取同义词库向量信息
        file_name = "db_story_synonym_embedding"  # 文件名
        df_story_synonym_embedding = pd.read_csv(data_path + file_name + '.csv', header=None)
        for i in range(len(df_story_synonym_embedding)):
            self.story_synonym_embedding_list.append(df_story_synonym_embedding.iloc[i].tolist())
        file_name = "db_story_description_embedding"  # 文件名
        df_story_description_embedding = pd.read_csv(data_path + file_name + '.csv', header=None)
        for i in range(len(df_story_description_embedding)):
            self.story_description_embedding_list.append(df_story_description_embedding.iloc[i].tolist())

        # 几个判断值
        self.A = 0.99 # 故事名的相似度高
        self.B = 0.90 # 故事内容的相似度高
        self.C = 0.85 # 故事内容的相似度低

    def story_search(self, answer_name, answer_content):
        print('action_story_search:')
        answer_name = answer_name.replace('"','')
        answer_name = answer_name.replace('《','')
        answer_name = answer_name.replace('》','')
        answer_content = answer_content.replace('"','')

        # i.从数据库中搜索名字匹配度最高的故事
        answer_name_embedding = embedding_text.return_embedding(answer_name) # 求answer_name的embedding
        # answer_name_embedding = model.encode(answer_name)

        #print(answer_name_embedding)
        #print(answer_name)
        max_sim = 0
        idx = 0
        for i in range(len(self.story_synonym_embedding_list)):
            sim = cosine_similarity([answer_name_embedding,self.story_synonym_embedding_list[i]])[0,1]
            # print(sim)
            if sim > max_sim:
                max_sim = sim
                idx = i
                if max_sim > self.A:
                    break
        print('名字相似性：', idx, max_sim)
        # ii.如果相似性>某预定值A，返回：情况类型=1，对应结果=wav地址
        if max_sim > self.A:
            synonym_story_name = self.synonym_story_name_list[idx]
            for i in range(len(self.story_name_list)):
                print(i,synonym_story_name,self.story_name_list[i])
                if synonym_story_name == self.story_name_list[i]:
                    answer = self.story_audio_address_list[i]
                    break
            return answer
        # iii.从数据库中搜索故事内容匹配度最高的故事
        answer_content_embedding = embedding_text.return_embedding(answer_content) # 求answer_content的embedding
        # answer_content_embedding = model.encode(answer_content)
        max_sim = 0
        idx = 0
        for i in range(len(self.story_description_embedding_list)):
            sim = cosine_similarity([answer_content_embedding,self.story_description_embedding_list[i]])[0,1]
            if sim > max_sim:
                max_sim = sim
                idx = i
                if max_sim > self.B:
                    break
        # iv.如果相似性>某预定值B，返回：情况类型=1，对应结果=wav地址
        print('内容相似性：', idx, max_sim)
        if max_sim > self.B:
            answer = self.story_audio_address_list[idx]
            return answer
        # v.如果相似性<某预定值C
        if max_sim < self.C:
            if answer_name == 'none':
                answer = '输出类似于“能告诉我故事名称吗？”这样的句子'
            else: # v.ii.否则，返回：情况类型=2，对应结果=抱歉！我不会讲这个故事。
                answer = self.story_generating(answer_name, answer_content)
            return answer
        # vi. 如果相似性>某预定值C and 相似性<某预定值B
        if max_sim > self.C and max_sim < self.B:
            # vi.i.如果故事名称为空，返回：情况类型=3，对应结果=相近的故事有…，想听吗？
            answer = '相近的故事有《' + self.story_name_list[idx] + '》。想听吗？'
            return answer

    def story_generating(self, answer_name, answer_content):
        # print('action_story_generating:')
        if answer_content == 'none':
            prompt_1 = '【要求】请编写200个字的、适合口述的《'
            prompt_2 = '》的故事。'
            input_text = prompt_1 + answer_name + prompt_2
        else:    
            prompt_0 = '【背景】以下是客户对故事内容的大致描述：\n'
            prompt_1 = '【要求】请根据描述，编写200个字的、适合口述的《'
            prompt_2 = '》的故事。'
            input_text = prompt_0 + answer_content + '\n' + prompt_1 + answer_name + prompt_2
        prompt_3 = '【注意】1）故事中不要出现“**”、“##”等不适合口述的文字；2）结尾处不要出现类似于“您还想了解其他故事吗？”、“还想更进一步了解更详细的内容吗？”等问句。'
        input_text = input_text + prompt_3
        # print(input_text)
        #answer = llm.return_text(input_text, "qwen3:14b")
        #answer = answer.replace('\n','')
        answer = input_text
        return answer

action_story = Action_Story()

from utils.audio import audio_player
from tools import tool
@tool(name="story_telling", description="""本程序的功能是讲故事，根据故事名称或内容进行播讲。如客户类似表达了“我想听空城计的故事”或“我想听空城计”的意思，可使用本程序。
输入：故事名称，故事内容。例如，故事名称：仅从对话内容中提取（不要自己设想、猜测），如“桃园三结义”；故事内容：从对话中提取，如“三个男人结为异性兄弟，并肩作战。”。注：如果从对话中提取不出故事名称或故事内容，相应填写字符串'none'。
回复要求：如果本函数返回的结果是''，即空字符，则回复''；如果本函数返回的结果不为空，则按照本函数返回的结果要求由大模型生成回复内容""",audioSyncMode=2) 
def story_telling(story_name, story_content):
    print('story_telling:',story_name, story_content)
    """本程序的功能是讲故事。如果聊天客户的要求是听故事，可使用本程序。"""
    answer = action_story.story_search(story_name, story_content)
    if '.wav' in answer:
        try:
            answer = action_story.wav_path + answer
            audio_player.play(answer)
            return ""
        except Exception as e:
            print("无法播放")
            return ""
    else:
        return answer

@tool(name="stop_story", description="""在播放故事时，用户说“停止播放故事、停止播放、停止故事播放”等类似的话一定调用此工具
                                  回复要求：'' """)
def stop_story() -> str:
    """停止播放故事"""
    audio_player.safe_stop()
    return ""


