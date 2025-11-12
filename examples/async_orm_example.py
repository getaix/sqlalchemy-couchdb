"""
异步 ORM 使用示例

演示如何使用 CouchDB 异步 ORM，包括：
1. 创建异步引擎和 session
2. 使用 ORM 进行 CRUD 操作
3. Event 系统（before_insert, before_update）
4. 异步查询
"""

import asyncio
import time
from sqlalchemy import Column, String, Integer, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from sqlalchemy_couchdb.orm import declarative_base, async_sessionmaker

# 创建 Base
Base = declarative_base()


# 定义模型
class User(Base):
    __tablename__ = "users"

    _id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    email = Column(String)

    # 审计字段
    creator_name = Column(String)
    creator_id = Column(String)
    updater_name = Column(String)
    updater_id = Column(String)


# 注册 Event 监听器
@event.listens_for(User, "before_insert", propagate=True)
def set_created_info(mapper, connection, target):
    """在插入前设置创建人信息"""
    # 模拟获取当前用户信息
    target.creator_name = "System"
    target.creator_id = "system-001"
    target.updater_name = "System"
    target.updater_id = "system-001"
    print(f"   [Event] before_insert: 设置 creator_name={target.creator_name}")


@event.listens_for(User, "before_update", propagate=True)
def set_updated_info(mapper, connection, target):
    """在更新前设置更新人信息"""
    target.updater_name = "Admin"
    target.updater_id = "admin-001"
    print(f"   [Event] before_update: 设置 updater_name={target.updater_name}")


async def main():
    """
    主函数：演示异步 ORM 使用
    """
    print("\n" + "="*80)
    print("CouchDB 异步 ORM 示例")
    print("="*80)

    # 1. 创建异步引擎
    print("\n🔧 步骤1：创建异步引擎")
    engine = create_async_engine(
        "couchdb+async://admin:123456@localhost:5984/test_db",
        poolclass=NullPool,
        echo=False
    )
    print("   ✅ 异步引擎创建成功")

    # 2. 创建 session 工厂
    print("\n🔧 步骤2：创建 Session 工厂")
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)
    print("   ✅ Session 工厂创建成功")

    # 3. 使用 ORM 插入数据（会触发 before_insert event）
    print("\n📝 步骤3：使用 ORM 插入数据")
    async with SessionFactory() as session:
        # 创建用户对象
        unique_id = f"user:{int(time.time() * 1000)}"
        user = User(
            _id=unique_id,
            name="Alice",
            age=30,
            email="alice@example.com"
        )
        print(f"   创建对象: User(id={unique_id}, name=Alice)")
        print(f"   插入前 creator_name: {user.creator_name}")

        # 添加到 session
        session.add(user)

        # 提交（触发 before_insert event）
        await session.commit()

        print(f"   插入后 creator_name: {user.creator_name}")
        print("   ✅ 插入成功")

        # 等待 CouchDB 索引
        await asyncio.sleep(0.3)

    # 4. 查询数据
    print("\n🔍 步骤4：查询数据")
    async with SessionFactory() as session:
        user = await session.get(User, unique_id)
        if user:
            print(f"   找到用户: {user.name} (age={user.age}, email={user.email})")
            print(f"   创建人: {user.creator_name}")
            print("   ✅ 查询成功")
        else:
            print("   ❌ 未找到用户")

    # 5. 更新数据（会触发 before_update event）
    print("\n✏️ 步骤5：更新数据")
    async with SessionFactory() as session:
        user = await session.get(User, unique_id)
        if user:
            print(f"   更新前 updater_name: {user.updater_name}")

            # 修改属性
            user.age = 31
            user.email = "alice.new@example.com"

            # 标记为 dirty（需要更新）
            session._dirty_instances.append(user)

            # 提交（触发 before_update event）
            await session.commit()

            print(f"   更新后 updater_name: {user.updater_name}")
            print("   ✅ 更新成功")

    # 6. 删除数据
    print("\n🗑️ 步骤6：删除数据")
    async with SessionFactory() as session:
        user = await session.get(User, unique_id)
        if user:
            session.delete(user)
            await session.commit()
            print("   ✅ 删除成功")

    # 7. 验证删除
    print("\n🔍 步骤7：验证删除")
    async with SessionFactory() as session:
        user = await session.get(User, unique_id)
        if user:
            print("   ❌ 数据仍然存在")
        else:
            print("   ✅ 数据已删除")

    print("\n" + "="*80)
    print("✅ 所有测试完成！")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
