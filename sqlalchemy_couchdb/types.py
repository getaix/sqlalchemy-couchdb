"""
类型系统 - SQLAlchemy 类型与 CouchDB JSON 类型的映射

提供完整的 Python ↔ JSON 类型转换。
"""

from datetime import datetime, date
from sqlalchemy import types as sa_types
from sqlalchemy.engine.interfaces import Dialect


class CouchDBString(sa_types.String):
    """
    字符串类型

    CouchDB 存储: JSON string
    Python 类型: str
    """

    def bind_processor(self, dialect: Dialect):
        """
        绑定处理器: Python → JSON

        转换 Python 值为 CouchDB 可接受的格式
        """

        def process(value):
            if value is None:
                return None
            return str(value)

        return process

    def result_processor(self, dialect: Dialect, coltype):
        """
        结果处理器: JSON → Python

        转换 CouchDB 返回值为 Python 类型
        """

        def process(value):
            if value is None:
                return None
            return str(value)

        return process


class CouchDBText(CouchDBString):
    """
    文本类型

    与 CouchDBString 相同，但语义上表示长文本。
    """

    pass


class CouchDBInteger(sa_types.Integer):
    """
    整数类型

    CouchDB 存储: JSON number
    Python 类型: int
    """

    def bind_processor(self, dialect: Dialect):
        """绑定处理器"""

        def process(value):
            if value is None:
                return None
            return int(value)

        return process

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器"""

        def process(value):
            if value is None:
                return None
            return int(value)

        return process


class CouchDBFloat(sa_types.Float):
    """
    浮点数类型

    CouchDB 存储: JSON number
    Python 类型: float
    """

    def bind_processor(self, dialect: Dialect):
        """绑定处理器"""

        def process(value):
            if value is None:
                return None
            return float(value)

        return process

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器"""

        def process(value):
            if value is None:
                return None
            return float(value)

        return process


class CouchDBBoolean(sa_types.Boolean):
    """
    布尔类型

    CouchDB 存储: JSON boolean
    Python 类型: bool
    """

    def bind_processor(self, dialect: Dialect):
        """绑定处理器"""

        def process(value):
            if value is None:
                return None
            return bool(value)

        return process

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器"""

        def process(value):
            if value is None:
                return None
            return bool(value)

        return process


class CouchDBDateTime(sa_types.DateTime):
    """
    日期时间类型

    CouchDB 存储: ISO 8601 格式的字符串
    Python 类型: datetime

    示例:
        Python: datetime(2025, 1, 2, 15, 30, 0)
        JSON:   "2025-01-02T15:30:00"
    """

    def bind_processor(self, dialect: Dialect):
        """绑定处理器: datetime → ISO 8601 字符串"""

        def process(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, date):
                return datetime(value.year, value.month, value.day).isoformat()
            return str(value)

        return process

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器: ISO 8601 字符串 → datetime"""

        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    # 如果解析失败，返回原值
                    return value
            return value

        return process


class CouchDBDate(sa_types.Date):
    """
    日期类型

    CouchDB 存储: ISO 8601 日期字符串
    Python 类型: date

    示例:
        Python: date(2025, 1, 2)
        JSON:   "2025-01-02"
    """

    def bind_processor(self, dialect: Dialect):
        """绑定处理器: date → ISO 8601 日期字符串"""

        def process(value):
            if value is None:
                return None
            if isinstance(value, date):
                return value.isoformat()
            return str(value)

        return process

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器: ISO 8601 日期字符串 → date"""

        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                try:
                    return date.fromisoformat(value)
                except ValueError:
                    return value
            return value

        return process


class CouchDBJSON(sa_types.JSON):
    """
    JSON 类型

    CouchDB 存储: JSON object 或 array
    Python 类型: dict 或 list

    注意: CouchDB 原生支持 JSON，无需特殊处理
    """

    def bind_processor(self, dialect: Dialect):
        """绑定处理器: 直接存储"""
        return None  # 无需处理，CouchDB 原生支持

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器: 直接返回"""
        return None  # 无需处理


class CouchDBNumeric(sa_types.Numeric):
    """
    数值类型（高精度）

    CouchDB 存储: JSON number（可能损失精度）或 string（保持精度）
    Python 类型: Decimal

    注意: JSON 的 number 类型是浮点数，可能损失精度。
    对于高精度需求，存储为字符串。
    """

    def __init__(self, precision=None, scale=None, as_string=True, **kwargs):
        """
        初始化

        参数:
            precision: 精度
            scale: 小数位数
            as_string: 是否存储为字符串（默认 True，保持精度）
        """
        super().__init__(precision=precision, scale=scale, **kwargs)
        self.as_string = as_string

    def bind_processor(self, dialect: Dialect):
        """绑定处理器"""
        if self.as_string:
            # 存储为字符串，保持精度
            def process(value):
                if value is None:
                    return None
                return str(value)

            return process
        else:
            # 存储为数字，可能损失精度
            def process(value):
                if value is None:
                    return None
                return float(value)

            return process

    def result_processor(self, dialect: Dialect, coltype):
        """结果处理器"""
        if self.as_string:
            from decimal import Decimal

            def process(value):
                if value is None:
                    return None
                return Decimal(value)

            return process
        else:
            return None


# 类型映射表: SQLAlchemy 类型 → CouchDB 类型
colspecs = {
    sa_types.String: CouchDBString,
    sa_types.Text: CouchDBText,
    sa_types.Integer: CouchDBInteger,
    sa_types.SmallInteger: CouchDBInteger,
    sa_types.BigInteger: CouchDBInteger,
    sa_types.Float: CouchDBFloat,
    sa_types.Numeric: CouchDBNumeric,
    sa_types.Boolean: CouchDBBoolean,
    sa_types.DateTime: CouchDBDateTime,
    sa_types.Date: CouchDBDate,
    sa_types.JSON: CouchDBJSON,
}
