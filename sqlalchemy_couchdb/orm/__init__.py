"""
CouchDB ORM 支持 - 提供类似 SQLAlchemy ORM 的声明式 API

核心组件：
1. Declarative Base - 声明式基类
2. Relationship - 关系定义
3. Session - 对象持久化和状态管理

Example:
    ```python
    from sqlalchemy import create_engine, Column, String, Integer
    from sqlalchemy_couchdb.orm import declarative_base, Session, relationship

    # 创建 Base
    Base = declarative_base()

    # 定义模型
    class User(Base):
        __tablename__ = "users"

        id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        age = Column(Integer)

        # 一对多关系
        posts = relationship("Post", back_populates="author")

    class Post(Base):
        __tablename__ = "posts"

        id = Column(String, primary_key=True)
        title = Column(String)
        author_id = Column(String, ForeignKey("users.id"))

        author = relationship("User", back_populates="posts")

    # 创建引擎和 Session
    engine = create_engine("couchdb://admin:password@localhost:5984/mydb")
    session = Session(engine)

    # 使用 ORM
    user = User(id="user1", name="Alice", age=30)
    session.add(user)
    session.commit()

    # 查询
    users = session.query(User).filter(User.age > 18).all()

    session.close()
    ```

注意事项：
1. CouchDB 不支持真正的事务，commit 只是刷新操作
2. JOIN 通过多次查询模拟
3. 关系通过文档引用实现
"""

# Declarative
from .declarative import (
    declarative_base,
    CouchDBDeclarativeMeta,
    CouchDBColumn,
    couchdb_index,
    ForeignKey,
    create_all_indexes,
    create_all_views,
)

# Relationship
from .relationship import (
    Relationship,
    relationship,
    backref,
    RelationshipType,
    LoadStrategy,
    CascadeAction,
    CascadeManager,
)

# Session
from .session import Session, Query, sessionmaker, ObjectState, InstanceState, IdentityMap

# Async Session
from .async_session import CouchDBAsyncSession, async_sessionmaker


__all__ = [
    # Declarative
    "declarative_base",
    "CouchDBDeclarativeMeta",
    "CouchDBColumn",
    "couchdb_index",
    "ForeignKey",
    "create_all_indexes",
    "create_all_views",
    # Relationship
    "Relationship",
    "relationship",
    "backref",
    "RelationshipType",
    "LoadStrategy",
    "CascadeAction",
    "CascadeManager",
    # Session
    "Session",
    "Query",
    "sessionmaker",
    "ObjectState",
    "InstanceState",
    "IdentityMap",
    # Async Session
    "CouchDBAsyncSession",
    "async_sessionmaker",
]
