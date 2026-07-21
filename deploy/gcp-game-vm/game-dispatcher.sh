#!/usr/bin/env bash
set -euo pipefail

metadata_key="${GAME_METADATA_KEY:-active-game}"
metadata_url="http://metadata.google.internal/computeMetadata/v1/instance/attributes/${metadata_key}"

selected_game="$({
  curl --fail --silent --show-error \
    --header 'Metadata-Flavor: Google' \
    "${metadata_url}"
} | tr '[:upper:]' '[:lower:]')"

case "${selected_game}" in
  palworld)
    target_service="palworld.service"
    other_service="rust.service"
    ;;
  rust)
    target_service="rust.service"
    other_service="palworld.service"
    ;;
  *)
    echo "Unsupported or missing ${metadata_key}: ${selected_game:-<empty>}" >&2
    exit 1
    ;;
esac

if systemctl is-active --quiet "${other_service}"; then
  echo "Refusing to start ${target_service}; ${other_service} is active" >&2
  exit 1
fi

systemctl start "${target_service}"
echo "Started ${target_service} from VM metadata ${metadata_key}=${selected_game}"
