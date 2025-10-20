from db.base import Base, engine, metadata
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker

# t = Table(AdminUser.__tablename__, metadata, autoload=True)

Base.metadata.create_all(engine, checkfirst=True)


def get_db_session(engine):
    DbSession = sessionmaker()
    DbSession.configure(bind=engine)
    return DbSession()


@contextmanager
def get_db_context_session(transaction=False, engine=engine):
    session = get_db_session(engine)

    if transaction:
        try:
            session.begin()
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        try:
            yield session
        except:
            raise
        finally:
            session.close()
