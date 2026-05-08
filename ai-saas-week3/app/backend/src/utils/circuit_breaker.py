from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态枚举"""

    CLOSED = "CLOSED"  # 正常状态，允许调用
    OPEN = "OPEN"  # 熔断状态，拒绝调用
    HALF_OPEN = "HALF_OPEN"  # 半开状态，允许试探性调用


class CircuitBreaker:
    """熔断器实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_samples: int = 3,
    ):
        """
        初始化熔断器

        :param failure_threshold: 连续失败阈值，超过此值触发熔断
        :param recovery_timeout: 熔断后等待恢复的秒数
        :param half_open_samples: HALF_OPEN状态下需要成功的样本数
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_samples = half_open_samples

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """获取当前状态（考虑自动从OPEN切换到HALF_OPEN）"""
        asyncio.create_task(self._check_auto_transition())
        return self._state

    @property
    def state_str(self) -> str:
        """获取状态字符串"""
        return self.state.value

    async def _check_auto_transition(self):
        """检查是否需要自动状态转换"""
        async with self._lock:
            if (
                self._state == CircuitState.OPEN
                and self._last_failure_time
                and datetime.now() - self._last_failure_time
                > timedelta(seconds=self.recovery_timeout)
            ):
                logger.info("[CircuitBreaker] Auto transition from OPEN to HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0

    async def call(
        self,
        func: Callable[..., Any],
        *args,
        timeout: int = 30,
        max_retries: int = 4,
        **kwargs,
    ) -> Any:
        """
        受熔断器保护的调用

        :param func: 要调用的函数
        :param timeout: 单次调用超时时间（秒）
        :param max_retries: 最大重试次数
        :return: 函数返回值
        """
        # 检查熔断器状态
        current_state = self.state
        if current_state == CircuitState.OPEN:
            logger.warning("[CircuitBreaker] Circuit is OPEN, rejecting call")
            raise CircuitBreakerError("Circuit is OPEN")

        try:
            # 带超时和重试的调用
            result = await self._with_retry(func, timeout, max_retries, *args, **kwargs)

            # 成功处理
            await self._on_success()
            return result

        except Exception:
            # 失败处理
            await self._on_failure()
            raise

    async def _with_retry(
        self, func: Callable[..., Any], timeout: int, max_retries: int, *args, **kwargs
    ) -> Any:
        """带指数退避重试的调用"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                async with asyncio.timeout(timeout):
                    return await func(*args, **kwargs)
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    f"[CircuitBreaker] Timeout on attempt {attempt + 1}/{max_retries + 1}"
                )
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"[CircuitBreaker] Error on attempt {attempt + 1}/{max_retries + 1}: {str(e)}"
                )

            # 指数退避等待
            if attempt < max_retries:
                wait_time = 2**attempt  # 2^0, 2^1, 2^2, ...
                logger.info(f"[CircuitBreaker] Retrying after {wait_time}s...")
                await asyncio.sleep(wait_time)

        raise last_exception or Exception("Max retries exceeded")

    async def _on_success(self):
        """处理成功调用"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_samples:
                    logger.info(
                        "[CircuitBreaker] HALF_OPEN -> CLOSED (enough successes)"
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # 重置失败计数
                self._failure_count = 0

    async def _on_failure(self):
        """处理失败调用"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # HALF_OPEN状态下任何失败都回到OPEN
                logger.info("[CircuitBreaker] HALF_OPEN -> OPEN (failure)")
                self._state = CircuitState.OPEN
                self._last_failure_time = datetime.now()
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                logger.info(
                    f"[CircuitBreaker] Failure count: {self._failure_count}/{self.failure_threshold}"
                )

                if self._failure_count >= self.failure_threshold:
                    logger.info("[CircuitBreaker] CLOSED -> OPEN (threshold exceeded)")
                    self._state = CircuitState.OPEN
                    self._last_failure_time = datetime.now()

    def reset(self):
        """手动重置熔断器"""
        logger.info("[CircuitBreaker] Manual reset")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    def get_status(self) -> dict:
        """获取熔断器状态信息"""
        return {
            "state": self.state_str,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": (
                self._last_failure_time.isoformat() if self._last_failure_time else None
            ),
        }


class CircuitBreakerError(Exception):
    """熔断器异常"""

    pass


# 创建全局熔断器实例
global_circuit_breaker = CircuitBreaker()
