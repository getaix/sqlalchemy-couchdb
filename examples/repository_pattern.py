"""
Repository 模式示例 - 在 Core API 基础上构建优雅的数据访问层

这个示例展示如何使用 Repository 模式封装 Core API，
获得接近 ORM 的开发体验，同时保持性能优势。
"""

from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field
from sqlalchemy import Table, Column, String, Integer, MetaData, select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from datetime import datetime

# ============= 业务模型（Pydantic）=============

class UserModel(BaseModel):
    """用户业务模型 - 带类型提示和验证"""
    id: str = Field(default="", description="用户ID")
    _id: Optional[str] = Field(default=None, description="CouchDB 内部ID")
    _rev: Optional[str] = Field(default=None, description="CouchDB 版本")
    name: str = Field(..., min_length=1, max_length=50, description="用户名")
    age: int = Field(..., ge=0, le=150, description="年龄")
    email: str = Field(..., description="邮箱")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # 允许从 ORM 对象创建

    # 业务逻辑方法
    def is_adult(self) -> bool:
        """是否成年"""
        return self.age >= 18

    def get_display_name(self) -> str:
        """显示名称"""
        return f"{self.name} ({self.age}岁)"


class TenantModel(BaseModel):
    """租户业务模型"""
    id: str = Field(default="", description="租户ID")
    _id: Optional[str] = None
    _rev: Optional[str] = None
    code: str = Field(..., min_length=1, max_length=50, description="租户编码")
    name: str = Field(..., min_length=1, max_length=100, description="租户名称")
    status: int = Field(default=1, description="状态：0=禁用，1=启用")

    def is_active(self) -> bool:
        """是否启用"""
        return self.status == 1


# ============= 表定义（Core API）=============

metadata = MetaData()

users_table = Table(
    'users',
    metadata,
    Column('id', String, primary_key=True),
    Column('_id', String),
    Column('_rev', String),
    Column('name', String),
    Column('age', Integer),
    Column('email', String),
)

tenants_table = Table(
    'tenant',
    metadata,
    Column('id', String, primary_key=True),
    Column('_id', String),
    Column('_rev', String),
    Column('code', String),
    Column('name', String),
    Column('status', Integer),
)


# ============= Repository 基类 =============

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
    """Repository 基类 - 提供通用的 CRUD 操作"""

    def __init__(self, engine: AsyncEngine, table: Table, model_class: type[T]):
        self.engine = engine
        self.table = table
        self.model_class = model_class

    def _row_to_model(self, row) -> T:
        """将数据库行转换为业务模型"""
        if row is None:
            return None
        return self.model_class(**row._asdict())

    async def get_by_id(self, id: str) -> Optional[T]:
        """根据ID获取单条记录"""
        async with self.engine.connect() as conn:
            stmt = select(self.table).where(self.table.c.id == id)
            result = await conn.execute(stmt)
            row = result.fetchone()
            return self._row_to_model(row)

    async def list_all(self, limit: int = 100) -> List[T]:
        """获取所有记录"""
        async with self.engine.connect() as conn:
            stmt = select(self.table).limit(limit)
            result = await conn.execute(stmt)
            rows = result.fetchall()
            return [self._row_to_model(row) for row in rows]

    async def find_by(self, **filters) -> List[T]:
        """按条件查询"""
        async with self.engine.connect() as conn:
            stmt = select(self.table)
            # 动态添加过滤条件
            for key, value in filters.items():
                if hasattr(self.table.c, key):
                    stmt = stmt.where(getattr(self.table.c, key) == value)
            result = await conn.execute(stmt)
            rows = result.fetchall()
            return [self._row_to_model(row) for row in rows]

    async def create(self, model: T) -> T:
        """创建记录"""
        async with self.engine.connect() as conn:
            # 转换为字典，排除 None 值
            data = model.model_dump(exclude_none=True, exclude={'_id', '_rev'})
            stmt = insert(self.table).values(**data)
            await conn.execute(stmt)
            await conn.commit()
            return model

    async def update(self, id: str, **updates) -> Optional[T]:
        """更新记录"""
        async with self.engine.connect() as conn:
            stmt = update(self.table).where(
                self.table.c.id == id
            ).values(**updates)
            await conn.execute(stmt)
            await conn.commit()
            return await self.get_by_id(id)

    async def delete(self, id: str) -> bool:
        """删除记录"""
        async with self.engine.connect() as conn:
            stmt = delete(self.table).where(self.table.c.id == id)
            result = await conn.execute(stmt)
            await conn.commit()
            return result.rowcount > 0

    async def count(self) -> int:
        """统计记录数"""
        async with self.engine.connect() as conn:
            stmt = select(self.table)
            result = await conn.execute(stmt)
            return len(result.fetchall())


# ============= 具体 Repository =============

class UserRepository(BaseRepository[UserModel]):
    """用户仓储 - 扩展特定业务方法"""

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine, users_table, UserModel)

    async def find_adults(self) -> List[UserModel]:
        """查找成年用户"""
        async with self.engine.connect() as conn:
            stmt = select(self.table).where(self.table.c.age >= 18)
            result = await conn.execute(stmt)
            rows = result.fetchall()
            return [self._row_to_model(row) for row in rows]

    async def find_by_name(self, name: str) -> List[UserModel]:
        """按姓名查找"""
        return await self.find_by(name=name)

    async def find_by_email(self, email: str) -> Optional[UserModel]:
        """按邮箱查找（唯一）"""
        users = await self.find_by(email=email)
        return users[0] if users else None

    async def update_age(self, id: str, new_age: int) -> Optional[UserModel]:
        """更新年龄"""
        return await self.update(id, age=new_age)


class TenantRepository(BaseRepository[TenantModel]):
    """租户仓储"""

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine, tenants_table, TenantModel)

    async def find_active(self) -> List[TenantModel]:
        """查找启用的租户"""
        return await self.find_by(status=1)

    async def find_by_code(self, code: str) -> Optional[TenantModel]:
        """按编码查找"""
        tenants = await self.find_by(code=code)
        return tenants[0] if tenants else None

    async def activate(self, id: str) -> Optional[TenantModel]:
        """启用租户"""
        return await self.update(id, status=1)

    async def deactivate(self, id: str) -> Optional[TenantModel]:
        """禁用租户"""
        return await self.update(id, status=0)


# ============= 服务层（可选）=============

class UserService:
    """用户服务 - 处理业务逻辑"""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register_user(self, name: str, age: int, email: str) -> UserModel:
        """注册新用户"""
        # 检查邮箱是否已存在
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ValueError(f"邮箱 {email} 已被使用")

        # 创建用户
        user = UserModel(
            id=f"user:{email}",  # 使用邮箱作为ID
            name=name,
            age=age,
            email=email
        )
        return await self.user_repo.create(user)

    async def get_adult_users(self) -> List[UserModel]:
        """获取所有成年用户"""
        return await self.user_repo.find_adults()


# ============= 使用示例 =============

async def main():
    """使用示例"""

    # 创建引擎
    engine = create_async_engine(
        'couchdb+async://admin:123456@localhost:5984/test_db',
        poolclass=NullPool
    )

    # 创建仓储
    user_repo = UserRepository(engine)
    tenant_repo = TenantRepository(engine)

    try:
        # ========== 用户操作 ==========
        print("=" * 50)
        print("用户操作示例")
        print("=" * 50)

        # 1. 创建用户
        user = UserModel(
            id="user:alice",
            name="Alice",
            age=30,
            email="alice@example.com"
        )
        created_user = await user_repo.create(user)
        print(f"✅ 创建用户: {created_user.get_display_name()}")

        # 2. 查询用户
        found_user = await user_repo.get_by_id("user:alice")
        if found_user:
            print(f"✅ 查询用户: {found_user.name}")
            print(f"   是否成年: {found_user.is_adult()}")

        # 3. 更新用户
        updated_user = await user_repo.update_age("user:alice", 31)
        if updated_user:
            print(f"✅ 更新年龄: {updated_user.age}")

        # 4. 查询成年用户
        adults = await user_repo.find_adults()
        print(f"✅ 成年用户数量: {len(adults)}")

        # 5. 按邮箱查找
        user_by_email = await user_repo.find_by_email("alice@example.com")
        if user_by_email:
            print(f"✅ 按邮箱查找: {user_by_email.name}")

        # ========== 租户操作 ==========
        print("\n" + "=" * 50)
        print("租户操作示例")
        print("=" * 50)

        # 1. 创建租户
        tenant = TenantModel(
            id="tenant:001",
            code="ACME",
            name="ACME 公司",
            status=1
        )
        created_tenant = await tenant_repo.create(tenant)
        print(f"✅ 创建租户: {created_tenant.name}")

        # 2. 查询启用的租户
        active_tenants = await tenant_repo.find_active()
        print(f"✅ 启用的租户数量: {len(active_tenants)}")
        for t in active_tenants:
            print(f"   - {t.name} ({'启用' if t.is_active() else '禁用'})")

        # 3. 禁用租户
        await tenant_repo.deactivate("tenant:001")
        print(f"✅ 已禁用租户")

        # ========== 使用服务层 ==========
        print("\n" + "=" * 50)
        print("服务层示例")
        print("=" * 50)

        user_service = UserService(user_repo)

        try:
            # 注册新用户
            new_user = await user_service.register_user(
                name="Bob",
                age=25,
                email="bob@example.com"
            )
            print(f"✅ 注册用户: {new_user.name}")
        except ValueError as e:
            print(f"❌ 注册失败: {e}")

        # 获取成年用户
        adults = await user_service.get_adult_users()
        print(f"✅ 成年用户: {len(adults)} 人")

        print("\n" + "=" * 50)
        print("✅ 所有操作完成！")
        print("=" * 50)

    finally:
        await engine.dispose()


# ============= 优点总结 =============

"""
这种 Repository 模式的优点：

1. ✅ **类型安全**：Pydantic 模型提供完整类型提示
2. ✅ **业务逻辑**：模型中可以添加业务方法
3. ✅ **易于测试**：Repository 可以轻松 mock
4. ✅ **性能优秀**：底层使用 Core API，无 ORM 开销
5. ✅ **灵活扩展**：可以轻松添加自定义查询方法
6. ✅ **依赖注入**：方便集成到 FastAPI 等框架

对比标准 ORM：
- 性能：✅ 更好（无 ORM 开销）
- 灵活性：✅ 更好（可自由组合查询）
- 学习成本：✅ 更低（概念更少）
- 代码量：⚠️  稍多（需要手动写 Repository）
- 关系处理：❌ 需要手动处理（但 CouchDB 本身就不适合关系）

推荐用于：
- CouchDB 项目（文档数据库特性）
- 高性能要求的项目
- 需要灵活查询的项目
- 微服务架构（每个服务独立的 Repository）
"""

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
