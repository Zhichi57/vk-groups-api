from sqlalchemy import create_engine, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime

import os

# Получение адреса для подключения к бд из окружения
DATABASE_URL = os.getenv("DATABASE_URL")


# Подключение к базе данных
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Сущность "Запросы"
class Queries(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    query_date_time = Column(DateTime, unique=False)
    query = Column(String, unique=False)

    groups = relationship("Groups")


# Сущность "Группы"
class Groups(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=False)
    screen_name = Column(String, unique=False)
    is_closed = Column(Integer, unique=False)
    type = Column(String, unique=False)
    query_id = Column(Integer, ForeignKey('queries.id'))
    user_id = Column(Integer, index=True)
