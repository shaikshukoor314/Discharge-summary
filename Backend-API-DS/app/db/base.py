from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import MetaData


class Base(DeclarativeBase):

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

