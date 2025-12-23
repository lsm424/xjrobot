import requests
# url = 'http://172.21.102.154:5100/embed'
# url = 'http://172.30.3.7:5100/embed'
url = 'http://47.108.93.204:5100/embed'

class Embedding_Text:
    def __init__(self):
        # self.embedding = SentenceTransformer('/home/robot/coding/bot_brain/Embedding/moka-ai/m3e-base')
        # self.embedding = SentenceTransformer('bot_brain/Embedding/moka-ai/m3e-base')
        pass

    def return_embedding(self, text):
        # 计算句子的句向量
        print('==========================0')
        print(type(text),text)
        if type(text) == str:
            sentences = [text]
            data = {"sentences":sentences, "normalize":True}
            res = requests.post(url, json=data)
            res = res.text
            start_idx = res.index('embeddings')
            end_idx = res.index('model')
            emb_text = res[start_idx+14:end_idx-5]
            emb_list = emb_text.split(',')
            emb = [float(item) for item in emb_list]
        else:
            sentences = text
            data = {"sentences":sentences, "normalize":True}
            print('==========================1')
            print('sentences:',sentences)
            res = requests.post(url, json=data)
            print('==========================2')
            res = res.text
            start_idx = res.index('embeddings')
            end_idx = res.index('model')
            emb_text = res[start_idx+14:end_idx-4]
            text_list = emb_text.split('],[')
            for item in text_list:
                item = item.replace(']','')
                item = item.replace('[','')
            emb = [] 
            for text in text_list:
                text_split = text.split(',')
                emb.append([float(item) for item in text_split])
        return emb

'''
embedding_text = Embedding_Text()
emb = embedding_text.return_embedding('您好！')
print(emb,len(emb))
embedding_text = Embedding_Text()
emb = embedding_text.return_embedding(['您好！','早上好','晚上好'])
print(emb,len(emb),len(emb[0]),len(emb[1]),len(emb[2]))
'''