"""SQLAlchemy declarative base。所有 ORM 模型继承。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
