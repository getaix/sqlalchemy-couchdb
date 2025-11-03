"""
SQLAlchemy-CouchDB 异步模式使用示例

演示如何使用 SQLAlchemy 的异步引擎操作 CouchDB 数据库。

要求:
    - Python 3.8+
    - SQLAlchemy 2.0+
    - CouchDB 3.0+
    - httpx (异步 HTTP 客户端)

运行:
    python examples/async_example.py
"""

import asyncio
from sqlalchemy import Column, Integer, String, MetaData, Table, select, insert, update, delete
from sqlalchemy.ext.asyncio import create_async_engine


async def basic_crud_example():
    """基本 CRUD 操作示例"""
    print("=" * 60)
    print("示例 1: 基本 CRUD 操作")
    print("=" * 60)

    # 创建异步引擎
    engine = create_async_engine(
        "couchdb+async://admin:password@localhost:5984/test_db",
        echo=False,  # 设置为 True 可以看到 SQL 日志
    )

    # 定义表结构
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("_id", String, primary_key=True),
        Column("_rev", String),
        Column("name", String(50)),
        Column("age", Integer),
        Column("email", String(100)),
    )

    async with engine.connect() as conn:
        # 1. INSERT - 插入数据
        print("\n1. 插入用户 Alice...")
        stmt = insert(users).values(name="Alice", age=30, email="alice@example.com")
        result = await conn.execute(stmt)
        await conn.commit()
        print(f"   插入成功，影响行数: {result.rowcount}")

        # 2. SELECT - 查询数据
        print("\n2. 查询用户 Alice...")
        stmt = select(users).where(users.c.name == "Alice")
        result = await conn.execute(stmt)

        # 注意：fetchone() 是同步的（结果已在 execute 时缓存）
        row = result.fetchone()
        if row:
            print(f"   找到用户: {row.name}, 年龄: {row.age}, 邮箱: {row.email}")

        # 3. UPDATE - 更新数据
        print("\n3. 更新 Alice 的年龄为 31...")
        stmt = update(users).where(users.c.name == "Alice").values(age=31)
        result = await conn.execute(stmt)
        await conn.commit()
        print(f"   更新成功，影响行数: {result.rowcount}")

        # 验证更新
        stmt = select(users).where(users.c.name == "Alice")
        result = await conn.execute(stmt)
        row = result.fetchone()
        print(f"   更新后的年龄: {row.age}")

        # 4. DELETE - 删除数据
        print("\n4. 删除用户 Alice...")
        stmt = delete(users).where(users.c.name == "Alice")
        result = await conn.execute(stmt)
        await conn.commit()
        print(f"   删除成功，影响行数: {result.rowcount}")

    await engine.dispose()
    print("\n✅ 基本 CRUD 操作完成！\n")


async def query_features_example():
    """查询功能示例"""
    print("=" * 60)
    print("示例 2: 高级查询功能")
    print("=" * 60)

    engine = create_async_engine(
        "couchdb+async://admin:password@localhost:5984/test_db", echo=False
    )

    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("_id", String, primary_key=True),
        Column("_rev", String),
        Column("name", String(50)),
        Column("age", Integer),
    )

    async with engine.connect() as conn:
        # 插入测试数据
        print("\n准备测试数据...")
        test_users = [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": 30},
            {"name": "Carol", "age": 28},
            {"name": "David", "age": 35},
        ]

        for user in test_users:
            stmt = insert(users).values(**user)
            await conn.execute(stmt)
        await conn.commit()
        print("   插入了 4 个用户")

        # WHERE 子句
        print("\n1. WHERE 子句 - 查询年龄 > 27 的用户...")
        stmt = select(users).where(users.c.age > 27)
        result = await conn.execute(stmt)

        rows = result.fetchall()
        print(f"   找到 {len(rows)} 个用户:")
        for row in rows:
            print(f"     - {row.name}: {row.age} 岁")

        # ORDER BY 排序
        print("\n2. ORDER BY - 按年龄降序排列...")
        stmt = select(users).order_by(users.c.age.desc())
        result = await conn.execute(stmt)

        rows = result.fetchall()
        print("   排序结果:")
        for row in rows:
            print(f"     - {row.name}: {row.age} 岁")

        # LIMIT 限制
        print("\n3. LIMIT - 只获取前 2 条记录...")
        stmt = select(users).limit(2)
        result = await conn.execute(stmt)

        rows = result.fetchall()
        print(f"   获取了 {len(rows)} 条记录:")
        for row in rows:
            print(f"     - {row.name}: {row.age} 岁")

        # 迭代结果（同步迭代，因为结果已缓存）
        print("\n4. 迭代所有用户...")
        stmt = select(users)
        result = await conn.execute(stmt)

        count = 0
        for row in result:  # 同步迭代
            count += 1
        print(f"   共迭代了 {count} 个用户")

        # 清理数据
        stmt = delete(users)
        await conn.execute(stmt)
        await conn.commit()

    await engine.dispose()
    print("\n✅ 查询功能演示完成！\n")


async def concurrent_operations_example():
    """并发操作示例"""
    print("=" * 60)
    print("示例 3: 并发操作")
    print("=" * 60)

    engine = create_async_engine(
        "couchdb+async://admin:password@localhost:5984/test_db", echo=False
    )

    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("_id", String, primary_key=True),
        Column("_rev", String),
        Column("name", String(50)),
        Column("age", Integer),
    )

    # 并发插入
    async def insert_user(conn, name, age):
        """插入单个用户"""
        stmt = insert(users).values(name=name, age=age)
        result = await conn.execute(stmt)
        await conn.commit()
        return result.rowcount

    print("\n1. 并发插入 5 个用户...")
    async with engine.connect() as conn:
        tasks = [insert_user(conn, f"User{i}", 20 + i) for i in range(5)]

        results = await asyncio.gather(*tasks)
        print(f"   插入成功，共 {sum(results)} 条记录")

    # 并发查询
    async def query_users_by_age(age_threshold):
        """查询年龄大于阈值的用户"""
        async with engine.connect() as conn:
            stmt = select(users).where(users.c.age > age_threshold)
            result = await conn.execute(stmt)
            rows = result.fetchall()
            return len(rows)

    print("\n2. 并发执行 3 个查询...")
    tasks = [query_users_by_age(20), query_users_by_age(22), query_users_by_age(24)]

    results = await asyncio.gather(*tasks)
    print(f"   年龄 > 20: {results[0]} 人")
    print(f"   年龄 > 22: {results[1]} 人")
    print(f"   年龄 > 24: {results[2]} 人")

    # 清理数据
    async with engine.connect() as conn:
        stmt = delete(users)
        await conn.execute(stmt)
        await conn.commit()

    await engine.dispose()
    print("\n✅ 并发操作演示完成！\n")


async def connection_management_example():
    """连接管理示例"""
    print("=" * 60)
    print("示例 4: 连接管理")
    print("=" * 60)

    engine = create_async_engine(
        "couchdb+async://admin:password@localhost:5984/test_db", echo=False
    )

    # 使用上下文管理器
    print("\n1. 使用异步上下文管理器...")
    async with engine.connect() as conn:
        print("   连接已打开")

        # 检查连接
        raw_conn = await conn.get_raw_connection()
        is_alive = await raw_conn.driver_connection.client.ping()
        print(f"   连接状态: {'✅ 活跃' if is_alive else '❌ 断开'}")

    print("   连接已关闭")

    # 事务（虽然 CouchDB 自动提交）
    print("\n2. 事务操作（CouchDB 自动提交）...")
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("name", String(50)),
        Column("age", Integer),
    )

    async with engine.connect() as conn:
        stmt = insert(users).values(name="Test", age=25)
        await conn.execute(stmt)
        await conn.commit()  # 虽然不需要，但应该不报错
        print("   事务提交成功")

        # 清理
        stmt = delete(users).where(users.c.name == "Test")
        await conn.execute(stmt)
        await conn.commit()

    await engine.dispose()
    print("\n✅ 连接管理演示完成！\n")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("SQLAlchemy-CouchDB 异步模式示例")
    print("=" * 60)
    print("\n注意：请确保 CouchDB 服务正在运行")
    print("连接信息: localhost:5984")
    print("数据库: test_db")
    print("用户名: admin")
    print("密码: password\n")

    try:
        # 运行所有示例
        await basic_crud_example()
        await query_features_example()
        await concurrent_operations_example()
        await connection_management_example()

        print("=" * 60)
        print("所有示例运行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请检查:")
        print("  1. CouchDB 服务是否运行")
        print("  2. 数据库 test_db 是否存在")
        print("  3. 用户名和密码是否正确")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
