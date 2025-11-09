"""
CouchDB Dialect 的 ORM 支持方案

这个示例展示如何使用标准的 declarative 模型，
配合 Connection（而不是 Session）来实现类似 ORM 的功能。

这是一个实用的混合方案，提供了 ORM 的大部分好处。
"""

import asyncio
from typing import Optional, List, Type, TypeVar
from sqlalchemy import Column, String, Integer, select, insert, update, delete
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from sqlalchemy.pool import NullPool

Base = declarative_base()
T = TypeVar('T')

# ============= ORM 模型定义（标准 declarative）=============

class User(Base):
    """用户模型 - 使用标准 SQLAlchemy declarative"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    _id = Column(String)  # CouchDB 内部 ID
    _rev = Column(String)  # CouchDB 版本
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    email = Column(String)

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, age={self.age})>"

    # 业务逻辑方法
    def is_adult(self) -> bool:
        return self.age >= 18


class Tenant(Base):
    """租户模型"""
    __tablename__ = "tenant"

    id = Column(String, primary_key=True)
    _id = Column(String)
    _rev = Column(String)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(Integer, default=1)

    def is_active(self) -> bool:
        return self.status == 1


# ============= 辅助函数：结果映射 =============

def row_to_model(row, model_class: Type[T]) -> T:
    """
    将数据库行转换为模型实例

    参数:
        row: 数据库行（Row 对象）
        model_class: 模型类

    返回:
        模型实例
    """
    if row is None:
        return None

    # 创建模型实例
    instance = model_class()

    # 从 row 填充属性
    for column in model_class.__table__.columns:
        col_name = column.name
        if hasattr(row, col_name):
            setattr(instance, col_name, getattr(row, col_name))

    return instance


def rows_to_models(rows, model_class: Type[T]) -> List[T]:
    """将多行转换为模型列表"""
    return [row_to_model(row, model_class) for row in rows]


# ============= 查询辅助类 =============

class Query:
    """
    查询辅助类 - 提供类似 ORM 的查询接口

    这个类封装了 Connection，提供更方便的查询方法。
    """

    def __init__(self, conn: AsyncConnection, model_class: Type[T]):
        self.conn = conn
        self.model_class = model_class
        self.table = model_class.__table__

    async def get(self, id: str) -> Optional[T]:
        """根据主键获取单个对象"""
        stmt = select(self.model_class).where(self.table.c.id == id)
        result = await self.conn.execute(stmt)
        row = result.fetchone()
        return row_to_model(row, self.model_class)

    async def filter(self, **conditions) -> List[T]:
        """按条件过滤"""
        stmt = select(self.model_class)
        for key, value in conditions.items():
            if hasattr(self.table.c, key):
                stmt = stmt.where(getattr(self.table.c, key) == value)
        result = await self.conn.execute(stmt)
        rows = result.fetchall()
        return rows_to_models(rows, self.model_class)

    async def all(self, limit: int = 100) -> List[T]:
        """获取所有对象"""
        stmt = select(self.model_class).limit(limit)
        result = await self.conn.execute(stmt)
        rows = result.fetchall()
        return rows_to_models(rows, self.model_class)

    async def create(self, **values) -> T:
        """创建新对象"""
        stmt = insert(self.table).values(**values)
        await self.conn.execute(stmt)
        await self.conn.commit()

        # 返回创建的对象
        if 'id' in values:
            return await self.get(values['id'])
        return None

    async def update_by_id(self, id: str, **values) -> Optional[T]:
        """更新对象"""
        stmt = update(self.table).where(
            self.table.c.id == id
        ).values(**values)
        await self.conn.execute(stmt)
        await self.conn.commit()
        return await self.get(id)

    async def delete_by_id(self, id: str) -> bool:
        """删除对象"""
        stmt = delete(self.table).where(self.table.c.id == id)
        result = await self.conn.execute(stmt)
        await self.conn.commit()
        return result.rowcount > 0


# ============= 使用示例 =============

async def example_usage():
    """完整的使用示例"""

    print("=" * 80)
    print("CouchDB Dialect ORM 支持示例")
    print("=" * 80)

    # 创建引擎
    engine = create_async_engine(
        'couchdb+async://admin:123456@localhost:5984/test_db',
        poolclass=NullPool
    )

    try:
        async with engine.connect() as conn:
            # ========== 方式 1：使用标准 select() + 手动映射 ==========
            print("\n【方式 1】标准 select() + 手动映射")
            print("-" * 40)

            # 查询
            stmt = select(User).where(User.age > 25).limit(5)
            result = await conn.execute(stmt)
            rows = result.fetchall()

            # 映射为对象
            users = rows_to_models(rows, User)

            print(f"查询到 {len(users)} 个用户:")
            for user in users:
                print(f"  - {user.name}, {user.age}岁, 成年: {user.is_adult()}")

            # ========== 方式 2：使用 Query 辅助类 ==========
            print("\n【方式 2】使用 Query 辅助类")
            print("-" * 40)

            query = Query(conn, User)

            # 查询所有
            users = await query.all(limit=10)
            print(f"所有用户: {len(users)} 个")

            # 按条件过滤
            adults = await query.filter(age=30)
            print(f"30岁的用户: {len(adults)} 个")

            # 按ID获取
            user = await query.get("user123")
            if user:
                print(f"用户 user123: {user.name}")

            # 创建新用户
            new_user = await query.create(
                id="user:new",
                name="New User",
                age=25,
                email="new@example.com"
            )
            if new_user:
                print(f"✅ 创建用户: {new_user.name}")

            # 更新用户
            updated_user = await query.update_by_id(
                "user:new",
                age=26
            )
            if updated_user:
                print(f"✅ 更新用户年龄: {updated_user.age}")

            # ========== 方式 3：租户示例 ==========
            print("\n【方式 3】租户模型示例")
            print("-" * 40)

            tenant_query = Query(conn, Tenant)

            # 创建租户
            tenant = await tenant_query.create(
                id="tenant:001",
                code="ACME",
                name="ACME 公司",
                status=1
            )
            if tenant:
                print(f"✅ 创建租户: {tenant.name}")
                print(f"   状态: {'启用' if tenant.is_active() else '禁用'}")

            # 查询租户
            tenants = await tenant_query.filter(status=1)
            print(f"✅ 启用的租户: {len(tenants)} 个")

            print("\n" + "=" * 80)
            print("✅ 所有示例完成！")
            print("=" * 80)

    finally:
        await engine.dispose()


# ============= 对比说明 =============

"""
这个混合方案的优缺点：

【优点】✅
1. 可以使用标准 declarative 模型（类型提示、IDE 支持）
2. 可以使用 select() 查询语法
3. 可以在模型中添加业务逻辑方法
4. 性能优秀（基于 Connection，无 Session 开销）
5. 代码清晰，易于理解

【限制】⚠️
1. 不支持 Session.add() / Session.commit() 模式
2. 不支持对象状态跟踪
3. 不支持延迟加载（lazy loading）
4. 不支持级联操作
5. 不支持关系（relationship）

【与标准 ORM 的对比】

标准 ORM (Session):
```python
session = Session(engine)
user = User(name="Alice", age=30)
session.add(user)
session.commit()

user = session.get(User, "user123")
user.age = 31
session.commit()
```

我们的方案 (Connection + Query):
```python
async with engine.connect() as conn:
    query = Query(conn, User)
    user = await query.create(id="user123", name="Alice", age=30)
    user = await query.update_by_id("user123", age=31)
```

【推荐使用场景】
- ✅ CRUD 操作为主的应用
- ✅ 不需要复杂关系的场景
- ✅ 性能要求高的场景
- ✅ 与 CouchDB 的文档特性匹配的场景
"""

if __name__ == "__main__":
    asyncio.run(example_usage())
