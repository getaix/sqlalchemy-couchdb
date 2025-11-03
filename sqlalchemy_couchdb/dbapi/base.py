"""
DBAPI 2.0 基础常量和类型定义

符合 PEP 249 (DB-API 2.0) 规范。
"""

# DBAPI 2.0 模块接口
apilevel = "2.0"  # DBAPI 版本
threadsafety = 1  # 线程可以共享模块，但不能共享连接
paramstyle = "named"  # 命名参数风格，例如: :name


class DBAPITypeObject:
    """DBAPI 类型对象"""

    def __init__(self, *values):
        """
        初始化类型对象

        参数:
            *values: 该类型对应的 Python 类型
        """
        self.values = values

    def __eq__(self, other):
        """类型比较"""
        return other in self.values


# DBAPI 2.0 标准类型对象
STRING = DBAPITypeObject(str)  # 字符串类型
BINARY = DBAPITypeObject(bytes, bytearray)  # 二进制类型
NUMBER = DBAPITypeObject(int, float)  # 数字类型
DATETIME = DBAPITypeObject()  # 日期时间类型
ROWID = DBAPITypeObject()  # 行 ID 类型
