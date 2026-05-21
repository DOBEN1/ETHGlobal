import time
import uuid
import logging

logger = logging.getLogger("payment")


class PaymentError(Exception):
    pass


class PaymentTransientError(Exception):
    pass


class PaymentService:
    """
    Mock payment gateway integration.
    Implements retry with exponential backoff for transient failures.
    """

    def __init__(self):
        self._processed = {}
        self._retry_count = {}

    def process_payment(self, user_id: str, amount: float, plan: str,
                        idempotency_key: str = None) -> dict:
        """
        Process a payment with idempotency guarantees.

        If a payment with the same idempotency_key was already processed,
        returns the cached result instead of charging again.
        """
        if idempotency_key is None:
            idempotency_key = f"pay_{uuid.uuid4().hex[:12]}"

        if idempotency_key in self._processed:
            logger.warning(
                f"Duplicate payment detected for key={idempotency_key}. "
                f"Returning cached result. (This is expected during retries)"
            )
            return self._processed[idempotency_key]

        logger.info(
            f"Processing payment: user={user_id}, amount=${amount:.2f}, "
            f"plan={plan}, key={idempotency_key}"
        )

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                result = self._charge(user_id, amount, plan, idempotency_key, attempt)
                self._processed[idempotency_key] = result
                return result
            except PaymentTransientError as e:
                if attempt < max_retries:
                    backoff = 0.1 * (2 ** attempt)
                    logger.warning(
                        f"Transient error on attempt {attempt}/{max_retries}: {e}. "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"All {max_retries} attempts failed for key={idempotency_key}")
                    raise PaymentError(f"Payment failed after {max_retries} attempts: {e}")

    def _charge(self, user_id, amount, plan, idempotency_key, attempt):
        time.sleep(0.05)
        charge_id = f"ch_{uuid.uuid4().hex[:10]}"
        logger.info(
            f"Charge successful: charge_id={charge_id}, user={user_id}, "
            f"amount=${amount:.2f} (attempt {attempt})"
        )
        return {
            "success": True,
            "charge_id": charge_id,
            "amount": amount,
            "plan": plan,
            "idempotency_key": idempotency_key,
            "timestamp": time.time(),
        }

    def reset(self):
        self._processed = {}
        self._retry_count = {}
