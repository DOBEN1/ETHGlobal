# Bug Report: Premium Features Showing for Free-Tier Users

**Reported by:** Sarah Kim, Customer Success Lead
**Priority:** P1 — Revenue Impact
**Date:** 2024-11-14

---

## Summary

We're getting reports from the billing team that some users who attempted to upgrade but were **not successfully charged** are showing premium features in their account. The user's profile page correctly shows **"Free"** plan, but they have access to premium-only features like CSV Export and Advanced Analytics.

This has been reported 3 times this week. It seems intermittent — most upgrades work fine, but occasionally the system gets into a bad state.

## Steps to Reproduce

1. Start the application:
   ```bash
   pip install flask
   python app.py
   ```
2. Open http://localhost:5001
3. Click **"Upgrade to Premium"**
4. *Sometimes* the upgrade fails with a 500 error
5. After the failure, refresh the page
6. Notice: Profile shows **"Free"** plan, but the Features panel shows premium features as enabled

**Note from DevOps:** The issue is more reliably reproduced under load or when the database is under connection pressure. The debug panel (gear icon at the bottom of the page) has a **"Force DB Failure + Upgrade"** button that simulates this condition.

## What We've Investigated So Far

- **Payment service** — Checked payment logs. Payments are either fully processed or not charged at all. The payment service's idempotency seems to be working correctly. We don't think this is a payment issue.
- **Retry logic** — The upgrade endpoint has retry middleware. We wondered if retries were causing duplicate charges or duplicate feature grants, but payment idempotency keys prevent double-charging. Still, the retry logic seems suspicious — worth looking at.
- **Event bus** — We see events being published in the log. The entitlements service processes them. Nothing obviously wrong in the handler logs, but we haven't ruled this out.

## Expected Behavior

If an upgrade fails for any reason, the user's features should remain at free-tier level. The system should **never** be in a state where the profile shows one plan but features reflect another.

## Acceptance Criteria for Fix

1. The system must never be in an inconsistent state between the user profile and feature entitlements, even if the database fails mid-operation
2. The fix should be resilient to process crashes and restarts
3. Events should be processed exactly once (or at least effectively once)
4. Include a way to verify the fix works (e.g., force a failure and confirm consistency is maintained)

## File Overview

| File | Description |
|------|-------------|
| `app.py` | Main server — upgrade flow, API endpoints |
| `database.py` | Mock database with transaction support |
| `event_bus.py` | Event bus + entitlements feature service |
| `payment_service.py` | Payment processing with retry & idempotency |
| `retry.py` | Retry decorator for transient failure handling |
| `templates/index.html` | Frontend UI |
