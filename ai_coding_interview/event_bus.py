import time
import uuid
import logging
from collections import defaultdict

logger = logging.getLogger("eventbus")


class EventBus:

    def __init__(self):
        self._subscribers = defaultdict(list)
        self._event_log = []
        self._delivery_count = defaultdict(int)

    def subscribe(self, event_type: str, handler, handler_name: str = None):
        name = handler_name or handler.__name__
        self._subscribers[event_type].append({"handler": handler, "name": name})
        logger.info(f"Registered handler '{name}' for event '{event_type}'")

    def publish(self, event: dict):
        event_id = event.get("id", f"evt_{uuid.uuid4().hex[:10]}")
        event["id"] = event_id
        event["published_at"] = time.time()

        event_type = event.get("type", "unknown")
        handlers = self._subscribers.get(event_type, [])

        logger.info(f"Publishing event: type={event_type}, id={event_id}, handlers={len(handlers)}")

        self._event_log.append(event)
        self._delivery_count[event_id] += 1

        if self._delivery_count[event_id] > 1:
            logger.warning(f"Event {event_id} delivered {self._delivery_count[event_id]} times — possible duplicate")

        for sub in handlers:
            try:
                logger.debug(f"Dispatching {event_type} -> '{sub['name']}'")
                sub["handler"](event)
            except Exception as e:
                logger.error(f"Handler '{sub['name']}' failed for event {event_id}: {e}")

    def get_event_log(self):
        return list(self._event_log)

    def reset(self):
        self._event_log = []
        self._delivery_count = defaultdict(int)


class EntitlementsService:

    PLAN_FEATURES = {
        "free": {
            "api_access": True,
            "export_csv": False,
            "advanced_analytics": False,
            "priority_support": False,
            "custom_integrations": False,
        },
        "premium": {
            "api_access": True,
            "export_csv": True,
            "advanced_analytics": True,
            "priority_support": True,
            "custom_integrations": True,
        },
    }

    def __init__(self):
        self._entitlements = {
            "user_1": dict(self.PLAN_FEATURES["free"]),
        }
        self._processed_events = set()
        self._processing_log = []

    def handle_plan_upgraded(self, event: dict):
        user_id = event.get("user_id")
        new_plan = event.get("new_plan", "premium")
        event_id = event.get("id", "unknown")
        idempotency_key = event.get("idempotency_key")

        if idempotency_key and idempotency_key in self._processed_events:
            logger.info(f"Skipping duplicate event: idempotency_key={idempotency_key}")
            return

        # Simulate network latency to downstream service
        time.sleep(0.3)

        logger.info(f"Processing plan upgrade: user={user_id}, plan={new_plan}, event_id={event_id}")

        features = self.PLAN_FEATURES.get(new_plan, self.PLAN_FEATURES["free"])
        self._entitlements[user_id] = dict(features)

        if idempotency_key:
            self._processed_events.add(idempotency_key)

        self._processing_log.append({
            "event_id": event_id,
            "user_id": user_id,
            "new_plan": new_plan,
            "timestamp": time.time(),
            "idempotency_key": idempotency_key,
        })

        logger.info(
            f"Features updated for user={user_id}: "
            f"{sum(1 for v in features.values() if v)} features enabled"
        )

    def get_entitlements(self, user_id: str) -> dict:
        return self._entitlements.get(user_id, dict(self.PLAN_FEATURES["free"]))

    def reset(self):
        self._entitlements = {
            "user_1": dict(self.PLAN_FEATURES["free"]),
        }
        self._processed_events = set()
        self._processing_log = []
