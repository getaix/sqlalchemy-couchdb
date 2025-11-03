"""
SQLAlchemy-CouchDB 性能对比测试

对比同步模式和异步模式的性能差异。

要求:
    - Python 3.8+
    - SQLAlchemy 2.0+
    - CouchDB 3.0+

运行:
    python examples/performance_benchmark.py
"""

import asyncio
import time

from sqlalchemy import (
    Column,
    Integer,
    String,
    MetaData,
    Table,
    select,
    insert,
    delete,
    create_engine,
)
from sqlalchemy.ext.asyncio import create_async_engine


# 测试配置
SYNC_URL = "couchdb://admin:password@localhost:5984/test_db"
ASYNC_URL = "couchdb+async://admin:password@localhost:5984/test_db"
NUM_RECORDS = 100  # 测试记录数


def create_users_table():
    """创建用户表定义"""
    metadata = MetaData()
    return Table(
        "benchmark_users",
        metadata,
        Column("_id", String, primary_key=True),
        Column("_rev", String),
        Column("name", String(50)),
        Column("age", Integer),
        Column("email", String(100)),
    )


def benchmark_sync_insert(num_records: int) -> float:
    """基准测试：同步插入"""
    print(f"\n📊 同步模式 - 插入 {num_records} 条记录...")

    engine = create_engine(SYNC_URL, echo=False)
    users = create_users_table()

    start_time = time.perf_counter()

    with engine.connect() as conn:
        for i in range(num_records):
            stmt = insert(users).values(
                name=f"User{i}", age=20 + (i % 50), email=f"user{i}@example.com"
            )
            conn.execute(stmt)
        conn.commit()

    elapsed = time.perf_counter() - start_time
    ops_per_sec = num_records / elapsed if elapsed > 0 else 0

    print(f"   ✅ 完成：{elapsed:.3f}秒")
    print(f"   ⚡ 速度：{ops_per_sec:.2f} ops/s")

    engine.dispose()
    return elapsed


async def benchmark_async_insert(num_records: int) -> float:
    """基准测试：异步插入"""
    print(f"\n📊 异步模式 - 插入 {num_records} 条记录...")

    engine = create_async_engine(ASYNC_URL, echo=False)
    users = create_users_table()

    start_time = time.perf_counter()

    async with engine.connect() as conn:
        for i in range(num_records):
            stmt = insert(users).values(
                name=f"User{i}", age=20 + (i % 50), email=f"user{i}@example.com"
            )
            await conn.execute(stmt)
        await conn.commit()

    elapsed = time.perf_counter() - start_time
    ops_per_sec = num_records / elapsed if elapsed > 0 else 0

    print(f"   ✅ 完成：{elapsed:.3f}秒")
    print(f"   ⚡ 速度：{ops_per_sec:.2f} ops/s")

    await engine.dispose()
    return elapsed


def benchmark_sync_select(num_queries: int) -> float:
    """基准测试：同步查询"""
    print(f"\n📊 同步模式 - 执行 {num_queries} 次查询...")

    engine = create_engine(SYNC_URL, echo=False)
    users = create_users_table()

    start_time = time.perf_counter()

    with engine.connect() as conn:
        for i in range(num_queries):
            age = 20 + (i % 50)
            stmt = select(users).where(users.c.age == age)
            result = conn.execute(stmt)
            _ = result.fetchall()

    elapsed = time.perf_counter() - start_time
    ops_per_sec = num_queries / elapsed if elapsed > 0 else 0

    print(f"   ✅ 完成：{elapsed:.3f}秒")
    print(f"   ⚡ 速度：{ops_per_sec:.2f} ops/s")

    engine.dispose()
    return elapsed


async def benchmark_async_select(num_queries: int) -> float:
    """基准测试：异步查询"""
    print(f"\n📊 异步模式 - 执行 {num_queries} 次查询...")

    engine = create_async_engine(ASYNC_URL, echo=False)
    users = create_users_table()

    start_time = time.perf_counter()

    async with engine.connect() as conn:
        for i in range(num_queries):
            age = 20 + (i % 50)
            stmt = select(users).where(users.c.age == age)
            result = await conn.execute(stmt)
            _ = result.fetchall()

    elapsed = time.perf_counter() - start_time
    ops_per_sec = num_queries / elapsed if elapsed > 0 else 0

    print(f"   ✅ 完成：{elapsed:.3f}秒")
    print(f"   ⚡ 速度：{ops_per_sec:.2f} ops/s")

    await engine.dispose()
    return elapsed


async def benchmark_async_concurrent_queries(num_queries: int, concurrency: int) -> float:
    """基准测试：异步并发查询"""
    print(f"\n📊 异步模式 - 并发执行 {num_queries} 次查询（并发度={concurrency}）...")

    engine = create_async_engine(ASYNC_URL, echo=False)
    users = create_users_table()

    async def query_batch(conn, start, end):
        """执行一批查询"""
        for i in range(start, end):
            age = 20 + (i % 50)
            stmt = select(users).where(users.c.age == age)
            result = await conn.execute(stmt)
            _ = result.fetchall()

    start_time = time.perf_counter()

    async with engine.connect() as conn:
        batch_size = num_queries // concurrency
        tasks = []
        for i in range(concurrency):
            start_idx = i * batch_size
            end_idx = start_idx + batch_size if i < concurrency - 1 else num_queries
            tasks.append(query_batch(conn, start_idx, end_idx))

        await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start_time
    ops_per_sec = num_queries / elapsed if elapsed > 0 else 0

    print(f"   ✅ 完成：{elapsed:.3f}秒")
    print(f"   ⚡ 速度：{ops_per_sec:.2f} ops/s")

    await engine.dispose()
    return elapsed


def cleanup_data():
    """清理测试数据"""
    print("\n🧹 清理测试数据...")
    engine = create_engine(SYNC_URL, echo=False)
    users = create_users_table()

    with engine.connect() as conn:
        stmt = delete(users)
        result = conn.execute(stmt)
        conn.commit()
        print(f"   ✅ 清理了 {result.rowcount} 条记录")

    engine.dispose()


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("SQLAlchemy-CouchDB 性能基准测试")
    print("=" * 70)
    print("\n测试配置:")
    print(f"  - 记录数: {NUM_RECORDS}")
    print(f"  - 同步 URL: {SYNC_URL}")
    print(f"  - 异步 URL: {ASYNC_URL}")

    results = {}

    try:
        # 1. 插入性能测试
        print("\n" + "-" * 70)
        print("测试 1: 插入性能")
        print("-" * 70)

        sync_insert_time = benchmark_sync_insert(NUM_RECORDS)
        results["sync_insert"] = sync_insert_time

        # 清理数据
        cleanup_data()

        async_insert_time = await benchmark_async_insert(NUM_RECORDS)
        results["async_insert"] = async_insert_time

        # 2. 查询性能测试
        print("\n" + "-" * 70)
        print("测试 2: 查询性能")
        print("-" * 70)

        sync_select_time = benchmark_sync_select(50)
        results["sync_select"] = sync_select_time

        async_select_time = await benchmark_async_select(50)
        results["async_select"] = async_select_time

        # 3. 并发查询性能测试（仅异步）
        print("\n" + "-" * 70)
        print("测试 3: 并发查询性能")
        print("-" * 70)

        async_concurrent_time = await benchmark_async_concurrent_queries(50, 5)
        results["async_concurrent"] = async_concurrent_time

        # 清理数据
        cleanup_data()

        # 结果汇总
        print("\n" + "=" * 70)
        print("性能测试结果汇总")
        print("=" * 70)

        print("\n插入性能:")
        print(f"  同步模式: {results['sync_insert']:.3f}秒")
        print(f"  异步模式: {results['async_insert']:.3f}秒")
        speedup = results["sync_insert"] / results["async_insert"]
        if speedup > 1:
            print(f"  ⚡ 异步模式快 {speedup:.2f}x")
        elif speedup < 1:
            print(f"  📊 同步模式快 {1/speedup:.2f}x")
        else:
            print("  ⚖️ 性能相当")

        print("\n查询性能:")
        print(f"  同步模式: {results['sync_select']:.3f}秒")
        print(f"  异步模式: {results['async_select']:.3f}秒")
        speedup = results["sync_select"] / results["async_select"]
        if speedup > 1:
            print(f"  ⚡ 异步模式快 {speedup:.2f}x")
        elif speedup < 1:
            print(f"  📊 同步模式快 {1/speedup:.2f}x")
        else:
            print("  ⚖️ 性能相当")

        print("\n并发查询:")
        print(f"  异步并发模式: {results['async_concurrent']:.3f}秒")
        speedup = results["async_select"] / results["async_concurrent"]
        if speedup > 1:
            print(f"  ⚡ 并发比顺序快 {speedup:.2f}x")
        elif speedup < 1:
            print(f"  📊 顺序比并发快 {1/speedup:.2f}x")
        else:
            print("  ⚖️ 性能相当")

        print("\n💡 性能建议:")
        print("  - 对于单个操作，同步和异步模式性能相近（都是 HTTP 请求）")
        print("  - 对于需要并发执行多个操作的场景，异步模式有明显优势")
        print("  - 对于简单的CRUD应用，选择同步模式更简单")
        print("  - 对于需要高并发的应用，选择异步模式性能更好")

        print("\n" + "=" * 70)
        print("测试完成！")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请检查:")
        print("  1. CouchDB 服务是否运行")
        print("  2. 数据库 test_db 是否存在")
        print("  3. 用户名和密码是否正确")

        # 尝试清理
        try:
            cleanup_data()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())
