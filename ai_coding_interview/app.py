import uuid
import time
import logging

from flask import Flask, jsonify, request, render_template

from database import Database, DatabaseError
from event_bus import EventBus, EntitlementsService
from payment_service import PaymentService
from retry import with_retry

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app")

app = Flask(__name__)

db = Database()
event_bus = EventBus()
entitlements = EntitlementsService()
payment_service = PaymentService()

event_bus.subscribe(
    "plan_upgraded",
    entitlements.handle_plan_upgraded,
    handler_name="EntitlementsService.handle_plan_upgraded",
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/user/<user_id>")
def get_user(user_id):
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    features = entitlements.get_entitlements(user_id)
    return jsonify({"user": user, "features": features})


@app.route("/api/upgrade", methods=["POST"])
def upgrade_user():
    data = request.get_json() or {}
    user_id = data.get("user_id", "user_1")
    plan = data.get("plan", "premium")

    try:
        result = _perform_upgrade(user_id, plan)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Upgrade failed for user={user_id}: {e}")
        return jsonify({"error": str(e), "user_id": user_id}), 500


@with_retry(max_attempts=3, retryable_exceptions=(DatabaseError,))
def _perform_upgrade(user_id: str, plan: str) -> dict:
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    logger.info(f"[{request_id}] Starting upgrade: user={user_id}, plan={plan}")

    user = db.get_user(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    if user["plan"] == plan:
        logger.info(f"[{request_id}] User already on {plan} plan — no-op")
        return {"success": True, "message": "Already on this plan", "user_id": user_id}

    payment_key = f"upgrade_{user_id}_{plan}_{int(time.time())}"
    logger.info(f"[{request_id}] Processing payment...")
    payment_result = payment_service.process_payment(
        user_id=user_id,
        amount=9.99,
        plan=plan,
        idempotency_key=payment_key,
    )
    logger.info(f"[{request_id}] Payment OK: charge_id={payment_result['charge_id']}")

    txn_id = db.begin_transaction()
    logger.info(f"[{request_id}] Updating user plan in database...")
    db.update_user(txn_id, user_id, {"plan": plan})

    logger.info(f"[{request_id}] Publishing upgrade event...")
    event_bus.publish({
        "type": "plan_upgraded",
        "user_id": user_id,
        "new_plan": plan,
        "previous_plan": user["plan"],
        "charge_id": payment_result["charge_id"],
        "request_id": request_id,
    })

    logger.info(f"[{request_id}] Committing transaction...")
    db.commit(txn_id)

    logger.info(f"[{request_id}] Upgrade complete")
    return {
        "success": True,
        "user_id": user_id,
        "plan": plan,
        "charge_id": payment_result["charge_id"],
        "request_id": request_id,
    }


# --------------- debug / test helpers ---------------

@app.route("/api/debug/force-fail", methods=["POST"])
def force_fail():
    count = (request.get_json() or {}).get("count", 1)
    db.force_fail_next_commits(count)
    logger.warning(f"[DEBUG] Forcing next {count} DB commit(s) to fail")
    return jsonify({"message": f"Next {count} commit(s) will fail"})


@app.route("/api/debug/state")
def debug_state():
    user = db.get_user("user_1")
    features = entitlements.get_entitlements("user_1")
    expected = entitlements.PLAN_FEATURES.get(user["plan"], {})
    return jsonify({
        "user": user,
        "features": features,
        "event_log": event_bus.get_event_log(),
        "outbox": db.outbox,
        "consistency": {
            "is_consistent": features == expected,
            "user_plan": user["plan"],
            "expected_features": expected,
            "actual_features": features,
        },
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    db.reset()
    event_bus.reset()
    entitlements.reset()
    payment_service.reset()
    logger.info("All state reset")
    return jsonify({"message": "All state reset", "success": True})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
