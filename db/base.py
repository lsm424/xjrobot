'''
Author: wadesmli
Date: 2024-08-13 14:59:59
LastEditTime: 2024-08-27 19:17:18
Description: 
'''
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from common.config import cfg
from sqlalchemy import Column, MetaData, create_engine, func, text, DateTime
from datetime import datetime

Base = declarative_base()


def to_dict(self):
    if not hasattr(self, 'serialize_only'):
        self.serialize_only = list(map(lambda x: x.name, self.__table__.columns))
    ret = {c: getattr(self, c, None) for c in self.serialize_only}
    for k, v in ret.items():
        if isinstance(v, datetime):
            ret[k] = v.strftime('%Y-%m-%d %H:%M:%S')
    # if isinstance(ret.get('created_at', None), datetime):
    #     ret['created_at'] = ret['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    # if isinstance(ret.get('updated_at', None), datetime):
    #     ret['updated_at'] = ret['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
    # if isinstance(ret.get('token_expire_time', None), datetime):
    #     ret['token_expire_time'] = ret['token_expire_time'].strftime('%Y-%m-%d %H:%M:%S')
    return ret


Base.to_dict = to_dict
engine = create_engine(cfg.get('db', 'dsn'), echo=False, pool_recycle=3600)
metadata = MetaData(bind=engine)


class TimestampMixin:
    create_time = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now(), comment='创建时间')
    update_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间')
    delete_time = Column(DateTime, nullable=False, server_default=func.now(), comment='删除时间')
