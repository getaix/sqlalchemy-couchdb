"""
异步模式使用示例

演示如何使用 SQLAlchemy CouchDB Dialect 进行异步数据库操作。
"""

import asyncio
from sqlalchemy import MetaData, Table, Column, Integer, String, select, insert, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# ==================== 1. 创建异步引擎 ====================

# 注意: URL 使用 couchdb+async:// 而不是 couchdb://
engine = create_async_engine("couchdb+async://admin:123456@localhost:5984/test_db")

print("✓ 异步引擎创建成功")


# ==================== 2. 定义表结构 ====================

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50), nullable=False),
    Column("age", Integer),
    Column("email", String(100)),
)

print("✓ 表结构定义完成")


# ==================== 3. 异步操作函数 ====================


async def test_connection():
    """测试数据库连接"""
    print("\n--- 测试连接 ---")

    try:
        async with engine.connect() as conn:
            # 执行 PING 检查连接
            cursor = conn.connection.cursor()
            await cursor.execute("PING")
            print("✓ 数据库连接成功")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        raise


async def insert_data():
    """INSERT 操作"""
    print("\n--- INSERT 操作 ---")

    async with engine.connect() as conn:
        # 插入单条记录
        stmt = insert(users).values(name="Alice", age=30, email="alice@example.com")

        result = await conn.execute(stmt)
        await conn.commit()

        print(f"✓ 插入成功，影响行数: {result.rowcount}")


async def select_data():
    """SELECT 操作"""
    print("\n--- SELECT 操作 ---")

    async with engine.connect() as conn:
        # 查询所有用户
        stmt = select(users)
        result = await conn.execute(stmt)

        print("所有用户:")
        async for row in result:
            print(f"  - {row.name}, {row.age}岁, {row.email}")

        # 带条件的查询
        stmt = select(users).where(users.c.age > 25)
        result = await conn.execute(stmt)

        print("\n年龄 > 25 的用户:")
        rows = await result.fetchall()
        for row in rows:
            print(f"  - {row.name}, {row.age}岁")

        # 带排序和限制
        stmt = select(users).order_by(users.c.age.desc()).limit(10)
        result = await conn.execute(stmt)

        print("\n按年龄降序排列（前10条）:")
        async for row in result:
            print(f"  - {row.name}, {row.age}岁")


async def update_data():
    """UPDATE 操作"""
    print("\n--- UPDATE 操作 ---")

    async with engine.connect() as conn:
        stmt = update(users).where(users.c.name == "Alice").values(age=31)

        result = await conn.execute(stmt)
        await conn.commit()

        print(f"✓ 更新成功，影响行数: {result.rowcount}")


async def delete_data():
    """DELETE 操作"""
    print("\n--- DELETE 操作 ---")

    async with engine.connect() as conn:
        stmt = delete(users).where(users.c.age < 18)

        result = await conn.execute(stmt)
        await conn.commit()

        print(f"✓ 删除成功，影响行数: {result.rowcount}")


async def use_session():
    """使用 AsyncSession"""
    print("\n--- AsyncSession 操作 ---")

    async with AsyncSession(engine) as session:
        # 查询
        stmt = select(users).where(users.c.name == "Alice")
        result = await session.execute(stmt)

        user = result.fetchone()
        if user:
            print(f"✓ 找到用户: {user.name}, {user.age}岁")

        # 提交
        await session.commit()


async def batch_operations():
    """批量操作"""
    print("\n--- 批量操作 ---")

    async with engine.connect() as conn:
        # 批量插入
        stmt = insert(users)

        await conn.execute(
            stmt,
            [
                {"name": "Bob", "age": 25, "email": "bob@example.com"},
                {"name": "Carol", "age": 28, "email": "carol@example.com"},
                {"name": "Dave", "age": 35, "email": "dave@example.com"},
            ],
        )

        await conn.commit()
        print("✓ 批量插入完成")


async def error_handling():
    """错误处理"""
    print("\n--- 错误处理 ---")

    from sqlalchemy_couchdb.exceptions import CouchDBError, OperationalError

    try:
        async with engine.connect() as conn:
            # 尝试执行一个可能失败的操作
            stmt = select(users).where(users.c.age.is_(None))
            await conn.execute(stmt)

    except OperationalError as e:
        print(f"✗ 操作错误: {e}")
    except CouchDBError as e:
        print(f"✗ CouchDB 错误: {e}")
    except Exception as e:
        print(f"✗ 未知错误: {e}")
    else:
        print("✓ 操作成功")


async def concurrent_operations():
    """并发操作示例"""
    print("\n--- 并发操作 ---")

    # 同时执行多个查询
    async with engine.connect() as conn:
        tasks = [
            conn.execute(select(users).where(users.c.age > 20)),
            conn.execute(select(users).where(users.c.age > 30)),
            conn.execute(select(users).where(users.c.age > 40)),
        ]

        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            rows = await result.fetchall()
            print(f"  查询 {i+1}: 返回 {len(rows)} 行")


# ==================== 4. 主函数 ====================


async def main():
    """主函数，执行所有示例"""
    print("=== SQLAlchemy CouchDB 异步模式示例 ===\n")

    try:
        # 测试连接
        await test_connection()

        # INSERT
        await insert_data()

        # SELECT
        await select_data()

        # UPDATE
        await update_data()

        # DELETE
        await delete_data()

        # Session
        await use_session()

        # 批量操作
        await batch_operations()

        # 错误处理
        await error_handling()

        # 并发操作
        await concurrent_operations()

    finally:
        # 关闭引擎
        await engine.dispose()
        print("\n✓ 引擎已关闭")


# ==================== 5. 运行 ====================

if __name__ == "__main__":
    # Python 3.11+ 推荐使用 asyncio.run()
    asyncio.run(main())
