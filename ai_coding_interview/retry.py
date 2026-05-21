import time
import functools
import logging

logger = logging.getLogger("retry")


def with_retry(max_attempts=3, backoff_base=0.2, retryable_exceptions=(Exception,)):
    """
    Retry decorator with exponential backoff.

    Wraps a function so that transient failures are automatically retried.
    This is used on critical API endpoints to improve reliability.

    WARNING: Be careful with non-idempotent operations inside retried functions.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"Executing '{func.__name__}' (attempt {attempt}/{max_attempts})")
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(f"'{func.__name__}' succeeded on attempt {attempt}")
                    return result
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = backoff_base * (2 ** (attempt - 1))
                        logger.warning(
                            f"'{func.__name__}' failed (attempt {attempt}): "
                            f"{type(e).__name__}: {e}. Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"'{func.__name__}' exhausted all {max_attempts} attempts. "
                            f"Last error: {e}"
                        )
            raise last_exception
        return wrapper
    return decorator
