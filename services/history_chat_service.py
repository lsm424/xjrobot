from common.db import get_db_context_session
from common.config import cfg

class HistoryChatService:
    def __init__(self, round_cnt=20):
        self.round_cnt = round_cnt
        self.lastrowid = None
        with get_db_context_session() as cursor:
            cursor.execute('''create table if not exists history_chat (
                id integer primary key autoincrement,
                user_question text,
                robot_answer text,
                created_at datetime default current_timestamp)'''
            )

    def save_chat(self, user_question, robot_answer):
        with get_db_context_session() as cursor:
            cursor.execute('''insert into history_chat (user_question, robot_answer) values (?, ?)''', (user_question, robot_answer))

    def get_history(self):
        with get_db_context_session() as cursor:
            cursor.execute('''select * from history_chat where robot_answer != "" order by id limit ?''', (self.round_cnt, ))
            rows = cursor.fetchall()
        return [dict(zip([desc[0] for desc in cursor.description], row)) for row in rows]

history_chat = HistoryChatService(cfg.getint('llm', 'recent_round'))