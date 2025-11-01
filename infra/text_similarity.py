from sentence_transformers import SentenceTransformer, SimilarityFunction

class TextSimilarity:
    def __init__(self, model_name: str = "moka-ai/m3e-base"):
        self.model = SentenceTransformer(model_name)
        self.model.similarity_fn_name = SimilarityFunction.COSINE

    def encode(self, sentences: list[str]):
        ''''编码句子为向量'''
        return self.model.encode(sentences)
    
    def similarity(self, embeddings1: list[float], embeddings2: list[float]):
        ''''计算两个向量的相似度，返回矩阵'''
        return self.model.similarity(embeddings1, embeddings2)


text_similarity = TextSimilarity()