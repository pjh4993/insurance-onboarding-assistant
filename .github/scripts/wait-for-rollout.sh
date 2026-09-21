#!/usr/bin/env bash
# Wait until each ECS service's newest deployment serves all its tasks and older deployments have none running.
# Unlike `aws ecs wait services-stable`, this does not wait for Fargate to finish tearing down the old tasks
# (about two minutes), which is after traffic has already moved. A deployment the circuit breaker rolls back
# fails the step.
#
# usage: wait-for-rollout.sh <cluster> <service>... (TIMEOUT_SECONDS, default 900)
set -euo pipefail

cluster="$1"
shift
deadline=$(($(date +%s) + ${TIMEOUT_SECONDS:-900}))

while :; do
  pending=()
  for service in "$@"; do
    # shellcheck disable=SC2016 # the backticks are JMESPath literals
    read -r desired running rollout others < <(
      aws ecs describe-services --cluster "$cluster" --services "$service" --output text --query \
        'services[0].[desiredCount,
                      deployments[?status==`PRIMARY`] | [0].runningCount,
                      deployments[?status==`PRIMARY`] | [0].rolloutState,
                      sum(deployments[?status!=`PRIMARY`].runningCount)]'
    )
    if [[ "$rollout" == "FAILED" ]]; then
      echo "$service: deployment failed (rolled back by the circuit breaker)" >&2
      aws ecs describe-services --cluster "$cluster" --services "$service" \
        --query 'services[0].events[:5].message' --output text >&2
      exit 1
    fi
    if [[ "$running" == "$desired" && "${others:-0}" == "0" ]]; then
      echo "$service: $running/$desired new tasks serving, old tasks stopped or stopping"
    else
      pending+=("$service")
      echo "$service: $running/$desired new tasks running, ${others:-0} old still running ($rollout)"
    fi
  done
  ((${#pending[@]} == 0)) && exit 0
  if (($(date +%s) > deadline)); then
    echo "timed out waiting for: ${pending[*]}" >&2
    exit 1
  fi
  set -- "${pending[@]}"
  sleep 10
done
