#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
plugin_root=$(cd -- "$script_dir/../.." && pwd)
omarchy_path=${OMARCHY_PATH:-/usr/share/omarchy}

wayland_socket=${WAYLAND_DISPLAY:-}
if [[ -z $wayland_socket ]]; then
  printf '%s\n' "HOST-SMOKE: SKIP (WAYLAND_DISPLAY is not set)"
  exit 77
fi
if [[ $wayland_socket != /* ]]; then
  wayland_socket=${XDG_RUNTIME_DIR:?}/$wayland_socket
fi
if [[ ! -S $wayland_socket ]]; then
  printf '%s\n' "HOST-SMOKE: SKIP (Wayland socket is unavailable)"
  exit 77
fi

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT

config="$tmp/config"
fake_root="$tmp/plugin"
fake_address="AA:BB:CC:DD:EE:01"
mkdir -p "$config" "$tmp/home/.config" "$tmp/cache" "$tmp/state" "$fake_root/bridge"
ln -s "$omarchy_path/shell/Ui" "$config/Ui"
ln -s "$omarchy_path/shell/Commons" "$config/Commons"
ln -s "$script_dir/host-smoke/shell.qml" "$config/shell.qml"
ln -s "$script_dir/fixtures/fake_bridge.py" "$fake_root/bridge/freebuds_bridge.py"

bridge_pattern="$fake_root/bridge/freebuds_bridge.py --stdio"

run_scenario() {
  local startup=$1
  local expected_refreshes=$2
  local expected_starts=$3
  local expected_config_errors=$4
  local fake_log="$tmp/fake-bridge-$startup.jsonl"
  local fake_lock="$tmp/fake-bridge-$startup.lock"
  local smoke_output smoke_status
  local -a fake_records
  local refresh_count=0
  local start_count=0
  local config_count=0
  local config_line=-1
  local hello_line=-1
  local overlap=false
  local index record

  set +e
  smoke_output=$(env \
    HOME="$tmp/home" \
    XDG_CONFIG_HOME="$tmp/home/.config" \
    XDG_CACHE_HOME="$tmp/cache" \
    XDG_STATE_HOME="$tmp/state" \
    OMARCHY_PATH="$omarchy_path" \
    FREEBUDS_PLUGIN_ROOT="$plugin_root" \
    FREEBUDS_BRIDGE_ROOT="$fake_root" \
    FREEBUDS_FAKE_BRIDGE_LOG="$fake_log" \
    FREEBUDS_FAKE_BRIDGE_LOCK="$fake_lock" \
    FREEBUDS_FAKE_ADDRESS="$fake_address" \
    FREEBUDS_FAKE_STARTUP="$startup" \
    FREEBUDS_FAKE_REFRESH_DELAY="0.35" \
    DBUS_SYSTEM_BUS_ADDRESS="unix:path=$tmp/no-system-bus" \
    QT_QPA_PLATFORM=wayland \
    QS_DISABLE_FILE_WATCHER=1 \
    QS_NO_RELOAD_POPUP=1 \
    /usr/bin/timeout --kill-after=1s 10s \
      /usr/bin/quickshell -p "$config" --no-color 2>&1)
  smoke_status=$?
  set -e
  printf '%s\n' "$smoke_output"
  if (( smoke_status != 0 )); then
    return "$smoke_status"
  fi
  if [[ $smoke_output == *"WARN scene:"* ]]; then
    printf '%s\n' "HOST-SMOKE: plugin-owned QML warning detected" >&2
    return 1
  fi

  if [[ ! -f $fake_log ]]; then
    printf '%s\n' "HOST-SMOKE: fake bridge did not start" >&2
    return 1
  fi

  mapfile -t fake_records < "$fake_log"
  for index in "${!fake_records[@]}"; do
    record=${fake_records[$index]}
    if [[ $record == *'"event":"request","method":"refresh"'* ]]; then
      ((refresh_count += 1))
    elif [[ $record == *'"event":"started"'* ]]; then
      ((start_count += 1))
    elif [[ $record == *'"event":"overlap"'* ]]; then
      overlap=true
    elif [[ $record == *'"event":"output","type":"error","code":"config_invalid"'* ]]; then
      ((config_count += 1))
      config_line=$index
    elif [[ $record == *'"event":"output","type":"hello"'* ]]; then
      hello_line=$index
    fi
  done

  if [[ $startup == "invalid" || $startup == "duplicate-invalid" ]]; then
    if (( config_line < 0 || hello_line <= config_line )); then
      printf '%s\n' "HOST-SMOKE: fake bridge did not emit config_invalid before hello" >&2
      return 1
    fi
  elif (( config_line >= 0 )); then
    printf '%s\n' "HOST-SMOKE: valid startup emitted config_invalid" >&2
    return 1
  fi
  if (( refresh_count != expected_refreshes )); then
    printf '%s\n' "HOST-SMOKE: expected $expected_refreshes $startup refreshes, got $refresh_count" >&2
    return 1
  fi
  if (( start_count != expected_starts )); then
    printf '%s\n' "HOST-SMOKE: expected $expected_starts $startup bridge starts, got $start_count" >&2
    return 1
  fi
  if (( config_count != expected_config_errors )); then
    printf '%s\n' "HOST-SMOKE: expected $expected_config_errors $startup config errors, got $config_count" >&2
    return 1
  fi
  if [[ $overlap == true ]]; then
    printf '%s\n' "HOST-SMOKE: replacement bridge overlapped its predecessor" >&2
    return 1
  fi
  if pgrep -f -- "$bridge_pattern" >/dev/null; then
    printf '%s\n' "HOST-SMOKE: fake bridge survived service destruction" >&2
    return 1
  fi

  printf '%s\n' "HOST-SMOKE: $startup startup passed"
}

run_scenario valid 2 2 0
run_scenario invalid 2 2 2
run_scenario duplicate-invalid 0 1 2
printf '%s\n' "HOST-SMOKE: pending serialization, replacement lifecycle, startup gating, and child cleanup confirmed"
