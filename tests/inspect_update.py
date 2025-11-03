"""
检查 update_stmt 的内部结构
"""

from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, update

CONNECTION_URL = "couchdb://admin:123456@localhost:5984/test_db"

engine = create_engine(CONNECTION_URL)

metadata = MetaData()
users = Table(
    "test_users",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50)),
    Column("age", Integer),
)

# 创建 UPDATE 语句
stmt = update(users).where(users.c.name == "Alice").values(age=31)

print("=" * 60)
print("UPDATE 语句结构分析")
print("=" * 60)

print(f"\nstmt 类型: {type(stmt)}")

# 尝试访问 values
if hasattr(stmt, "_values"):
    print("\n_values 内容:")
    print(f"  类型: {type(stmt._values)}")
    print(f"  内容: {stmt._values}")

# 检查 WHERE 子句
if hasattr(stmt, "_where_criteria"):
    print("\n_where_criteria 内容:")
    print(f"  类型: {type(stmt._where_criteria)}")
    print(f"  内容: {stmt._where_criteria}")

    # 检查 WHERE 子句的结构
    where = stmt._where_criteria
    if hasattr(where, "left") and hasattr(where, "right"):
        print(f"\n  left: {where.left} (type: {type(where.left)})")
        print(f"  right: {where.right} (type: {type(where.right)})")
        if hasattr(where.right, "value"):
            print(f"  right.value: {where.right.value}")

engine.dispose()
