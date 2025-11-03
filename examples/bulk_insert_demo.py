"""
批量插入功能演示

演示如何使用 SQLAlchemy-CouchDB 的批量插入功能。

运行前确保:
1. CouchDB 服务运行在 localhost:5984
2. 数据库 test_db 已创建
3. 用户名和密码正确（默认: admin/password）
"""

import asyncio
import time
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    MetaData,
    Table,
    select,
    insert,
    delete,
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


# 数据库配置（根据实际情况修改）
SYNC_URL = "couchdb://admin:password@localhost:5984/test_db"
ASYNC_URL = "couchdb+async://admin:password@localhost:5984/test_db"


def create_users_table():
    """创建用户表定义"""
    metadata = MetaData()
    return Table(
        "demo_users",
        metadata,
        Column("_id", String, primary_key=True),
        Column("_rev", String),
        Column("name", String(50)),
        Column("age", Integer),
        Column("email", String(100)),
        Column("score", Float),
    )


def demo_sync_bulk_insert():
    """演示同步批量插入"""
    print("\n" + "=" * 70)
    print("同步批量插入演示")
    print("=" * 70)

    users = create_users_table()
    engine = create_engine(SYNC_URL, echo=False)

    try:
        # 清理旧数据
        print("\n1. 清理旧数据...")
        with engine.connect() as conn:
            stmt = delete(users)
            result = conn.execute(stmt)
            conn.commit()
            print(f"   已删除 {result.rowcount} 条旧记录")

        # 准备批量数据
        print("\n2. 准备批量数据...")
        num_records = 100
        user_data = [
            {
                "name": f"User{i}",
                "age": 20 + (i % 50),
                "email": f"user{i}@example.com",
                "score": 60.0 + (i % 40),
            }
            for i in range(num_records)
        ]
        print(f"   准备了 {num_records} 条记录")

        # 批量插入
        print("\n3. 执行批量插入...")
        start_time = time.perf_counter()

        with engine.connect() as conn:
            stmt = insert(users)
            result = conn.execute(stmt, user_data)
            conn.commit()

        elapsed = time.perf_counter() - start_time
        ops_per_sec = num_records / elapsed if elapsed > 0 else 0

        print("   ✅ 插入成功")
        print(f"   ⏱  耗时: {elapsed:.3f}秒")
        print(f"   ⚡ 速度: {ops_per_sec:.2f} 条/秒")
        print(f"   📊 受影响行数: {result.rowcount}")

        # 验证结果
        print("\n4. 验证插入结果...")
        with engine.connect() as conn:
            result = conn.execute(select(users))
            rows = result.fetchall()
            print(f"   总记录数: {len(rows)}")
            print("   前5条记录:")
            for i, row in enumerate(rows[:5]):
                print(f"     [{i+1}] {row.name}, {row.age}岁, {row.email}")

        print("\n✅ 同步批量插入演示完成！")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请检查:")
        print("  1. CouchDB 服务是否运行")
        print("  2. 数据库 test_db 是否存在")
        print("  3. 用户名和密码是否正确")

    finally:
        engine.dispose()


async def demo_async_bulk_insert():
    """演示异步批量插入"""
    print("\n" + "=" * 70)
    print("异步批量插入演示")
    print("=" * 70)

    users = create_users_table()
    engine = create_async_engine(ASYNC_URL, echo=False, poolclass=NullPool)

    try:
        # 清理旧数据
        print("\n1. 清理旧数据...")
        async with engine.connect() as conn:
            stmt = delete(users)
            result = await conn.execute(stmt)
            await conn.commit()
            print(f"   已删除 {result.rowcount} 条旧记录")

        # 准备批量数据
        print("\n2. 准备批量数据...")
        num_records = 100
        user_data = [
            {
                "name": f"AsyncUser{i}",
                "age": 25 + (i % 40),
                "email": f"async{i}@example.com",
                "score": 70.0 + (i % 30),
            }
            for i in range(num_records)
        ]
        print(f"   准备了 {num_records} 条记录")

        # 批量插入
        print("\n3. 执行异步批量插入...")
        start_time = time.perf_counter()

        async with engine.connect() as conn:
            stmt = insert(users)
            result = await conn.execute(stmt, user_data)
            await conn.commit()

        elapsed = time.perf_counter() - start_time
        ops_per_sec = num_records / elapsed if elapsed > 0 else 0

        print("   ✅ 插入成功")
        print(f"   ⏱  耗时: {elapsed:.3f}秒")
        print(f"   ⚡ 速度: {ops_per_sec:.2f} 条/秒")
        print(f"   📊 受影响行数: {result.rowcount}")

        # 验证结果
        print("\n4. 验证插入结果...")
        async with engine.connect() as conn:
            result = await conn.execute(select(users))
            rows = result.fetchall()
            print(f"   总记录数: {len(rows)}")
            print("   前5条记录:")
            for i, row in enumerate(rows[:5]):
                print(f"     [{i+1}] {row.name}, {row.age}岁, {row.email}")

        print("\n✅ 异步批量插入演示完成！")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请检查:")
        print("  1. CouchDB 服务是否运行")
        print("  2. 数据库 test_db 是否存在")
        print("  3. 用户名和密码是否正确")

    finally:
        await engine.dispose()


def demo_performance_comparison():
    """演示性能对比：批量 vs 循环"""
    print("\n" + "=" * 70)
    print("性能对比演示：批量插入 vs 循环插入")
    print("=" * 70)

    users = create_users_table()
    engine = create_engine(SYNC_URL, echo=False)

    try:
        num_records = 50  # 较小的数据量用于演示

        # 1. 循环插入
        print("\n1. 循环插入方式...")
        with engine.connect() as conn:
            stmt = delete(users)
            conn.execute(stmt)
            conn.commit()

        start_time = time.perf_counter()

        with engine.connect() as conn:
            for i in range(num_records):
                stmt = insert(users).values(
                    name=f"LoopUser{i}",
                    age=20 + i,
                    email=f"loop{i}@example.com",
                )
                conn.execute(stmt)
            conn.commit()

        loop_time = time.perf_counter() - start_time
        print(f"   ⏱  耗时: {loop_time:.3f}秒")
        print(f"   ⚡ 速度: {num_records/loop_time:.2f} 条/秒")

        # 2. 批量插入
        print("\n2. 批量插入方式...")
        with engine.connect() as conn:
            stmt = delete(users)
            conn.execute(stmt)
            conn.commit()

        start_time = time.perf_counter()

        with engine.connect() as conn:
            user_data = [
                {
                    "name": f"BulkUser{i}",
                    "age": 20 + i,
                    "email": f"bulk{i}@example.com",
                }
                for i in range(num_records)
            ]
            stmt = insert(users)
            conn.execute(stmt, user_data)
            conn.commit()

        bulk_time = time.perf_counter() - start_time
        print(f"   ⏱  耗时: {bulk_time:.3f}秒")
        print(f"   ⚡ 速度: {num_records/bulk_time:.2f} 条/秒")

        # 对比结果
        print("\n" + "-" * 70)
        print("📊 性能对比结果:")
        print("-" * 70)
        print(f"记录数量:     {num_records} 条")
        print(f"循环插入:     {loop_time:.3f}秒 ({num_records/loop_time:.2f} 条/秒)")
        print(f"批量插入:     {bulk_time:.3f}秒 ({num_records/bulk_time:.2f} 条/秒)")

        if bulk_time > 0:
            speedup = loop_time / bulk_time
            print(f"\n⚡ 性能提升:   {speedup:.2f}x")

            if speedup > 3:
                print("   🎉 批量插入比循环插入快了3倍以上！")
            elif speedup > 2:
                print("   ✅ 批量插入比循环插入快了2倍以上！")
            else:
                print("   📈 批量插入性能有所提升")

        print("-" * 70)

        print("\n✅ 性能对比演示完成！")

    except Exception as e:
        print(f"\n❌ 错误: {e}")

    finally:
        engine.dispose()


async def demo_concurrent_bulk_insert():
    """演示并发批量插入"""
    print("\n" + "=" * 70)
    print("并发批量插入演示")
    print("=" * 70)

    users = create_users_table()
    engine = create_async_engine(ASYNC_URL, echo=False, poolclass=NullPool)

    try:
        # 清理旧数据
        print("\n1. 清理旧数据...")
        async with engine.connect() as conn:
            stmt = delete(users)
            await conn.execute(stmt)
            await conn.commit()

        # 并发插入多批数据
        print("\n2. 并发插入3批数据...")

        async def insert_batch(conn, batch_id, size):
            """插入一批数据"""
            print(f"   开始插入批次 {batch_id}...")
            user_data = [
                {
                    "name": f"Batch{batch_id}_User{i}",
                    "age": 20 + i,
                    "email": f"batch{batch_id}_user{i}@example.com",
                }
                for i in range(size)
            ]
            stmt = insert(users)
            await conn.execute(stmt, user_data)
            print(f"   批次 {batch_id} 插入完成（{size}条）")

        start_time = time.perf_counter()

        async with engine.connect() as conn:
            # 并发插入3批数据
            await asyncio.gather(
                insert_batch(conn, 0, 20),
                insert_batch(conn, 1, 30),
                insert_batch(conn, 2, 25),
            )
            await conn.commit()

        elapsed = time.perf_counter() - start_time

        print("\n   ✅ 并发插入完成")
        print(f"   ⏱  总耗时: {elapsed:.3f}秒")
        print("   📊 总记录数: 75条")

        # 验证结果
        print("\n3. 验证插入结果...")
        async with engine.connect() as conn:
            result = await conn.execute(select(users))
            rows = result.fetchall()
            print(f"   总记录数: {len(rows)}")

            # 统计每批数据
            batch_counts = {}
            for row in rows:
                if row.name.startswith("Batch"):
                    batch_id = row.name.split("_")[0]
                    batch_counts[batch_id] = batch_counts.get(batch_id, 0) + 1

            print("   各批次记录数:")
            for batch_id, count in sorted(batch_counts.items()):
                print(f"     {batch_id}: {count}条")

        print("\n✅ 并发批量插入演示完成！")

    except Exception as e:
        print(f"\n❌ 错误: {e}")

    finally:
        await engine.dispose()


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("SQLAlchemy-CouchDB 批量插入功能演示")
    print("=" * 70)
    print("\n本演示将展示以下功能:")
    print("  1. 同步批量插入")
    print("  2. 异步批量插入")
    print("  3. 性能对比（批量 vs 循环）")
    print("  4. 并发批量插入")

    try:
        # 1. 同步批量插入
        demo_sync_bulk_insert()

        # 2. 异步批量插入
        asyncio.run(demo_async_bulk_insert())

        # 3. 性能对比
        demo_performance_comparison()

        # 4. 并发批量插入
        asyncio.run(demo_concurrent_bulk_insert())

        # 总结
        print("\n" + "=" * 70)
        print("✅ 所有演示完成！")
        print("=" * 70)
        print("\n💡 使用建议:")
        print("  - 对于大批量数据插入，使用批量插入可以显著提升性能")
        print("  - 批量插入默认分页大小为 500 条/批")
        print("  - 异步批量插入支持并发操作，性能更优")
        print("  - 部分失败时会抛出 IntegrityError 异常")
        print("\n" + "=" * 70)

    except KeyboardInterrupt:
        print("\n\n⚠️  演示被中断")
    except Exception as e:
        print(f"\n\n❌ 演示失败: {e}")


if __name__ == "__main__":
    main()
