"""
验证批量插入的数据
"""

from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, select

CONNECTION_URL = "couchdb://admin:123456@localhost:5984/test_db"

engine = create_engine(CONNECTION_URL)

metadata = MetaData()
users = Table(
    "test_batch",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50)),
    Column("age", Integer),
)

with engine.connect() as conn:
    # 查询所有test_batch数据
    stmt = select(users)
    result = conn.execute(stmt)

    rows = result.fetchall()
    print(f"\n查询到 {len(rows)} 行数据:")
    for row in rows:
        print(f"  {row}")
        # 检查name和age
        if len(row) >= 4:
            print(f"    name={row[2]}, age={row[3]}")

engine.dispose()
