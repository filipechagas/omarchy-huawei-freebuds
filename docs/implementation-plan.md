# FreeBuds Pro 5 Omarchy Plugin Implementation Plan

Status: Historical implementation plan
Plan date: 2026-08-18
Architecture authority: [`architecture.md`](architecture.md)
Target release: `0.1.0`
Plugin ID: `io.github.filipechagas.freebuds`

Release-policy update (2026-11-11): [`../CLAUDE.md`](../CLAUDE.md) supersedes all
release-gate instructions in this historical plan. Owner acceptance and green
automated checks are sufficient; HW-01 through HW-16 are optional, not blockers.
Tag signatures are optional as well.

## 1. Execution contract

This plan implements the accepted architecture without reopening its decisions. Work proceeds in the numbered order. A step is complete only after its exit gate passes; the next step does not begin while the current gate is red.

The implementation keeps these invariants from the first commit:

- The only hardware target is HUAWEI FreeBuds Pro 5, public model T0023, private DeviceInfo model ID `00016D`.
- Omarchy schema-v1 `service` and `bar-widget` entry points are the complete host integration.
- Quickshell Bluetooth is the only authority for generic adapter, paired/bonded, connected, and fallback aggregate-battery state.
- One attached Python 3 standard-library child handles strict framing and bounded private transactions.
- The child creates only `AF_BLUETOOTH` RFCOMM sockets, always on channel 1 with `BT_SECURITY_MEDIUM`.
- Device contact occurs only for panel-open refresh, explicit `Retry`, and explicit ANC actions.
- Every private transaction uses a new socket, repeats identity verification, permits one outstanding request, performs no automatic retry, and closes in `finally`.
- The three ANC writes are immutable captured frames and succeed only after a matching post-write state, returned directly or queried once after an exact zero-status acknowledgement.
- There is no OpenFreebuds integration, Omapods reuse, systemd unit, helper package, AUR dependency, IP networking, detached execution, Bluetooth management, channel scan, persistent socket, polling, notification subscription, reconnect contact, automatic write, or automatic write replay.
- The selected address is the only persistent device datum and is stored atomically with mode `0600`.
- Private values are nullable observations and are never fabricated or persisted.
- The UI remains visible and useful through its generic Quickshell fallback.
- The release tag remains blocked until the physical hardware gate passes; passing that gate does not broaden the exact target or establish a stable-support claim.
- Invalid config startup reports `config_invalid` before the final hello; accepted request IDs strictly increase for each child lifetime.
- Every transport send has a fail-closed queued-input guard with one exception for the exact empty `01/06` control frame, while the protocol's missing sequence field remains an explicit causality limit.
- Generic fallback is display-only, and a wall-clock rollback expires private observations.

If implementation evidence contradicts an accepted decision, work stops at the current gate. The contradiction is recorded and `architecture.md` is revised through a separate architecture decision before implementation resumes. No fallback dependency, model, channel, security level, transport, or command is introduced inside an implementation step.

## 2. Deliverables

The finished tree contains these implementation and verification files:

| File | Deliverable |
|---|---|
| `manifest.json` | Exact schema-v1 plugin identity and entry points |
| `Service.qml` | Singleton generic-state projection, child lifecycle, request serialization, generations, and private-state expiry |
| `Panel.qml` | Native always-visible bar widget and panel with generic fallback, selection, Retry, and gated ANC controls |
| `Model.js` | Pure primitive validation, reduction, formatting, and view-state functions |
| `bridge/freebuds_bridge.py` | One standard-library JSONL child with strict protocol, RFCOMM transactions, and owner-only selection persistence |
| `tests/python/test_framer.py` | Frame, CRC, stream, TLV, identity, battery, ANC, and deterministic fuzz tests |
| `tests/python/test_transactions.py` | Transport policy, transaction ordering, gating, timeout, close, and no-retry tests |
| `tests/python/test_jsonl.py` | JSONL, config, process handshake, validation, and stdout-isolation tests |
| `tests/qml/tst_Model.qml` | Pure model, generic/private state, generation, freshness, selection, and view-state tests |
| `tests/qml/fixtures/fake_bridge.py`, `tests/qml/host-smoke/shell.qml`, and `tests/qml/run-host-smoke.sh` | Fixed fake child plus installed-host entry-point, shared-service, fallback, and child-cleanup smoke harness |
| `.github/workflows/check.yml` | Static, Python, QML, manifest, dependency, and packaging gates |
| `.gitignore` | Excludes Python bytecode and `__pycache__` directories |
| `docs/hardware-validation.md` | Authoritative Pending/Passed/Failed ledger for HW-01 through HW-16 |
| `docs/preview.png` | Actual Omarchy layer-shell render with deterministic fixture values; documentation only |
| `README.md` | Target scope, hardware status, installation, use, privacy, troubleshooting, removal, and no-affiliation notice |
| `LICENSE` | Standard MIT License text with the project copyright notice |

No settings schema, package recipe, service unit, vendored dependency, icon asset, generated code, virtual environment, binary helper, submodule, raw mode-`160000` gitlink, or repository symlink is added.

## 3. Step 1: Establish the loadable plugin skeleton

### Changes

1. Add `manifest.json` byte-for-byte equivalent to the accepted manifest in `architecture.md`.
2. Add the standard MIT License text in `LICENSE`.
3. Add minimal `Service.qml` and `Panel.qml` entry points that instantiate without host properties and become usable after delayed host injection.
4. In `Service.qml`, declare nullable `shell` and `manifest`; do not use `required` for host-injected values.
5. In `Panel.qml`, derive from Omarchy `Panel`, set `manageIpc: false`, keep `bar`, `moduleName`, and `settings` nullable, and render one native generic headphones glyph even when the service is null.
6. Add `README.md` with the exact target, pending hardware status, Omarchy 4 baseline, MIT license, unofficial/no-affiliation statement, and a statement that all Bluetooth management remains in Omarchy Bluetooth.
7. Create `.github/workflows/check.yml` with an initial manifest and syntax job; later steps extend the same workflow.

### Verification

```bash
jq -e '
  .schemaVersion == 1 and
  .id == "io.github.filipechagas.freebuds" and
  .version == "0.1.0" and
  .license == "MIT" and
  .kinds == ["service", "bar-widget"] and
  .entryPoints.service == "Service.qml" and
  .entryPoints.barWidget == "Panel.qml"
' manifest.json >/dev/null

omarchy plugin validate .
gate_root=$(mktemp -d)
mkdir "$gate_root/qml-import"
ln -s /usr/share/omarchy/shell "$gate_root/qml-import/qs"
/usr/lib/qt6/bin/qmllint -W 0 -I "$gate_root/qml-import" Panel.qml Service.qml
rm -rf "$gate_root"
```

### Exit gate

- Omarchy validates both entry points.
- Each QML component can be constructed before host-property injection without warnings or exceptions.
- The bar item remains visible in the service-null state.
- The tree contains none of the prohibited packaging, dependency, or asset files.

## 4. Step 2: Implement the pure Huawei protocol boundary

### Changes

1. Add `bridge/freebuds_bridge.py` with no third-party imports and no socket creation at module import time.
2. Define the six immutable complete frames from `architecture.md`: DeviceInfo read, component-battery read, ANC read, Set Off, Set ANC, and Set Awareness.
3. Validate every constant's declared length and CRC during bridge startup. A failed self-check emits no hello and exits nonzero.
4. Implement CRC-16/XMODEM with `binascii.crc_hqx(data, 0)`.
5. Implement a bounded stream decoder with a 4096-byte declared-frame maximum, garbage resynchronization on `0x5A`, split-frame support, combined-frame support, version `0x00`, exact length, and CRC validation.
6. Implement strict TLV decoding with bounds checks, duplicate-known-field rejection, and uninterpreted retention of well-formed unknown fields.
7. Implement expected service/command matching for one outstanding request.
8. Implement strict DeviceInfo decoding: unique tag `02` length two, bounded ASCII tag `0A` ending in `00016D`, matching bounded ASCII prefix in tag `0F`, and unique tag `19` length one.
9. Implement the Pro 5 battery decoder: tag `02` length three, each percentage in `0..100`, and tag `05` length two with values in `{0,1}`. Expose only left, right, case, and one observation marker. Ignore private aggregate and charging semantics.
10. Implement the extended Pro 5 ANC decoder: tag `01` length two, top-level mode byte `0`, `1`, or `2`, and exact tag `02 01 05`. Map the modes to `off`, `anc`, and `awareness`; do not expose the submode.
11. Keep all decoder return values immutable primitive dictionaries, integers, bytes, strings, and `None`.

### Tests

`tests/python/test_framer.py` covers:

- Every immutable request and write frame byte-for-byte.
- Independently recomputed length and CRC for every retained frame.
- Every possible split point for each retained frame.
- Two and three valid frames in one byte stream.
- Garbage before magic and between frames.
- Minimum length, maximum length, over-limit length, wrong version, bad CRC, truncated frame, truncated TLV, and duplicate known TLV.
- An unknown well-formed TLV retained without a semantic field.
- An otherwise valid unexpected service/command rejected for the active request.
- All three captured extended ANC responses decoded to the correct top-level modes.
- Shorter other-model ANC shapes rejected.
- The captured `100/100/85` component battery and tag-05 presence bytes decoded correctly.
- Zero preserved as a real percentage and values above 100 rejected rather than clamped.
- Strict DeviceInfo acceptance and missing, duplicate, non-ASCII, oversized, conflicting, and non-`00016D` rejection.
- A clearly named synthetic `00016D` DeviceInfo frame used only for parser tests. It is never recorded as hardware evidence and never weakens the physical gate.
- A deterministic fixed-seed byte mutation loop that proves bounded parsing and exception containment without an external fuzzing library.

### Verification

```bash
python3 -m py_compile bridge/freebuds_bridge.py
python3 -m unittest tests.python.test_framer -v
```

### Exit gate

- Every retained frame passes byte, length, and independent CRC assertions.
- Every malformed framing and semantic case fails closed.
- The protocol module performs no IO at import time and exposes no arbitrary packet-send API.
- Coverage includes every parser branch that can admit a private value or command.

## 5. Step 3: Implement the bounded transaction controller

### Changes

1. Add an injectable `RfcommTransport` boundary and a synchronous `TransactionController` inside `bridge/freebuds_bridge.py`.
2. Create sockets only as `socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)`.
3. Before connecting, set `socket.SOL_BLUETOOTH`/`socket.BT_SECURITY` with Linux `struct bt_security` bytes `struct.pack("BB", 2, 0)`, where level `2` is `BT_SECURITY_MEDIUM`.
4. Read the socket option back and require a reported level of at least `2`. Missing constants, set failure, malformed readback, or a lower level returns `security_failed` and never calls `connect()`.
5. Connect only to `(address, 1)`. Do not perform SDP, UUID, service, channel, or security discovery.
6. Enforce a 3-second connect deadline, a 2-second deadline for each expected response, and a 10-second monotonic wall-clock deadline for the whole transaction.
7. Keep one outstanding request: send one query, receive its expected response, then advance.
8. Immediately before every query or write send, check for queued socket bytes or EOF and fault before sending when either is present. Never reinterpret queued input as the next reply.
9. Record the unavoidable causality limit: because retained frames contain no request sequence, a same-command frame arriving after the pre-send guard cannot be proven to have been caused by the latest query. One outstanding request, expected-pair matching, and a fresh socket bound but do not eliminate that ambiguity.
10. On any exception or return path, close the socket in `finally` and discard buffered bytes.
11. Implement `refresh(address)` as DeviceInfo, battery, and ANC queries on one socket. Identity failure invalidates the complete result. After valid identity, battery and ANC fail independently and return `None` for the failed feature.
12. Require at least one valid Pro 5-shaped feature before returning a read-verified result.
13. Implement `set_anc(address, mode)` as DeviceInfo, fresh ANC read, at most one exact write, and one fresh ANC readback.
14. When the initial ANC read already equals the request, return success without sending a write.
15. A send exception, missing readback, invalid readback, timeout, or mismatch returns failure without replay, inverse write, or optimistic state.
16. Return a valid mismatching readback as the observed mode together with `anc_readback_mismatch`; do not label the action successful.

### Tests

`tests/python/test_transactions.py` uses an injected scripted transport and clock to prove:

- The socket tuple is always channel 1.
- Medium security is set and verified before connect.
- Every security failure prevents connect and no low/insecure call exists.
- Refresh sends DeviceInfo, battery, and ANC in exact order with one outstanding request.
- Queued bytes or EOF before any send fail closed without sending the next query or write.
- A test records the no-sequence causality limit instead of claiming the guard can correlate a same-command frame that arrives after it.
- Identity failure prevents battery, ANC, selection, and every write.
- Identity plus one valid Pro 5 shape admits a partial read result; failed fields remain `None`.
- A name, address, successful connect, valid CRC, battery response, or ANC response alone cannot replace DeviceInfo `00016D`.
- `set_anc` performs same-socket identity and extended-ANC gating before a write.
- Each requested mode selects exactly its retained frame.
- Already-active mode sends zero write frames.
- Matching readback commits success.
- Missing, malformed, rejected, timed-out, or mismatching post-write confirmation never commits success or replays the write.
- Connect, response, and total deadlines each fault once and close once.
- EOF, busy channel, unexpected response, bad frame, and disconnect close once and do not retry.
- A transaction creates one socket; completion leaves no socket referenced by the controller.

### Verification

```bash
python3 -m unittest tests.python.test_transactions -v
```

### Exit gate

- Tests prove fixed channel 1, mandatory medium security, same-transaction identity, one outstanding request, exact-control-frame handling at send and response boundaries, rejection of other queued input, no retry, and unconditional close.
- No production function accepts a channel, security level, raw frame, retry count, or alternate model as an argument.
- The transaction controller contains no sleep loop, reconnect loop, polling timer, or notification path.

## 6. Step 4: Complete owner-only config and JSONL process control

### Changes

1. Implement the exact config path `${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/io.github.filipechagas.freebuds.json`.
2. Accept only schema version `1` and an uppercase canonical six-octet `selectedAddress`.
3. Reject symlinks, non-regular files, group/world permission bits, unknown keys, malformed JSON, missing values, and unknown schema versions as `config_invalid`.
4. Create a missing `omarchy` directory with mode `0700`.
5. Write a same-directory temporary regular file with mode `0600`, flush and `fsync` it, atomically replace the target, enforce mode `0600`, and `fsync` the directory. Serialize config operations with nonblocking advisory locks bounded to one second by `CLOCK_BOOTTIME`; map load contention to `config_invalid` and save or clear contention to `config_write_failed`.
6. Implement selection commit only after a `refresh` with `selectOnSuccess:true` passes DeviceInfo and at least one Pro 5 shape. Persist before emitting the successful result.
7. If persistence fails, emit `config_write_failed`, do not commit private state, and close the already-completed socket without another contact.
8. Require ordinary refresh and `set_anc` addresses to equal a final persisted-address read, and hold that read's shared selection lease through device contact so a cooperating process cannot replace its authorization mid-transaction.
9. Implement `clear_selection` as a local owner-only config deletion and `shutdown` as a local clean exit. Neither method imports or opens Bluetooth.
10. Implement the version-1 JSONL startup, request, result, and error messages defined in `architecture.md`. Emit `config_invalid` before the one final hello when config loading fails.
11. Read at most 16 KiB plus one sentinel byte per input line, require UTF-8 JSON objects, reject duplicate object keys, NaN, Infinity, unknown fields, unknown methods, wrong primitive types, duplicate or decreasing accepted IDs, and unsupported protocol versions.
12. Keep the bounded stdin reader active while one synchronous transaction worker runs. Reject every additional request as `busy` without queueing it, consume its strictly increasing accepted ID, and emit exactly one response for each request ID and generation through a serialized output lock.
13. Reserve stdout for compact JSONL messages and flush each line. Send bounded redacted diagnostics to stderr.
14. Use stable bridge error codes: `invalid_request`, `busy`, `config_invalid`, `config_write_failed`, `invalid_address`, `transport_unsupported`, `security_failed`, `connect_failed`, `transport_busy`, `timeout`, `socket_closed`, `invalid_frame`, `unexpected_response`, `identity_mismatch`, `identity_conflict`, `battery_invalid`, `anc_invalid`, `anc_send_failed`, `anc_readback_failed`, and `anc_readback_mismatch`.
15. Permit a QML-authorized `selectOnSuccess:true` refresh to replace a stale bridge selection only after full identity/shape reverification and durable persistence.
16. Redact full Bluetooth addresses, raw config, DeviceInfo strings, serial-like values, and battery snapshots from all error text and diagnostics.

### Tests

`tests/python/test_jsonl.py` covers:

- Missing config, valid config, exact mode `0600`, invalid modes, invalid address, unknown schema, unknown fields, malformed JSON, symlink, directory target, and non-owner-readable conditions.
- Same-directory atomic replacement and cleanup after an injected write failure.
- Bounded shared and exclusive lock contention with stable error mapping and no startup delay beyond the two-second hello contract.
- A competing writer cannot replace or clear a persisted address until an ordinary refresh or ANC transaction releases its shared selection lease.
- Config is not written after identity or shape failure.
- Config write failure suppresses otherwise valid private product state.
- `clear_selection` and `shutdown` create no socket.
- Invalid config emits `config_invalid` before the final hello; valid and missing config emit only the final hello.
- Accepted request IDs are strictly increasing, including a valid request rejected as `busy`.
- Overlong, invalid UTF-8, malformed, duplicate-key, wrong-version, unknown-method, unsafe-enum, and wrong-type lines fail closed.
- `off`, `anc`, and `awareness` are the only accepted ANC input values.
- A second active request returns `busy` and is not queued.
- A reverified `selectOnSuccess:true` candidate can replace stale bridge persistence, while a failed revalidation leaves it unselected.
- A subprocess hello/shutdown smoke test leaves no child and creates no Bluetooth socket.
- Captured stdout parses entirely as protocol JSONL; diagnostics and injected exceptions do not contaminate stdout.
- Redaction tests prove complete addresses and sensitive fixture strings are absent from stdout and stderr.
- An AST import audit permits only Python standard-library modules used by the bridge.

### Verification

```bash
python3 -m compileall -q bridge tests/python
python3 -m unittest discover -s tests/python -v
```

### Exit gate

- The bridge is a single attached-process program with a strict, bounded, versioned stdin/stdout interface.
- Selection persistence is atomic, owner-only, minimal, bounded under lock contention, and impossible before protocol verification.
- Every request has one terminal response, and no local request contacts Bluetooth.
- The complete Python suite passes without a device, BlueZ service, third-party package, or network.

## 7. Step 5: Implement the pure QML state model

### Changes

1. Add `Model.js` with pure functions only; it imports no QML module and accesses no QObjects, files, process, timer, or socket.
2. Define primitive candidate rows containing opaque address key, device name, display label, paired, bonded, connected, `batteryAvailable`, and battery fraction.
3. Match candidates only when immutable `deviceName` equals `HUAWEI FreeBuds Pro 5` and paired and bonded are true. Alias affects display text only.
4. Validate generic aggregate battery as finite `0.0..1.0` and format `Math.round(value * 100)`; use it only when verified component battery data is unavailable.
5. Validate bridge hello/result/error objects, exact protocol version, exact request/generation match, nullable fields, integer percentages in `0..100`, and the three ANC modes.
6. Implement deterministic reduction for helper phase, generic plane, selection intent, request pending, private observations, feature errors, and last safe user message.
7. Implement nondecreasing private age, fresh through 130 seconds, stale through 10 minutes, and expired afterward. Any wall-clock rollback relative to the previous aging sample expires private data immediately.
8. Implement generation rejection, selected-address change clearing, disconnect clearing, adapter-loss clearing, helper-exit clearing, identity-failure clearing, refresh-start clearing, and per-feature partial results.
9. Derive bar and panel view rows without exposing a complete address or private field as generic data.
10. Map every architecture failure class to one fixed short user message and one valid next action.

### Tests

`tests/qml/tst_Model.qml` covers:

- Null, delayed, sparse, malformed, and valid generic snapshots.
- Exact immutable-name candidate matching; alias-only matches rejected.
- Zero, one, and multiple candidate derivation.
- Generic battery absent, zero, one, out of range, NaN, Infinity, and valid fractions.
- Service-null direct fallback with one connected exact-name candidate and with ambiguous candidates.
- Valid full and partial private results.
- Missing, null, negative, floating, over-100, string, and stale private battery fields.
- ANC controls hidden for identity-only, battery-only, malformed, short-shape, stale, expired, disconnected, and helper-failed states.
- ANC controls exposed only for current-generation valid extended ANC state.
- Generation, request ID, address, helper restart, disconnect, adapter loss, and selection changes reject stale values.
- Fresh at 130 seconds, stale at 131 seconds, expired after 10 minutes, and expired immediately on wall-clock rollback.
- Fresh verified left/right data produces the lower-bud bar metric without becoming a generic aggregate or fabricated component; case is excluded.
- Every documented failure produces its fixed message without an address or raw error payload.

### Verification

```bash
OMARCHY_PATH="${OMARCHY_PATH:-/usr/share/omarchy}"
gate_root=$(mktemp -d)
mkdir "$gate_root/qml-import"
ln -s "$OMARCHY_PATH/shell" "$gate_root/qml-import/qs"
/usr/lib/qt6/bin/qmllint -W 0 -I "$gate_root/qml-import" tests/qml/tst_Model.qml
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner \
  -input tests/qml \
  -import "$gate_root/qml-import"
rm -rf "$gate_root"
```

### Exit gate

- Model tests prove that generic and private state cannot be confused.
- All untrusted primitive fields are validated before rendering or state mutation.
- Every stale or failed path produces null/unknown private state rather than a default value.

## 8. Step 6: Implement the singleton service

### Changes

1. Import `Quickshell.Bluetooth` in `Service.qml` and project `Bluetooth.devices.values` to primitives immediately; do not retain device QObjects in model rows.
2. Expose independent generic and private state planes plus `panelOpened()`, `retry()`, `markCandidate(address)`, `setAnc(mode)`, and `clearSelection()`.
3. Resolve the selected live device by address for each generic-state update. Quickshell properties remain authoritative even when bridge output disagrees.
4. Start one attached Quickshell `Process` only after `manifest.__sourceDir` exists, using the exact argv from `architecture.md`, stdin enabled, and the manifest source directory as working directory.
5. Add a two-second hello watchdog. A timeout, exit, malformed output, overlong output, or protocol violation stops the child, increments generation, clears private state, and waits for explicit Retry.
6. Do not restart the child automatically. When Retry starts a stopped child, store one retry intent and execute at most one eligible refresh after a valid hello.
7. Maintain one strictly increasing request ID, one generation, and one pending request. Do not queue panel-open or ANC work while pending.
8. Increment generation on helper start/exit, selected-address change, adapter loss/power-off, and selected-device disconnect.
9. Accept a device-IO result only when request ID, generation, address, current selection, and current Quickshell connection all match. Permit the matching local-only `clear_selection` response to reconcile across a generic generation change because it performs no device IO.
10. Implement selection rules exactly: persisted valid address first; zero candidates no contact; one unpersisted candidate eligible on panel open; multiple candidates require `markCandidate` followed by Retry; persistence only through `selectOnSuccess:true`.
11. Make `markCandidate` local with no child write and no device request.
12. On panel-open rising edge, start one eligible refresh only when idle. Multiple monitor opens during that request do not queue another refresh.
13. Implement ANC action only for a connected persisted selection with current fresh extended-ANC capability. Disable all action entry points while pending.
14. Add a one-second local aging timer that computes nondecreasing age. A backward wall-clock adjustment relative to the previous aging sample and a forward jump beyond expiry both expire data safely. The timer performs no child write or device contact.
15. Clear private state on every architecture-mandated event. Preserve the selected address across ordinary disconnect, adapter off, and child restart.
16. On service destruction, send `shutdown` when the child is running and stdin is writable. Otherwise skip the message. In both cases, close stdin, invalidate generation, and rely on attached-process destruction as the hard stop.
17. Add no `IpcHandler` and expose no shell-command string, external refresh endpoint, Bluetooth mutation, or detached process.

### Verification

Extend `tests/qml/tst_Model.qml` and the host entry-point smoke harness to prove:

- Delayed `manifest` and `shell` injection starts exactly one child.
- Two monitor panels share one service and one pending request.
- Panel open is a rising-edge trigger; close, generic state changes, reconnect, and child hello are not independent private-contact triggers.
- One-candidate panel open and marked-multiple-candidate Retry send the correct `selectOnSuccess` value.
- `markCandidate`, `clearSelection`, and panel close send no Bluetooth transaction.
- Unexpected child exit clears private state and does not restart.
- Explicit Retry performs one child restart and one eligible refresh.
- Late responses after disconnect, selection change, or helper generation are ignored.
- A matching local `clear_selection` result reconciles after an unrelated generic generation change without opening a socket.
- Freshness transitions perform no process write.
- Service destruction leaves no child.

### Exit gate

- One shell produces exactly one bridge child and one serialized request stream.
- Quickshell remains authoritative for every generic property.
- Only the three accepted trigger classes can reach `refresh` or `set_anc`.
- Helper failure leaves a stable generic fallback and requires explicit Retry.

## 9. Step 7: Build the native panel and bar interaction

### Changes

1. Implement `Panel.qml` with Omarchy's native `Panel`, `BarIconButton`, typography, spacing, color, focus, tooltip, and action components.
2. Use only host-supplied monochrome audio glyphs. Add no image, logo, custom icon, font, animation asset, or copied QML.
3. Retrieve the singleton reactively through `bar?.shell?.serviceFor(moduleName)` and keep a direct read-only Quickshell projection for the service-null generic fallback.
4. Make the bar control visible in every adapter, service, child, device, and private state.
5. Show the lower fresh verified left/right value in the bar and suppress the generic `Earbuds` row while component rows are present. Otherwise show the Quickshell aggregate only for the unambiguous selected connected device; in the service-null fallback, require exactly one connected exact-name paired/bonded candidate.
6. Open and close the per-monitor panel directly from the bar button. Set `manageIpc: false`; add no external IPC handler.
7. On `opened` changing from false to true, call `service.panelOpened()` once. Do not call it on component creation, close, generic reconnect, or state rerender.
8. Render the fixed panel order from `architecture.md`: product header, generic connection state, one battery presentation, freshness, ANC controls, and one safe next action.
9. Display unknown private fields as `Not reported`. Never render a null, invalid, stale-bar, or failed value as `0%`.
10. Hide ANC controls until current-generation extended ANC verification succeeds. Disable them while stale, pending, disconnected, helper-failed, or expired.
11. Render only `Off`, `ANC`, and `Awareness`; a fresh verified mode selects its matching bar glyph and short marker. A press calls `service.setAnc()` once and shows pending state until readback result.
12. Render exact-name candidates without displaying addresses. With multiple candidates, selecting a row calls `markCandidate` only; the separate `Retry` action performs verification.
13. Provide `Choose another device` as a local selection-clear action. It performs no BlueZ operation.
14. Provide no Pair, Connect, Disconnect, Forget, Scan, adapter-power, trust, profile, codec, EQ, gesture, wear, latency, multipoint, firmware, OpenFreebuds, or raw-packet control.
15. Add keyboard focus, arrow navigation, Enter/Space activation, Escape close, visible focus, accessible names, disabled-state explanations, and status text that does not rely on color.
16. Bound and elide untrusted display names and messages. Do not render complete addresses or raw backend error strings.

### Verification

Run QML unit tests and perform an Omarchy host smoke pass for:

- Service absent, starting, ready, stopped, protocol-failed, and Retry-starting states.
- Adapter absent, adapter off, no candidate, one disconnected candidate, one connected candidate, multiple candidates, and persisted-address absent states.
- Generic battery absent, zero, low, full, and invalid.
- Valid components, partial components, stale components, expired components, and refresh failure.
- Valid ANC state, pending action, already-active action, direct matching state, exact write acknowledgement plus matching readback, missing confirmation, and mismatching state.
- Keyboard-only operation, narrow panel width, host scaling, and two-monitor panel switching.
- No QML warnings, binding loops, destroyed-QObject access, duplicate process, duplicate trigger, or blocked shell frame.

### Exit gate

- The widget is always visible and native to Omarchy.
- Every private control is capability-gated and readback-driven.
- Every generic Bluetooth management operation is absent.
- Mouse and keyboard users can reach every action, and all statuses have textual meaning.

## 10. Step 8: Prove lifecycle and deterministic fallback integration

### Changes

1. Extend automated tests with process, socket, config, and child-output failure injection for every row in the architecture failure table.
2. Add a packaged-Quickshell entry-point test that creates each component before host injection, injects host properties later, and destroys it cleanly.
3. Add a multi-monitor host scenario that opens two panels rapidly and records one child and one private request.
4. Add hot-reload, disable, re-enable, update-while-open, and removal scenarios. Each scenario asserts that no bridge process or RFCOMM socket survives service destruction.
5. Add stale-generation scenarios for disconnect, adapter off, selection change, helper exit, and delayed child output.
6. Add a closed-panel idle measurement: the child remains blocked on stdin, opens no socket, emits no heartbeat, and performs no timed work.
7. Add log capture assertions that reject complete Bluetooth addresses, DeviceInfo identity strings, raw config, raw private frames, and repeated battery snapshots.
8. Record the exact safe user message and next action for each injected failure; compare them to the architecture table.

### Required scenario matrix

| Scenario | Required result |
|---|---|
| Child missing or exits | Generic state remains, private clears, no auto-restart, Retry shown |
| Hello timeout or malformed JSONL | Child stops, generation changes, private clears, no device contact |
| Adapter absent or off | Selection persists, private clears, no socket |
| Device disconnected or removed from inventory | Generic status updates, private clears, no reconnect contact |
| Zero or multiple unselected candidates | No socket until an eligible panel-open or marked-candidate Retry |
| Medium security unavailable | No connect call and no downgrade |
| Channel 1 refused, busy, or timed out | One failure, one close, no scan, Retry shown |
| Bad length, CRC, TLV, identity, shape, or command | No affected private value and no write |
| Battery or ANC partial failure | Failed feature is null; valid independent feature remains explicit |
| ANC send or readback failure | No success, no replay, no inverse write |
| Disconnect or reload during ANC | Generation rejects late result; no replay after return |
| Config invalid or write failure | No committed selection/private result; no permissive file |
| Observation stale or expired | Local UI transition only; zero child/device traffic |
| Panel closes during request | Original bounded request finishes or times out; no second request |
| Service destruction | Child and socket terminate; no orphan |

### Exit gate

- Every deterministic failure row has an automated assertion or a host smoke assertion.
- No lifecycle scenario adds an automatic restart, reconnect, retry, or replay.
- Standard Bluetooth audio and Omarchy Bluetooth remain untouched throughout fault injection.

## 11. Step 9: Lock static, CI, packaging, and release-document gates

### Changes

1. Complete `.github/workflows/check.yml` with manifest validation, Python compile/unit tests, QML lint/unit tests, formatting comparison, forbidden-dependency checks, and repository-shape checks.
2. Pin CI's Omarchy contract fixture to source `f0020448ca87329199de7cb12f2015ebc4a3e5e7` and Quickshell contract to revision `28771c7c74b42e20afca0b1b63980cb46515537c`.
3. Add an AST-based Python import allowlist test and a socket-construction test that permits only the accepted Bluetooth family/type/protocol.
4. Add static scans over implementation files for OpenFreebuds/Omapods runtime references, IP socket families, HTTP modules, D-Bus modules, systemd units, package recipes, detached execution, shell interpolation, channel iteration, security downgrade, retry loops, and private polling timers.
5. Use `/usr/lib/qt6/bin/qmlformat` on temporary copies whose filenames end in `.qml`, because installed `qmlformat 1.0` has no `--check` flag.
6. Complete `README.md` with exact install, enable, use, pending hardware warning, generic fallback, privacy, config path/mode, troubleshooting, disable, removal, and optional config deletion instructions.
7. State in README that the project is unofficial, is not affiliated with Huawei, supports only T0023/`00016D`, ships no Huawei/Omapods assets, performs no Bluetooth management, and performs no network access.
8. Verify the manifest and README contain no OpenFreebuds installation instruction, helper-package instruction, AUR dependency, systemd command, or broader-model claim.
9. Reject raw gitlinks from `git ls-files --stage`, as well as filesystem symlinks and unexpected paths. Permit only the bounded `880x1080` `docs/preview.png` as binary documentation and reject every other binary path.
10. Run `tests/qml/run-host-smoke.sh` under a headless Weston Wayland compositor in CI; exit 77 is a failure, not an allowed skip.
11. Block release tags unless `docs/hardware-validation.md` says `Status: Passed`, HW-01 through HW-16 all say `Pass`, the annotated tag contains a complete PGP or SSH signature envelope, and GitHub cryptographically verifies that signature with `verification.verified` equal to `true` and `verification.reason` equal to `valid`. Query GitHub's annotated-tag REST object with the workflow token, require its identity and direct commit target to match the local tag, and fail closed on API errors or malformed responses. Configure no private signing key and claim no current signing readiness.

### Full offline gate

```bash
set -euo pipefail
OMARCHY_PATH="${OMARCHY_PATH:-/usr/share/omarchy}"
gate_root=$(mktemp -d)
qml_import_root="$gate_root/qml-import"
format_root="$gate_root/formatted"
mkdir "$qml_import_root" "$format_root"
ln -s "$OMARCHY_PATH/shell" "$qml_import_root/qs"
cleanup() {
  rm -rf "$gate_root"
}
trap cleanup EXIT

jq -e . manifest.json >/dev/null
omarchy plugin validate .
python3 -m compileall -q bridge tests/python
python3 -m unittest discover -s tests/python -v
/usr/lib/qt6/bin/qmllint -W 0 -I "$qml_import_root" \
  Panel.qml Service.qml tests/qml/tst_Model.qml
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner \
  -input tests/qml \
  -import "$qml_import_root"

for file in Panel.qml Service.qml; do
  formatted="$format_root/$(basename "${file%.qml}")-formatted.qml"
  cp "$file" "$formatted"
  /usr/lib/qt6/bin/qmlformat -i "$formatted"
  diff -u "$file" "$formatted"
done

set +e
tests/qml/run-host-smoke.sh
host_smoke_status=$?
set -e
if (( host_smoke_status == 77 )); then
  printf 'HOST-SMOKE: skip 77 is a gate failure\n' >&2
  exit 1
fi
if (( host_smoke_status != 0 )); then
  exit "$host_smoke_status"
fi
```

Run the host smoke command inside a Wayland session. CI creates a temporary
headless Weston compositor before this command block reaches the smoke step.

The CI static audit separately enforces:

- No non-standard Python import.
- No IP-network socket or network client/server library.
- No OpenFreebuds runtime reference or Omapods source/asset provenance in implementation files.
- No systemd unit, package recipe, binary, raw gitlink, symlink, generated environment, or settings schema.
- No `execDetached`, `startDetached`, `bash -c`, arbitrary packet method, channel loop, low-security constant, automatic retry counter, reconnect loop, notification command, or private polling timer.
- Exact manifest ID, version, license, kinds, entry points, and `allowMultiple:false`.
- Exact six command-frame hashes, lengths, and CRCs.

### Exit gate

- The full offline gate passes on the supported Omarchy host and in CI.
- A clean plugin checkout validates and loads without a build or external package install.
- README behavior and troubleshooting match the architecture's deterministic fallbacks.
- The only runtime dependencies are the supported Omarchy/Quickshell host, Python 3 standard library, Linux Bluetooth socket ABI, BlueZ-managed pairing/connection, and the owner-authorized earbuds.

## 12. Step 10: Execute the physical hardware and release gate

This step uses one owner-authorized retail HUAWEI FreeBuds Pro 5/T0023 unit. It begins only after Steps 1 through 9 are green. Bluetooth addresses, serial-like DeviceInfo values, and raw private captures remain private; publishable evidence is redacted and hashed.

### Safe setup

1. Record plugin commit, version `0.1.0`, earbuds public model, firmware, Omarchy, Quickshell, kernel, BlueZ, and Bluetooth adapter versions in the release checklist.
2. Pair and connect exclusively through Omarchy Bluetooth.
3. Confirm no OpenFreebuds process, other private-control process, firmware update, call, or unrelated capture is active.
4. Record the starting ANC state so the owner can restore it after the checks.
5. Start a redacted process/socket/log trace sufficient to prove channel, security, trigger count, and cleanup without retaining a publishable address.

### Hardware checks

Execute the authoritative HW-01 through HW-16 matrix in
[`hardware-validation.md`](hardware-validation.md). Record results only there;
automated fixtures and host smoke do not satisfy a hardware row.

### Abort conditions

Stop the hardware session immediately if an unexpected pairing, authorization, reset, firmware update, account prompt, repeated disconnect, unstable audio, thermal issue, ambiguous target, differing write frame, second private-control socket, or unrecoverable starting state appears. Stop means close the current socket, send no compensating unverified command, preserve the exact failure evidence privately, and keep the release blocked.

### Release outcome

- If every HW gate passes, set the hardware ledger to `Status: Passed` and run the full offline gate once more. A release tag is eligible only if it is an annotated `v0.1.0` tag at that exact green commit, contains a PGP or SSH signature envelope, and GitHub cryptographically verifies that signature with `verification.verified: true` and `verification.reason: valid`.
- If any HW gate fails or is not executed, keep the ledger `Failed` or `Pending`, block the release tag, expose no unsupported private claim, and introduce no fallback implementation branch.
- A failed gate returns implementation to the numbered step that owns the failing behavior. After the fix, rerun that step's gate, all later automated gates, and the complete hardware matrix from HW-01.
- CI uses only its workflow token to query GitHub's verification result; it has no private signing key configured, and this plan claims no current signing readiness.

## 13. Final definition of done

Implementation is complete when all of these statements are true:

1. Steps 1 through 9 pass in order and the full offline command block is green.
2. The plugin validates and hot-loads on the fixed Omarchy 4/Quickshell baseline.
3. One shell owns one attached Python child and zero idle RFCOMM sockets.
4. Static and dynamic tests prove that only panel-open, Retry, and explicit ANC actions contact the private channel.
5. Every contact uses channel 1, medium security, same-transaction `00016D`, a retained Pro 5 shape, one outstanding request, bounded deadlines, and unconditional close.
6. Every ANC success has a matching post-write state, returned directly or queried after an exact zero-status acknowledgement; no failure path retries or replays a write.
7. Quickshell remains authoritative for generic state and the UI performs no Bluetooth mutation.
8. Selection persistence is atomic mode `0600`; no private observation is persisted or fabricated.
9. Every architecture failure state has a tested deterministic generic fallback.
10. The repository contains no rejected dependency, process model, networking path, model expansion, packet API, asset, or settings schema.
11. The physical-gate result is recorded in `docs/hardware-validation.md`; a tag requires Passed plus sixteen Pass rows, an annotated PGP or SSH signature envelope, and GitHub cryptographic verification with `verification.verified: true` and `verification.reason: valid`.
12. The exact T0023/`00016D` scope remains unchanged regardless of the hardware-gate outcome.

This definition is binary. A red item leaves the implementation incomplete or the release blocked according to Step 10; it does not authorize a compatibility workaround.
