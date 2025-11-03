"""
重试机制和错误恢复工具

提供重试装饰器和错误恢复策略，用于处理网络错误、超时等临时性故障。
"""

import time
import functools
from typing import Callable, Optional, Tuple
import httpx

from sqlalchemy_couchdb.exceptions import OperationalError


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        backoff_factor: float = 2.0,
        retry_on_status_codes: Optional[Tuple[int, ...]] = None,
    ):
        """
        初始化重试配置

        参数:
            max_retries: 最大重试次数（默认3次）
            retry_delay: 初始重试延迟（秒，默认0.5）
            backoff_factor: 退避因子（默认2.0，即每次延迟翻倍）
            retry_on_status_codes: 需要重试的HTTP状态码（默认: 502, 503, 504）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.retry_on_status_codes = retry_on_status_codes or (502, 503, 504)


def with_retry(config: Optional[RetryConfig] = None):
    """
    重试装饰器 - 用于自动重试失败的操作

    用法:
        @with_retry(RetryConfig(max_retries=5))
        def my_function():
            # 可能失败的操作
            pass

    参数:
        config: 重试配置，如果为None则使用默认配置
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.retry_delay

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (
                    httpx.NetworkError,
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    OperationalError,  # 添加 OperationalError 到可重试异常列表
                ) as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        # 达到最大重试次数，抛出异常
                        raise OperationalError(
                            f"操作失败，已重试 {config.max_retries} 次: {str(e)}"
                        ) from e

                    # 等待后重试
                    time.sleep(delay)
                    delay *= config.backoff_factor

                except httpx.HTTPStatusError as e:
                    # 检查是否应该重试此状态码
                    if e.response.status_code in config.retry_on_status_codes:
                        last_exception = e

                        if attempt == config.max_retries:
                            raise OperationalError(
                                f"HTTP {e.response.status_code} 错误，已重试 {config.max_retries} 次"
                            ) from e

                        time.sleep(delay)
                        delay *= config.backoff_factor
                    else:
                        # 不应重试的状态码，直接抛出
                        raise

            # 理论上不会到达这里，但以防万一
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def with_async_retry(config: Optional[RetryConfig] = None):
    """
    异步重试装饰器 - 用于自动重试失败的异步操作

    用法:
        @with_async_retry(RetryConfig(max_retries=5))
        async def my_async_function():
            # 可能失败的异步操作
            pass
    """
    import asyncio

    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.retry_delay

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (
                    httpx.NetworkError,
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    OperationalError,  # 添加 OperationalError 到可重试异常列表
                ) as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        raise OperationalError(
                            f"操作失败，已重试 {config.max_retries} 次: {str(e)}"
                        ) from e

                    await asyncio.sleep(delay)
                    delay *= config.backoff_factor

                except httpx.HTTPStatusError as e:
                    if e.response.status_code in config.retry_on_status_codes:
                        last_exception = e

                        if attempt == config.max_retries:
                            raise OperationalError(
                                f"HTTP {e.response.status_code} 错误，已重试 {config.max_retries} 次"
                            ) from e

                        await asyncio.sleep(delay)
                        delay *= config.backoff_factor
                    else:
                        raise

            if last_exception:
                raise last_exception

        return wrapper

    return decorator


# 默认重试配置实例
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    retry_delay=0.5,
    backoff_factor=2.0,
    retry_on_status_codes=(502, 503, 504),
)
