#!/usr/bin/env bash
# Campagnes de charge JMeter : 100, 500 puis 1000 utilisateurs (PARTIE 18) - Linux/macOS
# Usage : JMETER=/opt/apache-jmeter-5.6.3/bin/jmeter PORT=8000 LABEL=campagne ./jmeter/run_load_tests.sh
set -euo pipefail

JMETER="${JMETER:-jmeter}"
HOST="${HOST:-localhost}"
PORT="${PORT:-8000}"
RAMPUP="${RAMPUP:-10}"
LOOPS="${LOOPS:-10}"
USERS="${USERS:-100 500 1000}"
LABEL="${LABEL:-campagne}"
DIR="$(cd "$(dirname "$0")" && pwd)"

curl -sf "http://${HOST}:${PORT}/health" > /dev/null  # l'API doit répondre

for n in ${USERS}; do
  out="${DIR}/results/${LABEL}/${n}_users"
  rm -rf "${out}" && mkdir -p "${out}"
  echo "=== ${n} utilisateurs (ramp-up ${RAMPUP} s, ${LOOPS} boucles) ==="
  "${JMETER}" -n -t "${DIR}/churn_test_plan.jmx" \
    -Jthreads="${n}" -Jrampup="${RAMPUP}" -Jloops="${LOOPS}" -Jhost="${HOST}" -Jport="${PORT}" \
    -l "${out}/results.jtl" -e -o "${out}/report" -j "${out}/jmeter.log"
  # statistics.json (versionné) ; le rapport HTML et le .jtl restent en local
  cp "${out}/report/statistics.json" "${out}/statistics.json"
  sleep 15  # laisser l'API revenir au repos entre deux campagnes
done

python3 "${DIR}/summarize_results.py"
