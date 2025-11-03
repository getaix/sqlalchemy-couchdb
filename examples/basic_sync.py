"""
同步模式使用示例

演示如何使用 SQLAlchemy CouchDB Dialect 进行同步数据库操作。
"""

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    select,
    insert,
    update,
    delete,
)
from sqlalchemy.orm import Session
from sqlalchemy_couchdb.exceptions import CouchDBError, OperationalError

# ==================== 1. 创建引擎 ====================

# 方式 1: 基本连接
engine = create_engine("couchdb://admin:123456@localhost:5984/test_db")

# 方式 2: 带 SSL
engine_ssl = create_engine(
    "couchdb://admin:password@localhost:5984/mydb", connect_args={"use_ssl": True}
)

print("✓ 引擎创建成功")


# ==================== 2. 测试连接 ====================

try:
    with engine.connect() as conn:
        # 执行 PING 检查连接
        cursor = conn.connection.cursor()
        cursor.execute("PING")
        print("✓ 数据库连接成功")
except Exception as e:
    print(f"✗ 连接失败: {e}")
    exit(1)


# ==================== 3. 定义表结构 ====================

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


# ==================== 4. INSERT 操作 ====================

print("\n--- INSERT 操作 ---")

with engine.connect() as conn:
    # 插入单条记录
    stmt = insert(users).values(name="Alice", age=30, email="alice@example.com")

    result = conn.execute(stmt)
    conn.commit()

    print(f"✓ 插入成功，影响行数: {result.rowcount}")


# ==================== 5. SELECT 操作 ====================

print("\n--- SELECT 操作 ---")

with engine.connect() as conn:
    # 查询所有用户
    stmt = select(users)
    result = conn.execute(stmt)

    print("所有用户:")
    for row in result:
        print(f"  - {row.name}, {row.age}岁, {row.email}")

    # 带条件的查询
    stmt = select(users).where(users.c.age > 25)
    result = conn.execute(stmt)

    print("\n年龄 > 25 的用户:")
    for row in result:
        print(f"  - {row.name}, {row.age}岁")

    # 带排序和限制
    stmt = select(users).order_by(users.c.age.desc()).limit(10)
    result = conn.execute(stmt)

    print("\n按年龄降序排列（前10条）:")
    for row in result:
        print(f"  - {row.name}, {row.age}岁")


# ==================== 6. UPDATE 操作 ====================

print("\n--- UPDATE 操作 ---")

with engine.connect() as conn:
    stmt = update(users).where(users.c.name == "Alice").values(age=31)

    result = conn.execute(stmt)
    conn.commit()

    print(f"✓ 更新成功，影响行数: {result.rowcount}")


# ==================== 7. DELETE 操作 ====================

print("\n--- DELETE 操作 ---")

with engine.connect() as conn:
    stmt = delete(users).where(users.c.age < 18)

    result = conn.execute(stmt)
    conn.commit()

    print(f"✓ 删除成功，影响行数: {result.rowcount}")


# ==================== 8. 使用 Session (ORM 风格) ====================

print("\n--- Session 操作 ---")

# 注意: Phase 1 暂不支持完整的 ORM，这里仅演示 Session 的 execute 方法

with Session(engine) as session:
    # 查询
    stmt = select(users).where(users.c.name == "Alice")
    result = session.execute(stmt)

    user = result.fetchone()
    if user:
        print(f"✓ 找到用户: {user.name}, {user.age}岁")

    # 提交（虽然 CouchDB 自动提交，但保持一致性）
    session.commit()


# ==================== 9. 批量操作 ====================

print("\n--- 批量操作 ---")

with engine.connect() as conn:
    # 批量插入
    stmt = insert(users)

    conn.execute(
        stmt,
        [
            {"name": "Bob", "age": 25, "email": "bob@example.com"},
            {"name": "Carol", "age": 28, "email": "carol@example.com"},
            {"name": "Dave", "age": 35, "email": "dave@example.com"},
        ],
    )

    conn.commit()
    print("✓ 批量插入完成")


# ==================== 10. 错误处理 ====================

print("\n--- 错误处理 ---")

try:
    with engine.connect() as conn:
        # 尝试执行一个可能失败的操作
        stmt = select(users).where(users.c.age.is_(None))
        conn.execute(stmt)

except OperationalError as e:
    print(f"✗ 操作错误: {e}")
except CouchDBError as e:
    print(f"✗ CouchDB 错误: {e}")
except Exception as e:
    print(f"✗ 未知错误: {e}")
else:
    print("✓ 操作成功")


# ==================== 11. 关闭引擎 ====================

engine.dispose()
print("\n✓ 引擎已关闭")
