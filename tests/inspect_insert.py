"""
检查 insert_stmt 的内部结构
"""

from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, insert

CONNECTION_URL = "couchdb://admin:123456@localhost:5984/test_db"

engine = create_engine(CONNECTION_URL)

metadata = MetaData()
users = Table(
    "test_users_debug",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50)),
    Column("age", Integer),
)

# 创建 INSERT 语句
stmt = insert(users).values(name="Alice", age=30)

print("=" * 60)
print("INSERT 语句结构分析")
print("=" * 60)

print(f"\nstmt 类型: {type(stmt)}")
print("\nstmt 属性:")
for attr in dir(stmt):
    if not attr.startswith("_"):
        continue
    try:
        value = getattr(stmt, attr)
        if not callable(value) and attr in ["_values", "_multi_values", "parameters"]:
            print(f"  {attr}: {value}")
    except:
        pass

# 尝试访问 values
if hasattr(stmt, "_values"):
    print("\n_values 内容:")
    print(f"  类型: {type(stmt._values)}")
    print(f"  内容: {stmt._values}")

if hasattr(stmt, "_multi_values"):
    print("\n_multi_values 内容:")
    print(f"  类型: {type(stmt._multi_values)}")
    print(f"  内容: {stmt._multi_values}")

if hasattr(stmt, "parameters"):
    print("\nparameters 内容:")
    print(f"  类型: {type(stmt.parameters)}")
    print(f"  内容: {stmt.parameters}")

engine.dispose()
