#!/usr/bin/env bash
set -uo pipefail

app_dir="${JSK_APP_DIR:-/opt/jsk/app}"
heartbeat_url="${FINANCIAL_EXCEPTIONS_HEARTBEAT_URL:-}"

if [[ -z "${heartbeat_url}" ]]; then
  echo "financial_exception_heartbeat status=configuration_error"
  exit 64
fi

if [[ "${1:-}" == "--test-alert" ]]; then
  if ! curl --fail --silent --show-error --max-time 10 --retry 2 \
    --request POST "${heartbeat_url%/}/fail" >/dev/null; then
    echo "financial_exception_heartbeat status=test_delivery_failed"
    exit 69
  fi
  echo "financial_exception_heartbeat status=test_alert_sent"
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: check-financial-exceptions.sh [--test-alert]" >&2
  exit 64
fi

cd "${app_dir}" || exit 65
check_output="$({
  docker compose --env-file .env.production -f compose.production.yml \
    exec -T web python manage.py check_financial_exceptions
} 2>&1)"
check_status=$?
printf '%s\n' "${check_output}"

heartbeat_target="${heartbeat_url}"
if [[ ${check_status} -ne 0 ]]; then
  heartbeat_target="${heartbeat_url%/}/fail"
fi

if ! curl --fail --silent --show-error --max-time 10 --retry 2 \
  --request POST "${heartbeat_target}" >/dev/null; then
  echo "financial_exception_heartbeat status=delivery_failed"
  exit 69
fi

if [[ ${check_status} -eq 0 ]]; then
  echo "financial_exception_heartbeat status=ok"
else
  echo "financial_exception_heartbeat status=alert"
fi
exit "${check_status}"
