#!/usr/bin/env python3
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('assets/moka-ai/m3e-base')


class Action_Healthy:
    def __init__(self, ):
        # 取数据库信息
        self.healthy_name_list = []
        self.healthy_description_list = []
        self.healthy_synonym_embedding_list = []
        self.healthy_description_embedding_list = []
        self.healthy_audio_address_list = []

        # wav地址
        self.wav_path = "assets/data/Action_Healthy/"  # 数据路径

        # 取数据库文字信息
        data_path = "assets/data/Action_Healthy/DB_Healthy/"  # 数据路径
        file_name = "db_healthy"  # 文件名
        #print(data_path + file_name + '.csv')
        df_healthy = pd.read_csv(data_path + file_name + '.csv', header=None,
                               names=["healthy_name", "healthy_description", "healthy_audio_address"])
        self.healthy_name_list = df_healthy['healthy_name'].values.tolist()
        self.healthy_description_list = df_healthy['healthy_description'].values.tolist()
        self.healthy_audio_address_list = df_healthy['healthy_audio_address'].values.tolist()
        # 取同义词库文字信息
        file_name = "db_healthy_synonym"  # 文件名
        df_healthy = pd.read_csv(data_path + file_name + '.csv', header=None,
                               names=["healthy_name", "synonym_name"])
        self.synonym_healthy_name_list = df_healthy['healthy_name'].values.tolist()
        # 取同义词库向量信息
        file_name = "db_healthy_synonym_embedding"  # 文件名
        df_healthy_synonym_embedding = pd.read_csv(data_path + file_name + '.csv', header=None)
        for i in range(len(df_healthy_synonym_embedding)):
            self.healthy_synonym_embedding_list.append(df_healthy_synonym_embedding.iloc[i].tolist())
        # 取内容描述向量信息
        file_name = "db_healthy_description_embedding"  # 文件名
        df_healthy_description_embedding = pd.read_csv(data_path + file_name + '.csv', header=None)
        for i in range(len(df_healthy_description_embedding)):
            self.healthy_description_embedding_list.append(df_healthy_description_embedding.iloc[i].tolist())

        # 几个判断值
        self.A = 0.90 # 课程名的相似度高
        self.B = 0.85 # 课程内容的相似度高
        self.C = 0.80 # 课程内容的相似度低

    def healthy_search(self, answer_name, answer_content):
        print('action_healthy_search:')
        answer_name = answer_name.replace('"','')
        answer_name = answer_name.replace('《','')
        answer_name = answer_name.replace('》','')
        answer_content = answer_content.replace('"','')

        # i.从数据库中搜索名字匹配度最高的课程
        #answer_name_embedding = self.embedding_text.return_embedding(answer_name) # 求answer_name的embedding
        answer_name_embedding = model.encode(answer_name)
        
        max_sim = 0
        idx = 0
        for i in range(len(self.healthy_synonym_embedding_list)):
            sim = cosine_similarity([answer_name_embedding,self.healthy_synonym_embedding_list[i]])[0,1]
            #print(sim)
            if sim > max_sim:
                max_sim = sim
                idx = i
                if max_sim > self.A:
                    break
        print('名称相似性：',max_sim)
        # ii.如果相似性>某预定值A，返回：情况类型=1，对应结果=wav地址
        if max_sim > self.A:
            synonym_healthy_name = self.synonym_healthy_name_list[idx]
            for i in range(len(self.healthy_name_list)):
                print(i,synonym_healthy_name,self.healthy_name_list[i])
                if synonym_healthy_name == self.healthy_name_list[i]:
                    answer = self.healthy_audio_address_list[i]
                    break
            return answer
        # iii.从数据库中搜索内容匹配度最高的课程
        answer_content_embedding = model.encode(answer_content)
        max_sim = 0
        idx = 0
        for i in range(len(self.healthy_description_embedding_list)):
            sim = cosine_similarity([answer_content_embedding,self.healthy_description_embedding_list[i]])[0,1]
            if sim > max_sim:
                max_sim = sim
                idx = i
                if max_sim > self.B:
                    break
        # iv.如果相似性>某预定值B，返回：情况类型=1，对应结果=wav地址
        print('内容相似性：', idx, max_sim)
        if max_sim > self.B:
            answer = self.healthy_audio_address_list[idx]
            return answer
        # v.如果相似性<某预定值C
        if max_sim < self.C:
            if answer_name == 'none':
                answer = '输出类似于“能告诉我课程名称吗？”这样的句子'
            else: # v.ii.否则，返回：情况类型=2，对应结果=抱歉！我不会讲这个课程。
                answer = self.healthy_generating(answer_name, answer_content)
            return answer
        # vi. 如果相似性>某预定值C and 相似性<某预定值B
        if max_sim > self.C and max_sim < self.B:
            # vi.i.如果课程名称为空，返回：情况类型=3，对应结果=相近的课程有…，想听吗？
            answer = '相近的课程有《' + self.healthy_name_list[idx] + '》。想听吗？'
            return answer

    def healthy_generating(self, answer_name):
        # print('action_healthy_generating:')
        if answer_content == 'none':
            prompt_1 = '【要求】请编写200个字的、适合口述的《'
            prompt_2 = '》的健康知识课程。'
            input_text = prompt_1 + answer_name + prompt_2
        else:    
            prompt_0 = '【背景】以下是客户对课程内容的大致描述：\n'
            prompt_1 = '【要求】请根据描述，编写200个字的、适合口述的《'
            prompt_2 = '》的健康知识课程。'
            input_text = prompt_0 + answer_content + '\n' + prompt_1 + answer_name + prompt_2
        prompt_3 = '【注意】1）课程中不要出现“**”、“##”等不适合口述的文字；2）结尾处不要出现类似于“您还想了解其他课程吗？”、“还想更进一步了解更详细的内容吗？”等问句。'
        input_text = input_text + prompt_3
        answer = input_text
        return answer

action_healthy = Action_Healthy()

from utils.audio import audio_player
from tools import tool
@tool(name="healthy_course", description="""本程序的功能是健康课程讲座。根据课程名称或内容进行播讲。如客户类似表达了“我想听心理健康课程”或“请播放心理健康课程”的意思，可使用本程序。
输入：课程名称，课程内容。例如，课程名称：仅从对话内容中提取，如“老年人营养早餐的搭配”；课程内容：从对话中提取，如“营养早餐应包含哪些食物，...。”。注：如果从对话中提取不出课程名称或课程内容，相应填写字符串'none'。
回复要求：如果本函数返回的结果是''，即空字符，则回复''；如果本函数返回的结果不为空，则按照本函数返回的结果要求由大模型生成回复内容"""
, audioSyncMode=2)
def healthy_course(healthy_name, healthy_content):
    """本程序的功能是健康课程讲座。如果聊天客户的要求是听健康课程相关内容，可使用本程序。"""
    answer = action_healthy.healthy_search(healthy_name, healthy_content)
    if '.wav' in answer:
        try:
            answer = action_healthy.wav_path + answer
            audio_player.play(answer)
            return ""
        except Exception as e:
            print("无法播放")
            return ""
    else:
        return answer

@tool(name="stop_health", description="""在播放健康课程时，用户说“停止播放课程、停止播放、停止健康课程播放”等类似的话一定调用此工具
                                  回复要求：'' """)
def stop_healthy() -> str:
    """停止播放健康课程"""
    audio_player.safe_stop()
    return ""

