class TextSplitter:
    def __init__(self, separators=None):
        if separators is None:
            self.separators = ['，', '。', '！', '？', '；', '、', '……']
        else:
            self.separators = separators
    
    def split_text(self, text):
        if not text:
            return
        
        current_chunk = []
        minlen = 3
        for char in text:
            current_chunk.append(char)
            if char in self.separators:
                if len(current_chunk) <= minlen:
                    continue
                minlen += 10
                yield ''.join(current_chunk)
                current_chunk = []
        
        if current_chunk:
            yield ''.join(current_chunk)
    
    def __call__(self, text):
        return self.split_text(text)
