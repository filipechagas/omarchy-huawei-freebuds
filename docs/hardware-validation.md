# Optional Hardware Validation

Status: Pending

The owner reports the plugin working on their FreeBuds Pro 5 and accepted it for
release on 2026-11-11. The detailed checks below have not been run individually;
their `Not run` results are retained honestly. Automated fixtures, parser tests,
QML tests, and host smoke tests are separate from physical hardware evidence.

## Release Policy

Owner acceptance and green automated checks are the release criteria. This
matrix is an optional diagnostic checklist, not a release gate. A `Pending`
status or `Not run` result does not block releases. See [`../CLAUDE.md`](../CLAUDE.md)
for the release and marketplace-validation workflow.

Only an owner-authorized retail HUAWEI FreeBuds Pro 5, public model T0023, may
be used. Record exact host, adapter, firmware, Omarchy, Quickshell, Qt, BlueZ,
kernel, and commit versions in private test evidence. Publish only redacted
evidence with no complete Bluetooth address, serial-like DeviceInfo value, raw
config, or private battery snapshot.

## Hardware Matrix

| ID | Physical procedure | Pass condition | Result |
|---|---|---|---|
| HW-01 | Open the panel while the paired earbuds are disconnected. | Generic disconnected state is accurate and no RFCOMM socket opens. | Not run |
| HW-02 | Connect through Omarchy Bluetooth, then open the panel. | Exactly one channel-1 connection uses explicit `BT_SECURITY_MEDIUM`, consumes one exact empty `01/06` startup frame before the first query, and performs no SDP, scan, or downgrade. | Not run |
| HW-03 | Capture the DeviceInfo response privately. | A complete CRC-valid `01/07` response passes every strict identity field check and tag `0A` ends in `00016D`. | Not run |
| HW-04 | Run three panel-open or explicit Retry refreshes. | Every request repeats identity verification, returns at least one retained Pro 5 shape, and closes its socket. | Not run |
| HW-05 | Compare decoded left, right, and case values with controlled physical placement. | Tag-02 ordering agrees, missing data remains `Not reported`, the panel omits the generic `Earbuds` row, and the bar uses the lower left/right value without the case. | Not run |
| HW-06 | Observe the generic aggregate battery with private battery unavailable. | The fallback `Earbuds` value follows live Quickshell `batteryAvailable` and `battery` only and is not shown beside verified components. | Not run |
| HW-07 | From different starting modes, request Off, ANC, and Awareness once each. | Each action repeats identity and fresh ANC gating, sends at most one retained write, and succeeds only from a matching extended state returned directly or queried once after the exact zero-status `2B/04` acknowledgement. | Not run |
| HW-08 | Cause or simulate loss of the ANC readback after the write. | The action fails, no write is replayed or inverted, and ANC is not claimed from send success. | Not run |
| HW-09 | Disconnect during both refresh and an ANC action. | Private state clears, late results are ignored, no replay occurs, and BlueZ remains the audio-management owner. | Not run |
| HW-10 | Terminate the child, then press Retry once. | Private state clears, there is no automatic restart, and Retry creates one child and at most one eligible transaction. | Not run |
| HW-11 | Turn the adapter off and on through Omarchy Bluetooth. | The plugin performs no toggle, clears private state, preserves selection, and makes no automatic reconnect contact. | Not run |
| HW-12 | Hot reload with the panel open and repeat with two monitors. | One child and one active transaction exist, with no duplicate IPC target, socket, or orphan process. | Not run |
| HW-13 | Suspend and resume, then disable, enable, and remove the plugin. | No automatic private contact, stale callback, persisted private observation, or orphan process remains. | Not run |
| HW-14 | Leave the connected device idle with the panel closed for 10 minutes. | There are zero RFCOMM connections, heartbeats, polling loops, and measurable active-child CPU loops. | Not run |
| HW-15 | Inspect config, stdout, stderr, shell logs, and publishable evidence. | Config is mode `0600` and contains only the selected address; output exposes no complete address, serial-like value, raw config, or private snapshot. | Not run |
| HW-16 | Restore the owner's initial ANC state with one verified action. | Matching readback confirms restoration and the final socket closes. | Not run |

## Recording Rules

Change a row to `Pass` only after its complete procedure and pass condition are
observed on the recorded hardware/host tuple. Change it to `Fail` when the pass
condition is not met. Keep `Status: Pending` while any row is `Not run`; use
`Status: Failed` when the completed matrix contains a failure; use
`Status: Passed` only when all sixteen rows are `Pass`.

After a relevant implementation change, rerun affected optional checks before
claiming their results still apply. Runtime safeguards remain mandatory: fixed
channel, medium transport security, strict model identity, bounded transactions,
and verified write readback.
