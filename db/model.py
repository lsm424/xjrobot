# -*- coding: utf-8 -*-
'''
@File    :   model.py
@Time    :   2025/10/14 09:16:06
@Author  :   wadesmli 
@Version :   1.0
@Desc    :   None
'''


from mcp.types import Content
from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, JSON, String, TIMESTAMP, Text, text, BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from models.base import Base, async_engine
import asyncio


metadata = Base.metadata

class TChatHistory(Base):
    __tablename__ = 't_chat_history'
    __table_args__ = {'comment': '聊天记录表'}
    serialize_only = ('id', 'user_id', 'user_input', 'llm_response', 'update_time', 'create_time')

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, server_default=text("''"), comment='会话ID')
    user_id = Column(BIGINT, nullable=False, server_default=text("'0'"), comment='用户ID')
    content = Column(Text, nullable=False, server_default=text("''"), comment='内容')
    role = Column(String(255), nullable=False, server_default=text("''"), comment='角色: user,assistant')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment='创建时间')


async def create_tables():
    """创建所有表（如果不存在）"""
    async with async_engine.begin() as conn:
        # 检查表是否存在，如果存在则不创建
        # 这里使用create_all，但SQLAlchemy默认会跳过已存在的表
        await conn.run_sync(Base.metadata.create_all)
    print("表创建完成（已存在的表不会被覆盖）")
asyncio.run(create_tables())