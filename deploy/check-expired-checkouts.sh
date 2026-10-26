#!/usr/bin/env bash
set -uo pipefail

# Both checks share one heartbeat so a healthy checkout scan cannot mask an
# allocation/webhook exception. Provider/customer identifiers never reach it.
app_container="${JSK_WEB_CONTAINER:-jsk-savings-web-1}"
heartbeat_url="${FINANCIAL_EXCEPTIONS_HEARTBEAT_URL:-}"
check_status=0
/usr/bin/docker exec "${app_container}" python manage.py check_financial_exceptions || check_status=1
# At most six provider requests, each with a configured maximum of 30 seconds.
# The total expired backlog remains reported even when not inspected this cycle.
/usr/bin/docker exec "${app_container}" python manage.py reconcile_abandoned_razorpay_orders \
  --grace-minutes=5 --limit=3 --summary-only --fail-on-pending || check_status=1

if [[ -n "${heartbeat_url}" ]]; then
  heartbeat_target="${heartbeat_url}"
  if [[ ${check_status} -ne 0 ]]; then
    heartbeat_target="${heartbeat_url%/}/fail"
  fi
  if ! curl --fail --silent --max-time 10 --request POST "${heartbeat_target}" >/dev/null 2>&1; then
    echo "expired_checkout_alert delivery=failed"
    exit 69
  fi
  echo "expired_checkout_alert delivery=heartbeat"
else
  if [[ "${REQUIRE_FINANCIAL_HEARTBEAT:-false}" == "true" ]]; then
    echo "expired_checkout_alert delivery=unconfigured"
    exit 64
  fi
  echo "expired_checkout_alert delivery=server_only"
fi
exit "${check_status}"
