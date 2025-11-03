"""
简单验证脚本 - 测试基本功能
"""

from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, select, insert

# 连接配置
CONNECTION_URL = "couchdb://admin:123456@localhost:5984/test_db"

print("=" * 60)
print("简单功能验证")
print("=" * 60)

# 创建引擎
engine = create_engine(CONNECTION_URL, echo=True)

# 定义表
metadata = MetaData()
users = Table(
    "test_users",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50)),
    Column("age", Integer),
)

print("\n✓ 引擎和表结构创建成功\n")

# 测试插入
print("=" * 60)
print("测试插入")
print("=" * 60)

with engine.connect() as conn:
    # 清理
    try:
        from sqlalchemy import delete

        stmt = delete(users)
        conn.execute(stmt)
        conn.commit()
    except:
        pass

    # 插入
    stmt = insert(users).values(name="TestUser", age=25)
    result = conn.execute(stmt)
    conn.commit()

    print(f"\n✓ 插入成功，rowcount: {result.rowcount}")

# 测试查询
print("\n" + "=" * 60)
print("测试查询")
print("=" * 60)

with engine.connect() as conn:
    stmt = select(users).where(users.c.name == "TestUser")
    result = conn.execute(stmt)

    rows = result.fetchall()
    print(f"\n查询结果: {len(rows)} 行")

    if rows:
        for row in rows:
            print(f"Row: {row}")
            # 使用索引访问
            try:
                print(f"  name: {row[2]}, age: {row[3]}")
            except:
                print("  无法通过索引访问")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)

engine.dispose()
