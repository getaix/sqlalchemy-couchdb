"""
Declarative Base 支持 - 为 CouchDB 提供 SQLAlchemy ORM 风格的声明式基类

功能：
1. 表定义支持（映射到 CouchDB type 字段）
2. 列类型映射
3. 主键和外键（外键通过文档引用模拟）
4. 索引声明
"""

from typing import Any, Dict, List, Optional, Type, TypeVar
from sqlalchemy.ext.declarative import declarative_base as sa_declarative_base
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy import Column, MetaData, Index
import logging


logger = logging.getLogger(__name__)


# 类型变量
T = TypeVar("T")


class CouchDBDeclarativeMeta(DeclarativeMeta):
    """
    CouchDB Declarative Meta 类

    扩展 SQLAlchemy 的 DeclarativeMeta，添加 CouchDB 特定的元数据：
    - _couchdb_type: 对应 CouchDB 文档的 type 字段
    - _couchdb_indexes: CouchDB 索引定义
    - _couchdb_views: CouchDB 视图定义
    """

    def __init__(cls, classname, bases, dict_):
        super().__init__(classname, bases, dict_)

        # 添加 CouchDB 特定属性
        if not hasattr(cls, "__abstract__") or not cls.__abstract__:
            # 设置 CouchDB type 字段（默认使用表名）
            if not hasattr(cls, "_couchdb_type"):
                cls._couchdb_type = getattr(cls, "__tablename__", classname.lower())

            # 初始化索引列表
            if not hasattr(cls, "_couchdb_indexes"):
                cls._couchdb_indexes = []

            # 初始化视图列表
            if not hasattr(cls, "_couchdb_views"):
                cls._couchdb_views = []

            logger.debug(f"Registered CouchDB model: {classname} -> {cls._couchdb_type}")


def declarative_base(metadata: Optional[MetaData] = None, **kwargs) -> Type[Any]:
    """
    创建 CouchDB Declarative Base 类

    类似于 SQLAlchemy 的 declarative_base()，但针对 CouchDB 进行了优化。

    Example:
        ```python
        from sqlalchemy_couchdb.orm import declarative_base, Column, String, Integer

        Base = declarative_base()

        class User(Base):
            __tablename__ = "users"

            id = Column(String, primary_key=True)
            name = Column(String, nullable=False)
            age = Column(Integer)
            email = Column(String, unique=True)
        ```

    Args:
        metadata: SQLAlchemy MetaData 对象
        **kwargs: 传递给 declarative_base 的其他参数

    Returns:
        Declarative Base 类
    """
    if metadata is None:
        metadata = MetaData()

    # 使用自定义的 metaclass
    Base = sa_declarative_base(metadata=metadata, metaclass=CouchDBDeclarativeMeta, **kwargs)

    # 添加 CouchDB 特定的类方法
    Base.__abstract__ = True

    @classmethod
    def from_couchdb(cls: Type[T], doc: Dict[str, Any]) -> T:
        """
        从 CouchDB 文档创建模型实例

        Args:
            doc: CouchDB 文档

        Returns:
            模型实例
        """
        # 过滤出模型定义的列
        kwargs = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name in doc:
                kwargs[col_name] = doc[col_name]

        # 创建实例
        instance = cls(**kwargs)

        # 保存 CouchDB 特殊字段
        if hasattr(instance, "_id") and "_id" in doc:
            instance._id = doc["_id"]
        if hasattr(instance, "_rev") and "_rev" in doc:
            instance._rev = doc["_rev"]

        return instance

    @classmethod
    def to_couchdb(cls, instance: Any) -> Dict[str, Any]:
        """
        将模型实例转换为 CouchDB 文档

        Args:
            instance: 模型实例

        Returns:
            CouchDB 文档
        """
        doc = {}

        # 添加所有列值
        for column in cls.__table__.columns:
            col_name = column.name
            value = getattr(instance, col_name, None)
            if value is not None:
                doc[col_name] = value

        # 添加 type 字段
        doc["type"] = cls._couchdb_type

        # 添加 CouchDB 特殊字段
        if hasattr(instance, "_id") and instance._id:
            doc["_id"] = instance._id
        if hasattr(instance, "_rev") and instance._rev:
            doc["_rev"] = instance._rev

        return doc

    Base.from_couchdb = from_couchdb
    Base.to_couchdb = to_couchdb

    return Base


class CouchDBColumn(Column):
    """
    CouchDB 列定义

    扩展 SQLAlchemy Column，添加 CouchDB 特定的选项：
    - indexed: 是否创建 CouchDB 索引
    - view_map: 用于 MapReduce 视图的 map 函数
    - view_reduce: 用于 MapReduce 视图的 reduce 函数
    """

    def __init__(
        self,
        *args,
        indexed: bool = False,
        view_map: Optional[str] = None,
        view_reduce: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化 CouchDB 列

        Args:
            *args: Column 的位置参数
            indexed: 是否创建 CouchDB 索引
            view_map: MapReduce map 函数
            view_reduce: MapReduce reduce 函数
            **kwargs: Column 的关键字参数
        """
        super().__init__(*args, **kwargs)
        self.info["indexed"] = indexed
        self.info["view_map"] = view_map
        self.info["view_reduce"] = view_reduce


def couchdb_index(*columns, **kwargs) -> Index:
    """
    创建 CouchDB 索引

    Example:
        ```python
        class User(Base):
            __tablename__ = "users"

            id = Column(String, primary_key=True)
            email = Column(String)
            age = Column(Integer)

            # 创建复合索引
            __table_args__ = (
                couchdb_index("email", "age"),
            )
        ```

    Args:
        *columns: 列名
        **kwargs: 索引选项

    Returns:
        SQLAlchemy Index 对象
    """
    return Index(*columns, **kwargs)


class ForeignKey:
    """
    CouchDB 外键（通过文档引用模拟）

    在 CouchDB 中，外键是通过存储目标文档的 _id 来实现的。

    Example:
        ```python
        class Post(Base):
            __tablename__ = "posts"

            id = Column(String, primary_key=True)
            title = Column(String)
            author_id = Column(String, ForeignKey("users.id"))
        ```

    注意：CouchDB 不支持真正的外键约束，这只是语义上的声明。
    """

    def __init__(
        self, column: str, onupdate: Optional[str] = None, ondelete: Optional[str] = None, **kwargs
    ):
        """
        初始化外键

        Args:
            column: 目标列（格式：table.column）
            onupdate: 更新时的行为（CASCADE, SET NULL, RESTRICT 等）
            ondelete: 删除时的行为（CASCADE, SET NULL, RESTRICT 等）
            **kwargs: 其他选项
        """
        self.column = column
        self.onupdate = onupdate
        self.ondelete = ondelete
        self.kwargs = kwargs

        # 解析目标表和列
        if "." in column:
            self.target_table, self.target_column = column.split(".", 1)
        else:
            raise ValueError(f"ForeignKey column must be in format 'table.column', got: {column}")


def create_all_indexes(engine: Any, models: List[Type[Any]]) -> None:
    """
    为所有模型创建 CouchDB 索引

    Args:
        engine: SQLAlchemy Engine
        models: 模型类列表
    """
    logger.info(f"Creating indexes for {len(models)} models")

    for model in models:
        # 获取需要索引的列
        indexed_columns = []
        for column in model.__table__.columns:
            if column.info.get("indexed", False):
                indexed_columns.append(column.name)

        if indexed_columns:
            logger.info(f"Creating index for {model.__tablename__}: {indexed_columns}")
            # 这里应该调用 CouchDB 的 ensure_index API
            # engine.dialect.client.ensure_index(model._couchdb_type, indexed_columns)

        # 处理 __table_args__ 中的索引
        if hasattr(model, "__table_args__"):
            table_args = model.__table_args__
            if isinstance(table_args, tuple):
                for arg in table_args:
                    if isinstance(arg, Index):
                        index_columns = [col.name for col in arg.columns]
                        logger.info(f"Creating index for {model.__tablename__}: {index_columns}")
                        # engine.dialect.client.ensure_index(model._couchdb_type, index_columns)


def create_all_views(engine: Any, models: List[Type[Any]]) -> None:
    """
    为所有模型创建 CouchDB 视图

    Args:
        engine: SQLAlchemy Engine
        models: 模型类列表
    """
    logger.info(f"Creating views for {len(models)} models")

    for model in models:
        # 获取需要创建视图的列
        for column in model.__table__.columns:
            view_map = column.info.get("view_map")
            view_reduce = column.info.get("view_reduce")

            if view_map:
                view_name = f"{model._couchdb_type}_by_{column.name}"
                logger.info(f"Creating view: {view_name}")
                # 这里应该调用 CouchDB 的 view creation API
                # engine.dialect.client.create_view(view_name, view_map, view_reduce)
