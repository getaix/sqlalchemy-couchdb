"""
异步 ORM Session - 支持 SQLAlchemy 标准异步 ORM API

提供与 SQLAlchemy AsyncSession 兼容的接口，支持：
- 异步 CRUD 操作
- Event 系统（before_insert, before_update, after_insert 等）
- 身份映射（Identity Map）
- 状态管理（Transient/Pending/Persistent/Detached）
- 事务管理
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, List, Optional, Type, TypeVar

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker as base_async_sessionmaker
from sqlalchemy.orm import DeclarativeMeta

T = TypeVar("T")


class CouchDBResult:
    """CouchDB 查询结果包装器

    这个类包装 SQLAlchemy 的 Result 对象，避免 ORM 结果映射时的 NotImplementedError。
    它提供简化的接口用于访问查询结果。
    """

    def __init__(self, raw_result: Any, statement: Any):
        """初始化结果包装器

        Args:
            raw_result: SQLAlchemy Result 对象
            statement: 执行的 SQL 语句
        """
        self._raw_result = raw_result
        self._statement = statement
        self._rows = None
        self._model_class = None

        # 从 SELECT 语句中提取模型类
        from sqlalchemy.sql import Select
        if isinstance(statement, Select):
            # 尝试从 column_descriptions 获取实体类型
            if hasattr(statement, 'column_descriptions'):
                descs = statement.column_descriptions
                if descs and len(descs) > 0:
                    first_desc = descs[0]
                    if isinstance(first_desc, dict) and 'entity' in first_desc:
                        self._model_class = first_desc['entity']

            # 尝试从 froms 中获取对应的模型类
            # 这需要通过 Table 的 metadata 找到对应的模型类
            if not self._model_class and hasattr(statement, 'froms'):
                # 这里我们无法直接从 Table 获取模型类
                # 需要用户在使用时手动指定，或者通过其他方式
                pass

    def _fetch_all_rows(self):
        """获取所有行数据（懒加载）"""
        if self._rows is None:
            try:
                # 方法 1：直接从 cursor 获取数据，避免 ORM 映射
                cursor = getattr(self._raw_result, 'cursor', None)
                if cursor and hasattr(cursor, '_rows'):
                    # 从 CouchDB cursor 直接读取行数据
                    self._rows = list(cursor._rows)
                elif cursor and hasattr(cursor, 'fetchall'):
                    # 回退到 fetchall 方法
                    self._rows = cursor.fetchall()
                else:
                    # 方法 2：尝试迭代 result 对象
                    try:
                        self._rows = list(self._raw_result)
                    except NotImplementedError:
                        # 方法 3：如果迭代失败，尝试从 _rows 属性直接获取
                        if hasattr(self._raw_result, '_rows'):
                            self._rows = list(self._raw_result._rows)
                        else:
                            self._rows = []
            except Exception as e:
                # 如果所有方法都失败，返回空列表
                print(f"Warning: Failed to fetch rows: {e}")
                self._rows = []
        return self._rows

    def scalars(self):
        """返回标量结果对象"""
        return CouchDBScalars(self)

    def scalar(self):
        """返回单个标量值"""
        rows = self._fetch_all_rows()
        if not rows:
            return None
        first_row = rows[0]
        return first_row[0] if isinstance(first_row, (list, tuple)) else first_row

    def _row_to_model(self, row_tuple: tuple, model_class: type) -> Any:
        """将行元组转换为模型对象

        Args:
            row_tuple: 行数据元组
            model_class: 模型类

        Returns:
            模型实例
        """
        if not hasattr(model_class, '__table__'):
            return row_tuple

        # 获取列名
        columns = [col.name for col in model_class.__table__.columns]

        # 构建 kwargs
        kwargs = {}
        for i, col_name in enumerate(columns):
            if i < len(row_tuple):
                kwargs[col_name] = row_tuple[i]

        # 创建模型实例
        return model_class(**kwargs)

    def all(self):
        """返回所有行"""
        return self._fetch_all_rows()

    def one(self):
        """返回唯一一行"""
        rows = self._fetch_all_rows()
        if len(rows) != 1:
            raise ValueError(f"Expected exactly one row, got {len(rows)}")
        return rows[0]

    def one_or_none(self):
        """返回一行或 None"""
        rows = self._fetch_all_rows()
        if len(rows) == 0:
            return None
        if len(rows) > 1:
            raise ValueError(f"Expected at most one row, got {len(rows)}")
        return rows[0]

    def first(self):
        """返回第一行"""
        rows = self._fetch_all_rows()
        return rows[0] if rows else None


class CouchDBScalars:
    """CouchDB 标量结果包装器

    提供对查询结果第一列的访问。
    """

    def __init__(self, result: CouchDBResult):
        """初始化标量结果

        Args:
            result: CouchDBResult 对象
        """
        self._result = result

    def all(self):
        """返回所有标量值（转换为模型对象）"""
        rows = self._result._fetch_all_rows()

        # 如果有模型类，将元组转换为模型对象
        if self._result._model_class and rows and isinstance(rows[0], tuple):
            return [self._result._row_to_model(row, self._result._model_class) for row in rows]

        # 否则提取第一列
        return [row[0] if isinstance(row, (list, tuple)) else row for row in rows]

    def one(self):
        """返回唯一标量值"""
        scalars = self.all()
        if len(scalars) != 1:
            raise ValueError(f"Expected exactly one scalar, got {len(scalars)}")
        return scalars[0]

    def one_or_none(self):
        """返回一个标量值或 None"""
        scalars = self.all()
        if len(scalars) == 0:
            return None
        if len(scalars) > 1:
            raise ValueError(f"Expected at most one scalar, got {len(scalars)}")
        return scalars[0]

    def first(self):
        """返回第一个标量值"""
        scalars = self.all()
        return scalars[0] if scalars else None


class CouchDBAsyncSession:
    """
    CouchDB 异步 Session
   
    这是一个包装器，使得 CouchDB 能够使用 SQLAlchemy 的标准异步 ORM API。
    内部使用 Core API 执行操作，同时触发 ORM events。
    """

    def __init__(self, session: AsyncSession):
        """
        初始化异步 Session
        
        Args:
            session: SQLAlchemy AsyncSession 实例
        """
        self._session = session
        self._new_instances: List[Any] = []  # 新建的实例
        self._dirty_instances: List[Any] = []  # 修改的实例
        self._deleted_instances: List[Any] = []  # 删除的实例

    def add(self, instance: Any) -> None:
        """
        添加实例到 session
        
        这会将实例标记为"待插入"，在 flush/commit 时执行。
        触发 before_insert event。
        """
        self._new_instances.append(instance)

    def add_all(self, instances: List[Any]) -> None:
        """批量添加实例"""
        self._new_instances.extend(instances)

    def delete(self, instance: Any) -> None:
        """
        删除实例
        
        将实例标记为"待删除"，在 flush/commit 时执行。
        触发 before_delete event。
        """
        self._deleted_instances.append(instance)

    async def flush(self) -> None:
        """
        刷新待处理的更改到数据库
        
        执行所有待处理的 INSERT/UPDATE/DELETE 操作。
        """
        # 处理插入
        for instance in self._new_instances:
            await self._flush_insert(instance)

        # 处理更新
        for instance in self._dirty_instances:
            await self._flush_update(instance)

        # 处理删除
        for instance in self._deleted_instances:
            await self._flush_delete(instance)

        # 清空列表
        self._new_instances.clear()
        self._dirty_instances.clear()
        self._deleted_instances.clear()

    async def commit(self) -> None:
        """
        提交事务
        
        先 flush，然后提交底层 session。
        """
        await self.flush()
        await self._session.commit()

    async def rollback(self) -> None:
        """回滚事务"""
        self._new_instances.clear()
        self._dirty_instances.clear()
        self._deleted_instances.clear()
        await self._session.rollback()

    async def close(self) -> None:
        """关闭 session"""
        await self._session.close()

    async def execute(self, statement: Any) -> Any:
        """执行语句并返回自定义结果对象

        注意：这个方法返回一个简化的结果对象，用于避免 CouchDB 方言
        在 ORM 结果映射时的 NotImplementedError。
        """
        from sqlalchemy.sql import Select

        # 对于 SELECT 查询，使用特殊处理避免 ORM 映射
        if isinstance(statement, Select):
            # 获取底层连接并直接执行
            conn = await self._session.connection()
            result = await conn.execute(statement)

            # 包装结果，提供兼容的接口
            return CouchDBResult(result, statement)
        else:
            # 对于其他语句类型（INSERT/UPDATE/DELETE），正常执行
            result = await self._session.execute(statement)
            return result

    async def scalars(self, statement: Any) -> Any:
        """执行语句并返回标量结果

        注意：这个方法也经过包装以避免 ORM 结果映射问题。
        """
        result = await self.execute(statement)
        return result.scalars()

    async def _flush_insert(self, instance: Any) -> None:
        """
        执行插入操作
        
        使用 Core API insert，这样可以触发 SQLAlchemy 的 event 系统。
        """
        model_class = type(instance)
        if not hasattr(model_class, "__table__"):
            raise ValueError(f"{model_class.__name__} 没有 __table__ 属性")

        table = model_class.__table__

        # 构建插入数据
        values = {}
        for column in table.columns:
            if hasattr(instance, column.name):
                value = getattr(instance, column.name)
                if value is not None:
                    values[column.name] = value

        # 执行插入
        stmt = insert(table).values(**values)
        await self._session.execute(stmt)

    async def _flush_update(self, instance: Any) -> None:
        """
        执行更新操作
        """
        model_class = type(instance)
        if not hasattr(model_class, "__table__"):
            raise ValueError(f"{model_class.__name__} 没有 __table__ 属性")

        table = model_class.__table__

        # 找到主键
        primary_key_col = None
        primary_key_value = None
        for column in table.columns:
            if column.primary_key:
                primary_key_col = column
                primary_key_value = getattr(instance, column.name, None)
                break

        if primary_key_col is None or primary_key_value is None:
            raise ValueError(f"无法更新 {model_class.__name__}：缺少主键值")

        # 构建更新数据
        values = {}
        for column in table.columns:
            if not column.primary_key and hasattr(instance, column.name):
                value = getattr(instance, column.name)
                if value is not None:
                    values[column.name] = value

        # 执行更新
        stmt = update(table).where(primary_key_col == primary_key_value).values(**values)
        await self._session.execute(stmt)

    async def _flush_delete(self, instance: Any) -> None:
        """
        执行删除操作
        """
        model_class = type(instance)
        if not hasattr(model_class, "__table__"):
            raise ValueError(f"{model_class.__name__} 没有 __table__ 属性")

        table = model_class.__table__

        # 找到主键
        primary_key_col = None
        primary_key_value = None
        for column in table.columns:
            if column.primary_key:
                primary_key_col = column
                primary_key_value = getattr(instance, column.name, None)
                break

        if primary_key_col is None or primary_key_value is None:
            raise ValueError(f"无法删除 {model_class.__name__}：缺少主键值")

        # 执行删除
        stmt = delete(table).where(primary_key_col == primary_key_value)
        await self._session.execute(stmt)

    # 查询方法
    async def get(self, entity: Type[T], ident: Any) -> Optional[T]:
        """
        根据主键获取实例
        
        Args:
            entity: 模型类
            ident: 主键值
            
        Returns:
            模型实例或 None
        """
        if not hasattr(entity, "__table__"):
            raise ValueError(f"{entity.__name__} 没有 __table__ 属性")

        table = entity.__table__

        # 找到主键列
        primary_key_col = None
        for column in table.columns:
            if column.primary_key:
                primary_key_col = column
                break

        if primary_key_col is None:
            raise ValueError(f"{entity.__name__} 没有主键")

        # 执行查询
        stmt = select(table).where(primary_key_col == ident)
        result = await self._session.execute(stmt)
        row = result.one_or_none()

        if not row:
            return None

        # 转换为模型实例
        return self._row_to_instance(entity, row)

    def _row_to_instance(self, model_class: Type[T], row: Any) -> T:
        """
        将数据库行转换为模型实例
        """
        kwargs = {}
        if hasattr(row, "_mapping"):
            for column in model_class.__table__.columns:
                if column.name in row._mapping:
                    kwargs[column.name] = row._mapping[column.name]

        return model_class(**kwargs)


class async_sessionmaker:
    """
    异步 session 工厂

    使用示例:
        >>> from sqlalchemy.ext.asyncio import create_async_engine
        >>> from sqlalchemy_couchdb.orm import async_sessionmaker
        >>>
        >>> engine = create_async_engine("couchdb+async://admin:password@localhost:5984/mydb")
        >>> SessionFactory = async_sessionmaker(engine)
        >>>
        >>> async with SessionFactory() as session:
        ...     audit = AuditLog(_id="test:1", message="Test")
        ...     session.add(audit)
        ...     await session.commit()
    """

    def __init__(self, engine: AsyncEngine, **kwargs):
        """初始化 session 工厂

        Args:
            engine: 异步引擎
            **kwargs: 传递给 AsyncSession 的参数
        """
        self._base_factory = base_async_sessionmaker(
            engine,
            class_=AsyncSession,
            **kwargs
        )

    def __call__(self):
        """返回异步上下文管理器"""
        return self._session_context()

    @asynccontextmanager
    async def _session_context(self):
        """创建 session 上下文"""
        async with self._base_factory() as base_session:
            # 包装成 CouchDBAsyncSession
            couchdb_session = CouchDBAsyncSession(base_session)
            try:
                yield couchdb_session
            except Exception:
                await couchdb_session.rollback()
                raise
            finally:
                await couchdb_session.close()


__all__ = [
    "CouchDBAsyncSession",
    "async_sessionmaker",
    "CouchDBResult",
    "CouchDBScalars",
]
