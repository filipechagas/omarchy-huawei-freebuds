# Omarchy FreeBuds Pro 5 Product Specification

> [!WARNING]
> **Evidence only; superseded.** This research-era specification is not
> implementation, product, platform, hardware-status, or release authority.
> Follow [`../architecture.md`](../architecture.md),
> [`../implementation-plan.md`](../implementation-plan.md), and
> [`../hardware-validation.md`](../hardware-validation.md). Its conflicting
> plugin ID, packaged helper, systemd service, Connect control, polling,
> persistence, GPL project-license, stable-release, and 25-row hardware
> recommendations were rejected and must not be followed.

| Field | Decision |
|---|---|
| Status | Build-ready product specification; implementation and release remain gated by the protocol confirmations in PC-01 through PC-12 |
| Product release | `0.1.0` MVP |
| Shell target | Omarchy 4.0.0 and its packaged Quickshell build |
| Hardware target | HUAWEI FreeBuds Pro 5 only |
| Plugin id | `freebuds.pro5` |
| Helper package | `freebuds-pro5-helper` |
| Research cutoff | 2026-08-18 |
| Product decisions left open | None |

## 1. Executive Decision

Build a persistent Omarchy bar widget and one anchored native panel for one selected, verified FreeBuds Pro 5 pair. The horizontal bar shows a generic earbud glyph and one trustworthy earbud battery percentage when available. The panel shows connection state, independently qualified battery fields, and three explicit noise-control choices: `Off`, `Awareness`, and `Noise cancellation`.

The product must not imitate an Apple pairing card. It must use Omarchy's bar slot, `KeyboardPanel`, theme tokens, monospace typography, linear battery rows, native cursor/focus treatment, and all-edge placement. It must not use product renders, glossy cards, circular battery gauges, proximity animations, automatic popups, or Huawei/Apple logos.

The product has five decisive scope boundaries:

1. Support one selected FreeBuds Pro 5 pair, not a general Bluetooth manager and not other FreeBuds models.
2. Put only connection, battery, explicit connect, and the three top-level noise states in MVP.
3. Delegate pairing, disconnecting, forgetting, and adapter power to Omarchy's existing Bluetooth panel.
4. Treat every proprietary field and write as capability-gated. Unknown firmware receives read-only limited mode; an unverified device never receives a vendor write.
5. Run locally without an account, IP networking, analytics, crash upload, recording access, or automatic update checks.

Release `0.1.0` only after at least one exact retail hardware/firmware fingerprint passes the full physical-device matrix. A build that provides only generic BlueZ battery is a useful degraded build, not the MVP release.

## 2. Research Method And Evidence Boundary

### 2.1 Source policy

Huawei owns claims about FreeBuds product behavior, so those claims cite Huawei product, support, manual, or privacy pages. Omarchy, BlueZ, Qt, systemd, Quickshell, and comparable project behavior cite their own documentation or commit-pinned source. Secondary articles were not used.

Huawei documents user-facing behavior but no Linux control API. OpenFreebuds contains a FreeBuds Pro 5 driver and is useful evidence that a Linux implementation exists, but it is reverse-engineered third-party code, not a Huawei specification and not hardware validation for this project. Its packet meanings and command mappings remain protocol-confirmation items. [C1] [C2] [C3]

The platform and protocol reports are separate deliverables. This specification fixes the product behavior now and supplies a conservative runtime fallback for every unconfirmed fact.

### 2.2 Source-backed findings and product consequences

| Source-backed finding | Product consequence |
|---|---|
| Huawei documents ordinary Bluetooth pairing by placing both earbuds in the open case and holding the Function button for at least two seconds until the indicator flashes white. [H3] [H12] | Onboarding gives exactly that instruction, then opens Omarchy Bluetooth. The plugin does not implement its own pairing agent. |
| Huawei's UI can expose left, right, and charging-case battery values, can collapse nearly equal bud values into one value, and updates the case value only after earbuds are placed in the case. [H4] | The data model supports aggregate or split values. Case data always carries an age and never appears as current without a recent observation. Missing split values are not errors and never become `0%`. |
| Huawei names the three top-level states `Noise cancellation`, `Awareness`, and `Off`; no Pro 5 cycle order is published. [H5] | MVP exposes three direct choices in that wording and never implements a cycle button. |
| Pro 5 can retain ten pairings and connect to two devices concurrently. [H6] | Status says `Connected to this computer`, and MVP neither displays nor manages the other host. |
| Huawei's app surface also includes firmware, gestures, wear detection, Find Device, connection management, and other functions. [H7] | The plugin is deliberately not an AI Life clone. Those functions are non-goals. |
| Pro 5 has a Smart recording feature, and a factory reset can erase recordings stored on the earbuds. [H8] | MVP never accesses recordings and never offers reset. Troubleshooting must not casually instruct a reset. |
| Huawei documents Android/iOS management and Windows/macOS pairing but no Linux management app or Linux command protocol. [H7] [H12] | Every Linux proprietary capability remains runtime-gated and physically tested. |
| Omarchy 4.0.0 hosts bar widgets, panels, and services in one long-running Quickshell process; one widget instance exists per monitor while a service is singleton. [O1] [O2] [O15] | Use one `bar-widget` plus one shell `service`; no per-monitor polling or helper process. |
| Omarchy's plugin installer clones a Git repository, validates it, runs no hooks or builds, requests no sudo, and loads third-party code unsandboxed in the shell. [O3] [O17] | Ship reviewable QML through the plugin manager and the native helper as a separately packaged user service. Never self-install a helper from QML. |
| Omarchy's native rich panel is `KeyboardPanel`; it handles focus acquisition, all four bar edges, screen fitting, outside-click dismissal, and multi-monitor coordination. [O9] | Use `KeyboardPanel` at a nominal token-scaled width of 380 DIPs. Do not open a separate application window. |
| Omarchy's generic Bluetooth panel already pairs, connects, disconnects, forgets, scans only while open, and exposes one generic device battery. [O12] [O13] [O14] | Reuse the Bluetooth panel for system management. Do not run continuous discovery. Label generic `Battery1` data `Earbuds`, never left/right/case. |
| BlueZ `Device1.Connect()` can succeed when only one profile connects, has no documented `Connecting` property, and exposes `Connected` separately from `ServicesResolved`. [P2] | `Connecting` is a local pending operation. Bluetooth connection is not presented as audio readiness. |
| BlueZ `Battery1` contains one optional byte percentage. [P3] | Generic fallback is a single optional percentage. Component values require the confirmed vendor backend. |
| D-Bus object ownership and BlueZ object paths can disappear and return. [P1] | The helper clears live claims, cancels without replay, takes a fresh object snapshot, and increments a state generation after BlueZ restarts. |
| Quickshell's native Bluetooth singleton does not reliably rebuild after every BlueZ lifecycle failure, and QML-tracked processes die on configuration reload. [P4] [P5] | The systemd user helper, not Quickshell Bluetooth or a QML child process, is the authoritative backend. |
| OpenFreebuds loads handlers independently, models multiple manager states, conditionally shows available fields, and reads ANC state after a write. [C3] [C4] [C5] [C6] | Features fail independently; one missing field never blocks the panel. A noise change is confirmed only by readback. |
| NothingLinux models optional component batteries and separates pending from confirmed writes; KDE and GNOME show bounded busy states during connection changes. [C7] [C8] [C9] [C10] | Keep confirmed state visible under a pending overlay, disable duplicate commands, and bound connect at 30 seconds. |

### 2.3 Explicit evidence limits

The following are not established by Huawei's public material and must not be stated as product facts:

- The FreeBuds Pro 5 vendor transport, channel, framing, authentication, or packet semantics.
- Linux access to left/right/case battery, charging state, current noise state, or writes.
- Write acknowledgement, idempotency, timeout, or firmware compatibility.
- Per-component charging flags. OpenFreebuds exposes one aggregate charging field, which is insufficient to assign charging to a component. [C2]
- Safe vendor polling rate or whether another app can own the control channel concurrently.
- A complete Pro 5 mapping for Dynamic, Cozy, General, Ultra, voice boost, Conversation Awareness, or other submodes.

## 3. Product Definition

### 3.1 Product statement

`FreeBuds Pro 5 for Omarchy` is an unofficial local accessory control surface that answers three questions without opening a general settings application:

1. Are my selected earbuds connected to this computer?
2. What trustworthy battery information is currently available?
3. What top-level noise state is confirmed, and can I change it explicitly?

### 3.2 Goals and measurable outcomes

| Goal | Required outcome |
|---|---|
| Glanceability | A connected user can read the conservative earbud battery metric from a horizontal bar without opening the panel. |
| Fast control | A verified connected user can select a top-level noise state in two inputs: open, then choose. |
| Honest degradation | No unavailable, stale, aggregate, or historical value is presented as a current component value. |
| Native operation | The widget supports top, bottom, left, and right bars; all configured monitors; live theme and text-size changes; pointer and keyboard operation. |
| Safe failure | No adapter, BlueZ loss, unsupported firmware, malformed data, command ambiguity, helper crash, or rolling update can cause a vendor write, false success, shell crash, or restart loop. |
| Local privacy | Runtime network traffic is zero, and neither telemetry nor recording content is collected or uploaded. |

No usage analytics are collected. Success is determined by the acceptance tests, support reports, and opt-in issue reports.

## 4. Scope

### 4.1 MVP

| ID | Included behavior |
|---|---|
| M-01 | One persistent `freebuds.pro5` bar widget, `allowMultiple: false`, default right section, documented placement after `omarchy.bluetooth`. |
| M-02 | One selected, paired FreeBuds Pro 5 pair across all monitors. |
| M-03 | No-adapter, adapter-off, unpaired, unverified, disconnected, connecting, connected, limited, and service-failure states. |
| M-04 | Explicit `Connect`; no automatic connect initiated by the plugin. |
| M-05 | Generic aggregate battery fallback and capability-gated left, right, and case values with source and freshness. |
| M-06 | Explicit `Off`, `Awareness`, and `Noise cancellation` controls for allowlisted protocol/firmware only. |
| M-07 | Native handoff to Omarchy Bluetooth for pairing, disconnect, forget, and adapter power. |
| M-08 | First-run setup, device selection when more than one candidate exists, missing-helper repair guidance, and local troubleshooting. |
| M-09 | Session-scoped systemd user helper, same-UID local IPC, crash supervision, schema handshake, and rolling-update failure handling. |
| M-10 | Keyboard, Qt accessibility metadata, contrast, scale, constrained-layout, all-edge, and multi-monitor acceptance. |
| M-11 | Git-delivered Omarchy plugin plus a signed Arch/AUR helper package from one versioned source release. |

### 4.2 Non-goals

The following are excluded from `0.1.x` and must not appear as hidden, experimental, or disabled controls:

- General Bluetooth discovery, adapter power, pair, disconnect, forget, trust, or device renaming.
- Support for any model other than FreeBuds Pro 5.
- More than one concurrently displayed or controlled pair.
- Noise-cancellation strength, Dynamic/Cozy/General/Ultra, voice boost, Conversation Awareness, or Adaptive Volume controls.
- EQ, codec selection, low-latency mode, spatial audio, head tracking, volume, mute, microphone, PipeWire profile, or audio-route control.
- Gesture configuration, wear detection, auto-pause, call routing, or voice-assistant settings.
- Multi-device/phone connection management or display.
- Find Device, location history, ringtones, Huawei account integration, or proximity popups.
- Firmware download, update, downgrade, rollback, version policy, or update notifications.
- Smart recording start/stop, recording metadata, recording files, export, or reset.
- Battery-life estimates, predictive drain, or low-battery desktop notifications.
- Automatic popup on case open, connection, or proximity.
- Remote control, HTTP server, LAN binding, cloud sync, telemetry, or crash reporting.
- A standalone desktop app, tray icon, Waybar module, GNOME extension, KDE applet, or mobile UI.
- User-configurable thresholds, polling intervals, labels, or layouts inside the plugin. Bar placement remains an Omarchy concern.
- Translations in MVP. All strings must still be centralized and translation-ready.

## 5. Support Policy

### 5.1 Support tiers

| Tier | Entry condition | Allowed behavior | Visible label |
|---|---|---|---|
| Full | The selected paired device passes the confirmed identity handshake and its protocol/firmware fingerprint is in the release allowlist. | Connect, generic and vendor telemetry, and the three confirmed noise writes. | `Connected to this computer` |
| Limited | The exact model is selected but the protocol fingerprint is unknown, the vendor channel is unavailable, or only standard BlueZ data exists. | Standard connect and generic `Earbuds` battery only. No vendor write. | `Limited support` |
| Unsupported | Identity is not verified as FreeBuds Pro 5 or the payload/schema is invalid. | No vendor reads or writes. The device is not adopted as the selected pair. | `This device is not supported` |

At least one fingerprint must qualify for Full before `0.1.0`. New firmware enters Limited until a patch release adds hardware evidence and an allowlist entry. Huawei can update firmware through paired Huawei/Honor devices, so this transition must be safe without user preparation. [H3]

### 5.2 Device selection

- If one previously verified pair exists, select it.
- If no previous selection and exactly one connected candidate named `HUAWEI FreeBuds Pro 5` passes the read-only identity handshake, select it.
- If more than one verified pair exists, show an explicit radio list sorted by escaped alias and then the last four hexadecimal address digits. No pair is selected automatically.
- If a name matches but identity does not, label it unsupported for that session and send no write.
- Persist only the selected BlueZ adapter/device identity and compatibility fingerprint in a mode-`0600` user config file.
- Clear the selection and all cached values as soon as BlueZ reports the device removed or unpaired.
- A renamed device can remain selected only through its persisted verified identity; name matching alone never authorizes a vendor command.

## 6. User Stories

| ID | Exact user story | Acceptance references |
|---|---|---|
| US-01 | As an owner with connected earbuds, I can see a conservative current earbud battery value in the horizontal bar. | BAR-01, TEL-01, TEL-03 |
| US-02 | As an owner, I can open one native panel and distinguish left, right, charging-case, aggregate, missing, stale, and last-seen data. | POP-01, TEL-01 through TEL-10 |
| US-03 | As an owner on verified firmware, I can choose Off, Awareness, or Noise cancellation and see only a readback-confirmed result. | CMD-01 through CMD-08 |
| US-04 | As an owner with a paired disconnected device, I can explicitly connect without changing global Bluetooth or automatically reconnecting at login. | CON-01 through CON-08 |
| US-05 | As a new user, I receive exact pairing instructions and can move into Omarchy Bluetooth without a new pairing implementation. | DEV-01 through DEV-06 |
| US-06 | As a user with no adapter, disabled Bluetooth, unsupported firmware, or partial telemetry, I see a specific truthful state and a safe next action. | ENV-02 through ENV-09, TEL-02 through TEL-08 |
| US-07 | As a user, I can keep using available battery data when one optional feature fails. | TEL-02 through TEL-08, HLP-04 |
| US-08 | As a keyboard or assistive-technology user, I can summon, inspect, operate, and dismiss the panel without a pointer or color-only cue. | A11Y-01 through A11Y-09 |
| US-09 | As a multi-monitor or vertical-bar user, I get one shared state and a panel anchored to the monitor and edge I used. | UI-04 through UI-08 |
| US-10 | As a user during a helper crash, shell reload, or split update, no command is replayed and the UI recovers or fails closed. | HLP-01 through HLP-07, LIFE-01 through LIFE-09 |
| US-11 | As a privacy-conscious user, I can verify that runtime behavior is local, unprivileged, identifier-minimizing, and recording-blind. | SEC-01 through SEC-10 |

## 7. Information And State Model

### 7.1 Authoritative state dimensions

The helper publishes atomic snapshots and ordered deltas. The UI must not collapse these dimensions into one Boolean:

| Dimension | Values |
|---|---|
| Helper | `starting`, `ready`, `restarting`, `failed`, `missing`, `incompatible` |
| BlueZ | `unavailable`, `no-adapter`, `adapter-off`, `ready` |
| Selection | `none`, `candidate`, `verified`, `unsupported` |
| Device | `unpaired`, `disconnected`, `connecting`, `connected` |
| Services | `unresolved`, `resolved`, `vendor-unavailable`, `vendor-ready` |
| Support | `full`, `limited`, `unsupported` |
| Each telemetry field | `unknown`, `fresh`, `stale`, `last-seen`, `unavailable`, `invalid` |
| Operation | `idle`, `pending`, `reconciling`, `failed`, `timed-out`, `result-unknown` |

`Connected` means BlueZ reports the selected device connected to this computer. It does not mean every Bluetooth profile, an audio endpoint, a microphone, or the vendor channel is ready. MVP has no PipeWire dependency. [P2]

### 7.2 Snapshot contract

Every snapshot must contain:

- API major/minor version, monotonically increasing generation, and sequence number.
- Helper and BlueZ states.
- Sanitized selected-device label, paired state, connection state, and support tier.
- Capability booleans for aggregate battery, split battery, case battery, charging, noise read, and noise write.
- For aggregate, left, right, and case: integer percentage or null, source, monotonic observation time, freshness, and presence when confirmed.
- Aggregate charging as `true`, `false`, or `unknown`. Per-component charging remains absent until PC-04 is confirmed.
- Confirmed top-level noise state or null, availability, observation time, and supported choices.
- At most one pending operation with correlation id, kind, target value, start time, and deadline.
- One sanitized error category and stable local error code; never a raw packet, MAC address, serial number, username, or path.

Percentages outside `0` through `100`, non-integers, unknown enums, out-of-order sequences, and timestamps from another generation are invalid. They are discarded, logged without identifiers, and shown as unavailable. They are never clamped.

### 7.3 Rendering precedence

The panel and bar use this strict top-to-bottom precedence:

1. `missing` or `incompatible` helper.
2. Helper `starting`, `restarting`, or `failed`.
3. BlueZ `unavailable`.
4. `no-adapter`.
5. `adapter-off`.
6. No selected verified pair: setup or device selection.
7. `disconnected`.
8. `connecting`.
9. `connected` with Limited support.
10. `connected` with Full support and field-level degradation.

A command error is an inline banner inside the current connection state; it never replaces or falsifies observed connection state.

### 7.4 Required transitions

| From | Event | To | Required side effect |
|---|---|---|---|
| Startup | Helper handshake completes | State from full snapshot | Render no cached QML state before the snapshot. |
| Any ready state | `org.bluez` owner disappears | `BlueZ unavailable` | Increment generation, clear live telemetry, cancel operations without replay. |
| BlueZ unavailable | Owner returns | Snapshot-derived state | Re-enumerate all objects before publishing ready. |
| No adapter | Adapter appears | Adapter-off or ready | Observe only; do not power it or connect. |
| Adapter-off | User enables Bluetooth elsewhere | Setup/disconnected/connected | Observe only. |
| Unpaired | System pairing completes | Candidate or verified | Run read-only identity verification; no vendor write. |
| Disconnected | User presses Connect | Connecting | Start one 30-second local operation and disable duplicate Connect. |
| Connecting | BlueZ `Connected=true` | Connected | Clear pending, then resolve standard and vendor capabilities independently. |
| Connecting | Explicit error or 30-second deadline | Disconnected plus error | Reconcile once; never call Connect again automatically. |
| Connecting timeout | Late `Connected=true` signal | Connected | Clear the old error and accept observed state. |
| Connected | `Connected=false` | Disconnected | Mark values last-seen for this helper session; clear noise selection. |
| Any selected state | Device removed/unpaired | Setup | Delete selected identity and all cached values. |
| Full | Fingerprint changes or becomes unknown | Limited | Disable all vendor writes before publishing the transition. |
| Pending noise command | Matching readback | Full, idle | Commit new confirmed selection. |
| Pending noise command | Mismatch/error/deadline | Full, error | Keep old confirmed selection and report failure/unknown. |
| Any | Helper IPC closes unexpectedly | Restarting | Clear live proprietary claims and wait for systemd. |
| Restarting | Fresh helper snapshot | Snapshot-derived state | Never replay an operation that was pending before the disconnect. |
| Any | Shell/plugin reload | Fresh helper snapshot | Popup closes; helper survives; no command replay. |

## 8. Telemetry Rules

### 8.1 Source precedence

Use exactly one earbud presentation at a time:

1. If left and right are both valid, render component rows and compute the bar metric from them.
2. If split data is incomplete and a valid generic or vendor aggregate exists, render `Earbuds` and suppress the incomplete left/right rows; retain a separately valid case row.
3. If no aggregate exists, render each valid component independently and mark missing expected fields `Not reported`.
4. `Charging case` is never included in the bar metric.

Generic BlueZ `Battery1` is always labeled `Earbuds`; its `Source` may be recorded internally but never turns the value into left, right, or case. [P3]

### 8.2 Bar battery metric

- With fresh left and right values, show the lower percentage.
- With one explicitly present earbud and the other explicitly absent, show the present earbud value.
- With one missing field but no confirmed absence, show `--` unless a fresh aggregate exists.
- With a fresh aggregate, show it.
- With stale, last-seen, invalid, or unavailable data, show `--`.
- Round no values; display the integer supplied after validation.

The lower-bud rule is a deliberate conservative product decision, not an assertion about Huawei's own combined value.

### 8.3 Freshness

| Field/state | Rule | Rendering |
|---|---|---|
| Fresh earbud/aggregate | Successful observation at most 130 seconds old while BlueZ remains connected | Numeric value without age in bar; popup may say `Updated just now` |
| Stale earbud/aggregate | Connected and older than 130 seconds but at most 10 minutes | No bar value; popup shows value plus `Last updated N min ago` and `Battery data is out of date.` |
| Expired earbud/aggregate | Older than 10 minutes | `Not reported`; old number is removed |
| Case | Every value includes age because Huawei says it updates only after earbuds enter the case. [H4] | `54% - Last reported 8 min ago`; never used in bar |
| Disconnected | Value was valid before this session's disconnect | Popup prefixes `Last seen`; bar shows no percentage |
| Helper restart, unpair, device switch, logout | Any cached field | Delete it; no telemetry persistence |

The helper uses notifications when PC-05 confirms them. If validated polling is required, it performs no more than one read-only battery query per 60 seconds while connected, plus one query when the panel opens if the last attempt is older than 15 seconds. Until polling safety is confirmed, it does no proprietary polling and relies on standard BlueZ plus confirmed unsolicited updates.

### 8.4 Low battery and charging

- Earbud or aggregate `11%` through `20%` is warning.
- Earbud or aggregate `0%` through `10%` is critical.
- Charging-case `11%` through `40%` is warning and `0%` through `10%` is critical, matching Huawei's Pro 5 case-indicator bands when the buds are absent. [H4]
- Warning and critical states use both a shape/status word and theme color.
- A confirmed aggregate charging state suppresses urgency only for an aggregate row. It never creates left/right/case charging icons.
- Per-component charging indicators remain hidden until PC-04 confirms independent semantics.
- MVP sends no low-battery notification and plays no sound.

## 9. Bar Widget Specification

### 9.1 Placement and lifecycle

- Manifest id: `freebuds.pro5`.
- Kinds: `bar-widget` and `service`.
- `allowMultiple: false`, `defaultSection: right`, category `Hardware`.
- Documented enable placement: immediately after `omarchy.bluetooth`; if no placement is supplied, Omarchy inserts it in the normal right-section fallback. [O5]
- The widget remains visible after installation in every state, including setup and disconnected. Installation expresses intent and the stable position remains a setup/reconnect affordance.
- One visual instance exists per monitor; every instance reads the same singleton state. [O7]
- Left click toggles the panel. Right click, middle click, and wheel do nothing. This avoids hidden disconnect, adapter, volume, or mode actions.
- The plugin never opens its panel automatically.

### 9.2 Visual states

Use one generic monochrome earbud Nerd Font glyph in `BarIconButton`'s optical slot. Never use Huawei artwork or an AirPods silhouette.

| State | Horizontal bar | Vertical or constrained bar | Non-color cue |
|---|---|---|---|
| Checking | Glyph only | Glyph only | Tooltip says `Checking status` |
| Setup required | Glyph plus `Set up` | Glyph plus small setup marker | Text/marker |
| No adapter / BlueZ unavailable | Glyph plus `!` | Glyph plus `!` | Exclamation mark |
| Bluetooth off | Dimmed glyph with slash marker | Same | Slash marker |
| Disconnected | Dimmed glyph | Same | Dim state and tooltip text |
| Connecting | Glyph plus static pending dot and `...` | Glyph plus pending dot | Static dot; no spinner required |
| Connected, fresh metric | Glyph plus `68%` | Glyph only | Numeric text in horizontal mode |
| Connected, no fresh metric | Glyph plus `--` | Glyph plus unknown marker | Dashes/marker |
| Limited support | Available aggregate plus small `!`, otherwise glyph plus `!` | Glyph plus `!` | Exclamation mark |
| Warning battery | Value plus warning triangle | Glyph plus warning triangle | Triangle and number/name |
| Critical battery | Value plus urgent octagon/`!` | Glyph plus urgent marker | Shape and accessible status |
| Helper restarting/failed | Glyph plus `!` | Same | Exclamation mark |

Use `Color.foreground`, popup/bar surface tokens, `Color.muted`, `Color.accent`, and `Color.urgent`; no fixed colors. Use Omarchy's native open-panel edge indicator rather than drawing another selected underline. [O10] [O11]

### 9.3 Tooltip and accessible name

Omarchy displays shared bar tooltips after 400 ms. [O7] The tooltip is one of:

| State | Exact tooltip |
|---|---|
| Checking | `FreeBuds Pro 5: Checking status` |
| Setup | `FreeBuds Pro 5: Setup required` |
| No adapter | `FreeBuds Pro 5: No Bluetooth adapter` |
| Bluetooth off | `FreeBuds Pro 5: Bluetooth is off` |
| Disconnected | `FreeBuds Pro 5: Disconnected from this computer` |
| Connecting | `FreeBuds Pro 5: Connecting` |
| Connected/full | `FreeBuds Pro 5: Earbuds 68%; Noise cancellation` |
| Connected/partial | `FreeBuds Pro 5: Connected; battery data incomplete` |
| Limited | `FreeBuds Pro 5: Connected with limited support` |
| Service error | `FreeBuds Pro 5: Service unavailable` |

Omit battery or noise fragments when unavailable. The dynamic accessible name uses the same visible facts in spoken form, for example `FreeBuds Pro 5, connected to this computer, earbuds 68 percent, noise cancellation`. The glyph itself is ignored by accessibility.

## 10. Popup Specification

### 10.1 Native surface

Use `qs.Ui.Panel` as the bar-widget root and `KeyboardPanel` for the popup. The panel is anchored to the invoking bar button, opens inward from any edge, clamps to that monitor, participates in Omarchy's single-active-popout model, closes on outside click or Escape, and never opens on hover. [O8] [O9]

- Nominal content width: `Style.space(380)`, clamped by `fittedContentWidth`.
- Maximum content height: the smaller of intrinsic height, `Style.space(560)`, and available monitor height.
- Body scroll: vertical only when content does not fit.
- Popup margin, padding, gaps, typography, corners, borders, hover, selection, and focus use Omarchy semantic tokens. [O10] [O11]
- No explicit Close or Done button.
- Opening starts with the native panel key catcher; the first navigation key reveals the cursor without changing a value.
- Closing returns keyboard control to the application that had focus before the layer-shell panel opened.

### 10.2 Anatomy

```text
+--------------------------------------+
| [generic earbud] FreeBuds Pro 5      |
|                   CONNECTED TO THIS  |
|                   COMPUTER           |
|--------------------------------------|
| BATTERY                              |
| Left earbud                 72%       |
| Right earbud                68%       |
| Charging case               54%       |
|                      Last reported 8m |
|--------------------------------------|
| NOISE CONTROL                        |
| [ Off ] [ Awareness ] [ Noise canc. ]|
|--------------------------------------|
| Open Bluetooth       Change device   |
+--------------------------------------+
```

The actual `Noise cancellation` label is never abbreviated; responsive layout stacks controls when it does not fit. Battery is rendered as text plus a slim linear progress indicator, not circles. The compact hero contains only a generic glyph, fixed model title, and status; there is no product image.

### 10.3 Sections

| Section | Rule |
|---|---|
| Hero | Always visible. Fixed title `FreeBuds Pro 5`; uppercase native-style status caption; no untrusted alias in rich text. |
| State guidance | Replaces normal sections for missing dependency, no adapter, Bluetooth off, setup, unsupported, or failed helper. |
| Battery | Visible when connected or session last-seen values exist. Uses aggregate-or-components rules from Section 8. |
| Noise control | Visible only for a verified connected model. Enabled only when the release allowlist authorizes writes. |
| Inline error | Appears immediately below the affected section; remains until success, connection/support transition, or 30 seconds after the panel closes. |
| Footer actions | `Open Bluetooth` is always offered when the native Bluetooth target exists. `Change device` appears after a pair is selected. |

### 10.4 Controls

| Control | Availability | Exact behavior |
|---|---|---|
| Bar trigger | Always | Toggle this panel. |
| `Connect` | Verified paired and disconnected, adapter ready | Send one standard BlueZ connect request; keep panel open. |
| `Off` | Full support, connected, noise write available | Send explicit Off command, then read back. |
| `Awareness` | Same | Send explicit Awareness command, then read back. |
| `Noise cancellation` | Same | Send top-level Noise cancellation without exposing or changing a strength submode beyond the confirmed protocol mapping. |
| `Try again` | Recoverable connect, read, or dependency error | Perform one user-requested reconciliation or operation. Never replay an old command. |
| `Restart service` | Helper failed after restart limit | Reset the user-unit failure counter and start once through argv-form `systemctl --user`; no shell string and no privilege prompt. |
| `Open Bluetooth` | Omarchy Bluetooth panel target available | Close this panel and open `omarchy.bluetooth`; pairing, adapter power, disconnect, and forget happen there. |
| `Open setup help` | Native Bluetooth target or helper unavailable | Open the packaged local troubleshooting document; no network request. |
| `Change device` | A selected pair exists | Replace body with verified-candidate radio list. Choosing a different pair clears displayed telemetry and never auto-connects it. |

There is no Disconnect control in this panel. There is no manual battery refresh control; opening the panel already requests a safe read if allowed.

### 10.5 Noise command semantics

1. Keep the last confirmed radio selection checked.
2. Give the requested control a pending outline and show `Changing...`.
3. Disable all three choices until completion.
4. Attach a correlation id and a five-second total confirmation deadline.
5. Accept success only when a fresh readback equals the requested top-level state.
6. On explicit reject or mismatch, keep the old selection and show failure copy.
7. On timeout, reconcile once. If readback matches, accept success; if it differs, show failure; if unavailable, show result unknown.
8. Never retry a write automatically. `Try again` is a new explicit user action.
9. If shell/helper reloads or the device disconnects while pending, discard the pending overlay and query state after recovery; never reissue.
10. A device-originated mode change updates the confirmed selection when a valid event/readback arrives.

Unknown raw modes leave all three unselected with `Current noise state is not reported.` Known ANC strength or transient submodes map to `Noise cancellation` only after PC-06 defines that mapping. Conversation Awareness maps to `Awareness` only after the same confirmation; otherwise it is unknown.

### 10.6 Connect semantics

- Connect is always explicit and never runs on login, plugin load, case open, resume, adapter return, or helper restart.
- Pending feedback appears within 100 ms.
- Duplicate connect is disabled.
- A BlueZ method reply is not success; `Connected=true` is required. [P2]
- The local deadline is 30 seconds, following comparable shell bounded-transition behavior. [C10]
- A timeout never calls Disconnect and never retries. A late observed connection is accepted and clears the error.
- The plugin never changes default audio output or PipeWire state.

## 11. Responsive Layout

| Context | Required layout |
|---|---|
| Top/bottom bar, sufficient width | Glyph plus selected state text from Section 9. |
| Top/bottom bar, slot cannot fit glyph plus four-character battery text | Glyph only; tooltip and accessible name retain the value. |
| Left/right bar | Glyph-only status with marker; never rotate or wrap percentage text. |
| Panel at 380 DIPs | Noise choices appear in one row only when all complete labels and 24-DIP hit targets fit. |
| Panel below the controls' combined implicit width | Noise choices stack vertically in order Off, Awareness, Noise cancellation. |
| Available width 320 DIPs | No horizontal scroll, clipping, label abbreviation, or hidden action. |
| Available height 256 DIPs | Hero remains fixed; body scrolls on one vertical axis; every action remains reachable. |
| Text size 20 px or Qt scale 2 | Same fit rules; labels wrap to two lines where needed; panel remains one-axis scrollable. |
| Multiple monitors | Each bar instance shows the same snapshot; popup anchors to the invoked instance's monitor; one popup is active. |
| Monitor hot-unplug | Close a popup on the removed output and preserve helper/selection state on remaining bars. |

Use DIPs and Omarchy/Qt scaling. Do not multiply geometry by device-pixel ratio; use font glyphs or vectors. [A7]

## 12. Exact Copy Catalog

All user-facing strings use sentence case except Omarchy's native uppercase section/status captions.

| Situation | Title/status | Body | Primary action |
|---|---|---|---|
| Startup under 3 seconds | `Checking FreeBuds...` | `Reading local Bluetooth status.` | None |
| Helper missing | `Setup incomplete` | `The FreeBuds helper is not installed.` | `Open setup help` |
| Helper incompatible | `Update required` | `The widget and helper versions do not match. Update both from the same release.` | `Open setup help` |
| Helper restarting | `Restarting FreeBuds service...` | `Controls will return after a fresh device snapshot.` | None |
| Helper failed | `FreeBuds service unavailable` | `The local helper stopped repeatedly.` | `Restart service` |
| BlueZ absent | `Bluetooth service unavailable` | `The system Bluetooth service is not running.` | `Try again` |
| No adapter | `No Bluetooth adapter` | `No Bluetooth adapter was found on this computer.` | `Open setup help` |
| Adapter off | `Bluetooth is off` | `Turn on Bluetooth in the Omarchy Bluetooth panel.` | `Open Bluetooth` |
| Unpaired | `Set up FreeBuds Pro 5` | `Place both earbuds in the open case. Hold the Function button for at least 2 seconds, until the indicator flashes white. Then select HUAWEI FreeBuds Pro 5 in Bluetooth.` | `Open Bluetooth` |
| Setup privacy line | None | `Runs locally. No Huawei account or internet connection is used.` | None |
| Multiple verified pairs | `Choose earbuds` | `Select the FreeBuds Pro 5 pair to show in the bar.` | `Use this device` |
| Candidate verifying | `Verifying FreeBuds Pro 5...` | `No controls are sent during verification.` | None |
| Unsupported identity | `This device is not supported` | `This release supports verified FreeBuds Pro 5 devices only.` | `Open Bluetooth` |
| Paired/disconnected | `Disconnected from this computer` | `Connect to read battery levels and noise control.` | `Connect` |
| Connecting | `Connecting...` | `Keep the earbuds nearby and out of the closed case.` | None |
| Connect failed | `Couldn't connect` | `Put the earbuds nearby and try again.` | `Try again` |
| Connect timed out | `Connection result unknown` | `The connection took longer than 30 seconds. Current Bluetooth state will still be observed.` | None |
| Connected/resolving | `Connected to this computer` | `Loading device details...` | None |
| Connected/full | `Connected to this computer` | None | None |
| Limited firmware | `Limited support` | `This firmware has not been verified. Detailed battery and noise control are disabled.` | `Open setup help` |
| Vendor channel unavailable | `Limited support` | `The earbuds are connected, but device details are unavailable.` | `Try again` |
| Partial battery | `Battery data is incomplete.` | `Available values are shown separately.` | None |
| Stale battery | `Battery data is out of date.` | `Reconnect or open the case with the earbuds inside to refresh available values.` | None |
| Missing field | `Not reported` | None | None |
| Case no sample | `Not reported` | `Place the earbuds in the open case to refresh the charging-case level.` | None |
| Noise mode unavailable | `Noise control is unavailable in the current earbud state.` | None | None |
| Noise state unknown | `Current noise state is not reported.` | None | None |
| Noise pending | `Changing...` | None | None |
| Noise reject/mismatch | `Couldn't change noise control.` | `The previous confirmed setting is still shown.` | `Try again` |
| Noise timeout/unreadable | `Couldn't confirm the change.` | `Check the earbuds, then try again.` | `Try again` |
| Disconnect during command | `The earbuds disconnected before the change was confirmed.` | None | None |
| Bluetooth panel unavailable | `Bluetooth panel unavailable` | `Open Omarchy setup and choose Bluetooth.` | `Open setup help` |
| Access denied | `FreeBuds access denied` | `The local helper cannot access the Bluetooth service.` | `Open setup help` |

No raw exception, packet, process output, MAC address, serial number, or stack trace appears in the panel.

## 13. Setup And Onboarding

### 13.1 Installation flow

Omarchy's plugin manager cannot run a build or helper install hook. [O3] The supported setup is therefore deliberately two-part and reviewable:

1. Install the signed `freebuds-pro5-helper` Arch/AUR package through Omarchy's package command.
2. Add the public Git plugin with `omarchy plugin add`, review the warning/source, and enable `freebuds.pro5` after `omarchy.bluetooth`.
3. Open the widget. The socket-activated helper starts without `sudo`, a root daemon, linger, or a second setup command.

The release README contains the canonical repository URL and exact commands. The popup never executes package installation, `sudo`, `curl`, a shell pipeline, or a network download.

### 13.2 First open

1. Check helper API, BlueZ owner, adapter, and paired candidates without active discovery.
2. If already paired and connected, perform read-only verification and enter Full or Limited.
3. If unpaired, show the exact copy from Section 12 and switch to Omarchy Bluetooth on explicit action. Omarchy Bluetooth owns scanning and pairing and stops discovery when its panel closes. [O14]
4. When BlueZ reports pairing/connection, verify identity. Do not require the user to press a refresh button.
5. If one verified pair exists, select it. If several exist, require selection.
6. On first successful selection, transition directly to the normal panel; no success modal, animation, toast, or account prompt.

The setup panel can be dismissed at any time. The bar remains in `Set up` state. The plugin never suggests factory reset; Huawei says reset can erase Smart recordings. [H8]

### 13.3 Returning setup

`Change device` reopens candidate selection. Unpairing clears selection and returns to setup. Reinstalling can reuse the mode-`0600` selected-device record only if BlueZ still reports the same paired identity and verification still passes.

## 14. Degraded And Dependency Behavior

| Failure | Detection | Required behavior | Recovery |
|---|---|---|---|
| Helper package absent | Socket/service unit not found | Bar `!`; setup-incomplete copy; no Bluetooth claims or shell retry loop | Local setup help |
| Helper API major mismatch | Handshake version mismatch | Clear proprietary state and all writes; show Update required | Update plugin and helper; current/previous minor remain wire-compatible |
| Helper startup slower than 3 seconds | No valid handshake | Show Restarting/Checking, not disconnected | Continue until systemd result or 10-second setup error |
| Helper crash | IPC EOF/process failure | Immediately clear live proprietary fields; show Restarting | systemd `Restart=on-failure`, 2-second delay |
| Helper crash loop | Three starts in 60 seconds fail | Stop automatic restart; show Service unavailable | One explicit Restart service resets failure counter |
| BlueZ absent at startup | No `org.bluez` owner | Bluetooth service unavailable; no helper exit | Watch `NameOwnerChanged`, re-enumerate on return [P1] |
| BlueZ restarts | Owner generation changes | Clear live state and pending operations; no replay | Fresh `GetManagedObjects` snapshot |
| No adapter | No `Adapter1` object | No adapter copy; no helper restart | Observe adapter add |
| Adapter off/rfkill | Adapter exists, powered false | Bluetooth-off copy; no global toggle in this panel | Explicit Open Bluetooth |
| Unpaired | Selected device absent or `Paired=false` | Clear selection/data; setup | Pair in Omarchy Bluetooth |
| Paired/disconnected | `Paired=true`, `Connected=false` | No current percentage; explicit Connect | User action only |
| Services unresolved | Connected, services not resolved | Connected plus Loading details; noise disabled | Observe resolution; after 5 seconds enter Limited if vendor unavailable |
| Generic battery absent | No `Battery1` and no vendor value | `Not reported`, never `0%` | Observe interface/telemetry add |
| Partial proprietary telemetry | Some valid fields | Render fields independently under source-precedence rules | Safe read on panel open |
| Invalid payload/field | Schema/range/enum failure | Drop affected field; keep other features; sanitized log | Next valid update |
| Vendor channel failure | Bluetooth remains connected | Limited support; generic features remain; no command | Automatic read-channel reconnect at 1, 2, 5, 10, and 30 seconds, then manual Try again |
| Connect failure | BlueZ error | Return disconnected and show exact error | Explicit Try again |
| Noise command reject | Explicit backend error | Old confirmed state remains | Explicit Try again |
| Noise command timeout | Five-second deadline | Reconcile once; show result unknown if unreadable | Never automatic write retry |
| Omarchy Bluetooth target absent | IPC target unavailable | Do not crash or alter layout; show panel-unavailable copy | Local setup help |
| Permission denied | BlueZ/socket denial | Access-denied copy; no privilege prompt | Local troubleshooting |
| Socket malformed message | JSON/schema failure | Ignore message, close connection after three invalid frames in 60 seconds | Helper reconnect/fail state; shell remains responsive |

Expected device absence, malformed packets, BlueZ outage, and unsupported firmware are states inside the helper. They must not terminate the helper process.

## 15. Accessibility

This product adopts measurable WCAG 2.2 AA-derived desktop targets but does not claim formal WCAG conformance, because WCAG conformance applies to web content.

### 15.1 Semantics and keyboard

- Bar trigger: one `Accessible.Button`, dynamic `Accessible.name`, action-oriented description, and `Accessible.onPressAction` identical to left click. Qt identifies name, description, role, state, and press action as the core QML accessibility contract. [A6]
- Battery rows: `Accessible.StaticText` with names such as `Left earbud battery, 72 percent` and `Charging case battery, 54 percent, last reported 8 minutes ago`.
- Noise choices: one named radio group and three `Accessible.RadioButton` controls with checkable, checked, enabled, pending, and description states.
- Decorative glyphs, progress fills, separators, and duplicate labels: `Accessible.ignored: true`.
- Panel key model: standard right-section `Super+Ctrl+number` summon; first arrow or `h/j/k/l` reveals cursor; arrows or `h/j/k/l` navigate; Enter/Space activates; Escape closes; Tab/Shift+Tab switches neighboring Omarchy panels. This preserves Omarchy's native `PanelKeyCatcher` contract. [O9]
- Pointer hover and keyboard navigation update the same one-cursor model. No action occurs merely on focus or hover.
- A screen-reader press action can open the trigger even though Omarchy's stock `WidgetButton` is not a normal Tab stop.
- Meaningful command success/failure and connection changes are announced once with `Accessible.announce(..., Accessible.Polite)` only while this panel is open. Routine battery polling is never announced. Qt exposes this API from 6.8. [A6]
- No keyboard trap. Closing releases layer-shell focus to the previously focused application.

### 15.2 Visual and motor requirements

- All text has at least `4.5:1` contrast against the final composited background. [A1]
- Meaningful icons, focus outlines, component boundaries, and selected/warning states have at least `3:1` contrast. Color is never the only cue. [A2]
- Every interactive hit rectangle is at least `24 x 24` DIPs; the whole native bar slot is the trigger. [A3]
- Focus/cursor treatment includes a continuous 2-DIP outline or equivalent native border at `3:1` against both focused/unfocused surroundings and is never clipped.
- Status remains visible in text; tooltips and announcements are supplemental.
- No plugin-specific spinner, pulse, flash, rotating phrase, or decorative transition. Omarchy's panel open/close transition may run, but no state depends on motion.
- Test Omarchy text sizes 9 and 20 px and `QT_SCALE_FACTOR` 1, 1.25, 1.5, and 2. [A7]
- At 320 x 256 DIPs and 20-px text, all information and controls remain reachable with vertical scrolling only. [A5]

### 15.3 Claim gate

Do not claim screen-reader support until the actual layer-shell build passes Orca and Accerciser inspection on the supported Omarchy release. The current stock shell has no explicit `Accessible.*` usage, so source-level metadata alone is insufficient. [O17]

## 16. Privacy And Security

### 16.1 Data and privacy

- Runtime IP networking is prohibited. The helper unit enforces `IPAddressDeny=any` while retaining Unix and required Bluetooth access.
- No Huawei ID, OAuth token, account, cloud endpoint, analytics endpoint, update endpoint, or remote-control endpoint exists.
- No microphone, audio stream, Smart recording command, recording file, location, Find Device data, contact, or notification content is accessed.
- No telemetry value, command history, or last-seen battery is persisted.
- Persist only selected adapter/device identity, compatibility fingerprint, setup completion, and config schema version in `$XDG_CONFIG_HOME/freebuds-pro5/config.json`, mode `0600`.
- Store no secret. The Bluetooth address is never displayed in full or written to normal logs; multiple-device selection uses only four suffix digits.
- Raw packet logging is off in every release build. An opt-in debug run is local, time-bounded, visibly warned, and still redacts addresses, serials, username, and paths.
- No automatic crash report. Issue-report diagnostics are copied only after explicit user action and contain versions, state enums, error codes, and redacted identifiers.
- On unpair, delete the selected-device record. The documented purge command deletes all plugin/helper user state before package removal.

OpenFreebuds demonstrates why remote RPC is excluded: its optional server can bind to all interfaces and expose actions through web routes. [C12] Gadgetbridge provides the preferable local/no-vendor-account precedent. [C13]

### 16.2 Trust boundary

- Treat Bluetooth names, aliases, addresses, object paths, D-Bus errors, helper JSON, and vendor packets as untrusted.
- Escape all displayed text and render it as plain text, never rich text.
- Name matching discovers candidates only. A read-only capability handshake and release allowlist authorize writes.
- Vendor commands target only the selected paired object from the current BlueZ generation.
- Use structured argv arrays, not `bar.run()` or interpolated shell strings, for every process action. Omarchy's `bar.run()` reaches `bash -lc`. [O7]
- IPC uses one Unix-domain socket under `$XDG_RUNTIME_DIR/freebuds-pro5/helper.sock`, owner-only directory and socket mode `0600`, newline-delimited versioned JSON, bounded frame size, and same-UID peer validation. No TCP or HTTP listener exists.
- Helper runs as the user. It never requests root, sudo, polkit, Linux capabilities, or linger.
- Required systemd hardening: `NoNewPrivileges=yes`, `PrivateTmp=yes`, read-only system paths, private writable state directory, bounded memory/tasks, and address-family restriction to Unix plus the confirmed Bluetooth transport.
- No firmware, reset, trust, pairing, recording, filesystem-export, or arbitrary vendor command is implemented.
- Fuzz decoded packets and IPC frames. One malformed feature must fail closed without killing the process or desktop shell.

### 16.3 Supply chain and licensing

- Plugin source is public and reviewable because Omarchy runs it unsandboxed in the desktop shell. [O17]
- Project license: `GPL-3.0-or-later` for original QML/helper code.
- Do not copy OpenFreebuds, NothingLinux, Gadgetbridge, KDE, GNOME, or HeadsetControl code. Maintain a provenance ledger for protocol facts and implement independently. Their licenses range from MIT/LGPL to GPL/AGPL. [C14]
- Do not ship Huawei firmware, app code, images, logos, sounds, fonts, or packet captures containing user identifiers.
- UI carries an `Unofficial; not affiliated with Huawei` notice in local documentation, not in the compact panel.

## 17. Product Architecture Contract

### 17.1 Components

| Component | Responsibility | Must not do |
|---|---|---|
| Bar/panel entry point | Render per-monitor bar trigger and native `KeyboardPanel`; route user actions | Poll, decode protocol, own long-lived process, store state |
| Omarchy singleton service | Maintain one IPC client, validate snapshots, expose immutable QML state to every monitor | Speak vendor protocol, invoke shell strings, persist telemetry |
| systemd user helper | Own BlueZ lifecycle, selected identity, standard battery, confirmed vendor channel, commands, freshness, and complete snapshots | Render UI, use IP network, auto-connect, auto-retry writes |
| systemd user socket/service | Same-UID activation and crash supervision | Run as root, linger after logout |
| Local config | Selected verified identity and schema only | Store telemetry, history, raw packets, recording data |

### 17.2 Lifecycle

- The plugin's QML service connects to the socket; socket activation starts one helper.
- The helper survives QML/plugin reload and full shell restart within the graphical session and publishes a complete snapshot before deltas.
- No helper runs before a graphical-session client requests it and none remains after logout. Linger is disabled.
- The service uses `Restart=on-failure`, `RestartSec=2s`, `StartLimitIntervalSec=60s`, and `StartLimitBurst=3`. systemd recommends `Restart=on-failure` for long-running services and applies explicit rate limits. [P7] [P8]
- Missing adapter, disconnected device, BlueZ restart, unsupported firmware, malformed packet, and command failure do not exit the helper.
- A BlueZ owner change creates a new generation and invalidates every object, timestamp, and pending operation from the old generation.
- QML never uses Quickshell Bluetooth as an independent source of truth. The built-in Omarchy Bluetooth panel remains a separate explicit management surface.

### 17.3 IPC operations

The public local interface contains only:

| Operation | Preconditions | Result |
|---|---|---|
| `GetSnapshot` | Valid API handshake | Complete current generation |
| `SelectDevice` | Candidate is paired; read-only identity verification succeeds | New snapshot, cleared old telemetry |
| `Connect` | Verified selected pair, adapter ready, disconnected | Correlated pending result; no auto retry |
| `SetNoiseMode` | Full support, connected, exact mode enum | Correlated write plus readback result |
| `Refresh` | Connected; safe query capability confirmed | Read-only field updates only |
| `RetryVendorChannel` | Connected Limited state | One connection/read synchronization attempt |
| `ForgetSelection` | Any selected state | Local selection deletion only; does not unpair BlueZ |
| `GetSanitizedDiagnostics` | Explicit panel action | No raw identifiers or packets |

There is deliberately no `Pair`, `Disconnect`, `PowerAdapter`, `ForgetBluetoothDevice`, `Reset`, `FirmwareUpdate`, `Recording`, arbitrary packet, shell, file, or URL operation.

### 17.4 Performance and resource budgets

| Metric | Acceptance target |
|---|---|
| Cached panel open to painted content | p95 at most 100 ms |
| Helper event to all bar instances | p95 at most 250 ms |
| Pending feedback after user action | at most 100 ms |
| Initial generic state after helper starts | at most 2 seconds when BlueZ responds |
| First vendor details after connected/services resolved | at most 5 seconds or enter Limited |
| Noise confirmation deadline | 5 seconds total |
| Connect deadline | 30 seconds |
| Helper idle CPU, connected with panel closed | under 0.2% average over 10 minutes |
| Helper resident memory | under 30 MiB |
| Proprietary battery reads | at most one per 60 seconds, only after PC-05 |
| Active Bluetooth discovery by this plugin/helper | zero |
| QML warnings, binding loops, blocked-frame events | zero in acceptance runs |

## 18. Packaging, Installation, Updates, And Release

### 18.1 Repository and manifest

One public Git repository contains the root plugin manifest, QML, local documentation, helper source, packaging files, tests, license, and provenance records. The root manifest is ready to load without building and declares:

```json
{
  "schemaVersion": 1,
  "id": "freebuds.pro5",
  "name": "FreeBuds Pro 5",
  "version": "0.1.0",
  "kinds": ["service", "bar-widget"],
  "entryPoints": {
    "service": "Service.qml",
    "barWidget": "Panel.qml"
  },
  "barWidget": {
    "displayName": "FreeBuds Pro 5",
    "description": "Battery and noise control for verified Huawei FreeBuds Pro 5 earbuds",
    "category": "Hardware",
    "allowMultiple": false,
    "defaultSection": "right"
  }
}
```

`freebuds.pro5` satisfies Omarchy's id rules and does not claim the reserved `omarchy.*` namespace. Manifest schema 1 cannot express dependencies or minimum shell versions, so release documentation and runtime preflight must enforce them. [O4]

### 18.2 Distribution units

| Unit | Contents | Update owner |
|---|---|---|
| Omarchy plugin Git checkout | Manifest, QML, bundled generic icon fallback, local setup/troubleshooting/privacy docs | `omarchy plugin update freebuds.pro5` |
| `freebuds-pro5-helper` Arch/AUR package | Helper binary, user socket/service units, license, local man page, purge/diagnostic CLI | Omarchy/Arch package update |
| Signed source release | Exact source for both units, checksums, SBOM, changelog, support manifest | Project release |

The plugin installer runs no hooks, so the plugin must render Setup incomplete when the helper package is absent. The QML checkout must never contain an opaque prebuilt helper or download one at runtime.

### 18.3 Version compatibility

- Product and helper use semantic versions.
- IPC API major mismatch fails closed with Update required.
- Each release supports its own and the immediately previous IPC minor so users can update the two distribution units in either order. The split installer creates this concrete rolling-update need.
- Feature availability is the intersection of both sides' advertised minor capabilities.
- Unknown fields/enums are ignored, never treated as defaults.
- Config contains a schema version and is atomically migrated. A failed migration preserves a timestamped backup and returns to setup without deleting the original.
- Omarchy's manifest version is informational; the product performs its own helper handshake. Omarchy updates Git checkouts by fast-forward, validates afterward, and rolls back a validation failure. [O6]
- The default branch contains releases only because Omarchy updates from `origin HEAD`; development occurs on branches.
- No runtime update check or background network access exists.

### 18.4 Removal

The documented removal sequence is decisive:

1. Run the helper's unprivileged `purge` command to stop the user service and delete `$XDG_CONFIG_HOME/freebuds-pro5`.
2. Remove `freebuds.pro5` through `omarchy plugin remove`.
3. Remove the `freebuds-pro5-helper` package through Omarchy's package manager.

Omarchy has no uninstall hook and does not clean external dependencies, so documentation and package tests must cover all three steps. [O3]

### 18.5 Release artifacts and gates

Every release must provide:

- Signed annotated Git tag and signed `SHA256SUMS`.
- Source tarball; no binary-only release.
- Reproducible Arch/AUR recipe tied to the signed source tag.
- SPDX or CycloneDX SBOM.
- `CHANGELOG.md`, install/update/remove instructions, privacy statement, security contact, local troubleshooting guide, and exact Omarchy compatibility.
- Tested hardware table containing model, region, firmware/protocol fingerprint, Bluetooth adapter/chipset, BlueZ, Omarchy, Quickshell package, and helper version; Bluetooth addresses are redacted.
- Protocol provenance and third-party license audit.
- Automated test report, accessibility report, and signed physical-hardware checklist.
- No Huawei assets and a clear unofficial/non-affiliation statement.

Release support is current stable Omarchy 4.0.0 on x86_64 only. Installer/preflight refuses an untested Omarchy major or Qt below 6.8 with a local compatibility message; it does not attempt a compatibility shim.

## 19. Acceptance Strategy

### 19.1 Test layers

| Code | Layer | Purpose |
|---|---|---|
| U | Pure model/unit | State reduction, source precedence, timestamps, copy, validation, command reconciliation |
| Q | QML component/in-process fake | Rendering, keyboard, accessibility tree, responsive layout, multi-instance behavior |
| I | Integration with fake BlueZ/helper/socket/systemd | Lifecycle, ordering, timeout, malformed data, dependency and crash behavior |
| V | Clean Omarchy VM | Install, plugin validation, native panel coordination, update, removal, theme, shell restart |
| H | Actual retail FreeBuds Pro 5 | Identity, transport, telemetry, writes, radio/audio coexistence, firmware |
| M | Manual inspection/measurement | Visual contrast, Orca speech, package provenance, privacy and hardware observations |

The deterministic helper fixture must generate every state, field combination, generation change, out-of-order message, error, and deadline without physical hardware. The fake BlueZ bus must support owner loss/return and object add/remove/property changes. Hardware tests supplement these layers; they never replace fault injection.

Every row below is required. `0.1.0` has no expected failures, waivers, or “works on my machine” substitutions.

## 20. Acceptance-Test Matrix

### 20.1 Environment, dependency, and onboarding

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| ENV-01 | Clean supported Omarchy; install helper package; add, review, enable plugin after Bluetooth | One bar instance per monitor, one helper, no QML warning, manifest validates, setup panel opens | V |
| ENV-02 | `org.bluez` has no owner at helper start | Bar shows `!`; popup uses exact Bluetooth-service-unavailable copy; all device controls disabled; helper stays running | I, V |
| ENV-03 | BlueZ owns name but exposes no `Adapter1` | Exact no-adapter bar/popup; no restart, discovery, power, connect, or vendor call | I |
| ENV-04 | Adapter exists with power off/rfkill | Exact Bluetooth-off state; only `Open Bluetooth`/help is available; this plugin does not toggle power | I, V |
| ENV-05 | Helper package absent | Exact Setup incomplete state within 3 seconds; no process loop or raw socket error; local help opens | Q, V |
| ENV-06 | Helper API major differs | Exact Update required state; no cached telemetry or command; versions appear only in sanitized diagnostics | I, V |
| ENV-07 | Socket or BlueZ access returns permission denied | Exact access-denied state; no sudo/polkit prompt; helper does not retry in a tight loop | I |
| ENV-08 | Omarchy version/Qt below supported minimum | Install/preflight stops before enabling and gives local compatibility instructions | V |
| ENV-09 | `omarchy.bluetooth` widget/IPC target is absent | FreeBuds panel still works; `Open Bluetooth` produces exact panel-unavailable copy and local help; user layout is not altered | Q, V |
| ENV-10 | Runtime outbound IP is blocked and monitored | Normal setup/connected behavior works; helper and QML make zero DNS, TCP, UDP, or HTTP requests | V, M |
| DEV-01 | No selected or paired matching device | Persistent `Set up` bar state; exact three-step pairing copy; no active discovery by helper | Q, I |
| DEV-02 | User invokes `Open Bluetooth` from setup | FreeBuds panel closes and native Bluetooth panel opens on same output; scanning belongs only to that panel | V |
| DEV-03 | One named candidate pairs and connects, then read-only identity succeeds | Candidate becomes selected; main panel appears without toast; no vendor write occurred | I, H |
| DEV-04 | Exact-name spoof or unsupported FreeBuds model fails identity | Unsupported copy; no selection persistence and zero vendor writes | I, H |
| DEV-05 | Two verified pairs, no previous selection | Radio list appears in deterministic order; neither is auto-selected or auto-connected; full address is hidden | Q, I |
| DEV-06 | Selected pair is removed/unpaired while panel is open | Immediate setup transition; selection and all values deleted; no reset guidance | I, H |

### 20.2 Bar and popup fundamentals

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| BAR-01 | Full connected snapshot with L72/R68/case54/noise cancellation | Horizontal bar shows generic glyph plus `68%`; tooltip/accessibility state contains 68% and noise; case is excluded | U, Q |
| BAR-02 | Full connected snapshot on left or right bar | Icon-only state; no rotated/clipped percentage; tooltip retains complete facts | Q, V |
| BAR-03 | Disconnected with session last-seen values | Bar is dim and has no percentage; popup qualifies values `Last seen` | U, Q |
| BAR-04 | Partial split data with no aggregate and unknown presence | Bar shows `--`, never the one available bud as the pair metric; popup shows independent fields | U, Q |
| BAR-05 | Warning and critical thresholds crossed | Numeric/shape/color/accessibility status all change exactly at specified boundaries; no notification or sound | U, Q |
| BAR-06 | Right click, middle click, and wheel in every state | No action, state mutation, command, adapter change, disconnect, or volume change | Q, V |
| BAR-07 | Widget exists on two monitors and state changes | Both instances update within 250 ms from one singleton snapshot; only one helper connection exists | Q, I, V |
| POP-01 | Left click or standard right-section keyboard summon | One native `KeyboardPanel` opens at the invoking bar instance; second invocation closes it | Q, V |
| POP-02 | Click outside on same/other monitor or press Escape | Panel closes, no command is cancelled/replayed, and previous application regains keyboard control | Q, V |
| POP-03 | Open another Omarchy panel while FreeBuds is open | Native one-popout handoff occurs in one input with no overlapping card | V |
| POP-04 | Connected full state | Hero, battery, noise, and footer sections appear in specified order with exact complete labels and no product image/circular gauge | Q, M |
| POP-05 | Close panel during Connect or noise pending, then reopen | Operation continues once in helper; reopened panel reflects observed/pending/result state; no duplicate call | I, V |

### 20.3 Connection state

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| CON-01 | Verified paired disconnected; press Connect | Connecting state and pending cue appear within 100 ms; button and duplicates disabled; one BlueZ call | U, I |
| CON-02 | BlueZ method returns success but `Connected` remains false | UI remains Connecting until event/deadline; it does not claim success | I |
| CON-03 | `Connected=true` within deadline, services unresolved | Connected copy appears immediately; details say Loading; no audio-readiness claim | I |
| CON-04 | Services/vendor channel become ready independently | Generic fields appear first; vendor fields and controls appear only when each capability is ready | I |
| CON-05 | BlueZ returns explicit connect error | Return to disconnected; exact Couldn't connect copy; one explicit Try again available | I |
| CON-06 | No final result for 30 seconds | End local pending; exact result-unknown copy; no Disconnect or retry is sent | U, I |
| CON-07 | `Connected=true` arrives after timeout | Accept connected observation and clear timeout banner; never issue another Connect | I |
| CON-08 | Login, shell start, case open, adapter return, resume, helper restart | Plugin sends zero Connect requests; externally initiated connection is observed | I, V, H |
| CON-09 | Connected Bluetooth device has no PipeWire node | Remain Connected; no audio error and no PipeWire dependency | I, H |
| CON-10 | Disconnect occurs with popup open | Immediate disconnected state; controls disabled; live values become session `Last seen`; no stale bar percentage | I, H |
| CON-11 | Disconnect while noise command pending | Pending discarded; exact disconnected-before-confirmation copy; no write replay on reconnect | I, H |
| CON-12 | Device reconnects through OS policy without plugin command | Direct transition to connected/resolving; helper synchronizes read-only state | I, H |

### 20.4 Battery and partial telemetry

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| TEL-01 | Valid left, right, case fields with timestamps | Three correctly labeled rows; bar uses lower bud; case includes age | U, Q, H |
| TEL-02 | Huawei/backend supplies one aggregate only | One `Earbuds` row and aggregate bar value; no fabricated left/right; case appears only if separately valid | U, Q, H |
| TEL-03 | Left/right nearly equal but only aggregate supplied | Aggregate remains valid; UI does not treat missing split values as an error | U, Q, H |
| TEL-04 | Left fresh, right missing, aggregate fresh | Render aggregate instead of incomplete split; valid case remains independent | U, Q |
| TEL-05 | Left fresh, right explicitly absent, no aggregate | Render left and use it as bar metric; accessible description says one earbud is present | U, Q, H |
| TEL-06 | Left fresh, right missing without absence, no aggregate | Popup shows left and right Not reported; bar `--`; incomplete note | U, Q |
| TEL-07 | No `Battery1` or vendor battery | Not reported, never 0%; no low-battery styling | U, I |
| TEL-08 | Values include -1, 101, float, unknown sentinel, stale generation, or invalid JSON | Reject affected field/message; preserve valid independent fields; no shell/helper crash | U, I |
| TEL-09 | Earbud value ages past 130 seconds then 10 minutes | Bar changes to `--` at 130 seconds; popup shows stale age; number is removed at 10 minutes | U, Q |
| TEL-10 | Case value ages while buds are outside case | Case remains explicitly `Last reported`; bar unaffected; no inference that value is current | U, Q, H |
| TEL-11 | Helper, shell session, or selected device changes | Cached telemetry follows Section 8 deletion rules; no value leaks across device/generation/session | U, I |
| TEL-12 | Aggregate charging true but per-component charging unknown | Only aggregate row can say Charging; no left/right/case charging glyph | U, Q, H |
| TEL-13 | Warning boundaries: buds 21/20/11/10; case 41/40/11/10 | Exact normal/warning/critical transitions and non-color labels pass | U, Q, H |
| TEL-14 | Popup opens twice within 15 seconds, then after 15 seconds | No extra read in first interval; one allowed read after interval; never exceeds confirmed 60-second polling budget | I, H |
| TEL-15 | One proprietary battery feature initialization fails while ANC succeeds | Battery degrades independently; noise remains usable; no global failed state | I, H |

### 20.5 Noise controls and command failure

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| CMD-01 | Confirmed Off; choose Awareness; matching readback | Off remains checked under pending outline; after readback Awareness becomes checked; no success toast | U, Q, I, H |
| CMD-02 | Repeat for each directed pair among Off, Awareness, Noise cancellation | All six transitions confirm on every allowlisted fingerprint | I, H |
| CMD-03 | Double-click or activate another mode while one is pending | One write only; all choices disabled until result | U, Q, I |
| CMD-04 | Backend explicitly rejects write | Old confirmed selection remains; exact Couldn't change copy; no auto retry | U, I, H |
| CMD-05 | Write acknowledges but readback differs | Treat as mismatch/failure; old confirmed state remains | U, I, H |
| CMD-06 | Five-second timeout, reconciliation matches requested state | Treat as success without a second write | U, I, H |
| CMD-07 | Five-second timeout, reconciliation returns old state | Treat as failure; offer explicit Try again | U, I |
| CMD-08 | Five-second timeout, reconciliation unavailable | Exact Couldn't confirm copy; previous confirmed state retained as historical, controls await valid connection state | U, I |
| CMD-09 | Unknown firmware or unverified identity | Noise controls disabled/hidden per Limited/Unsupported; attempts through stale UI/IPC are rejected by helper | U, I, H |
| CMD-10 | Unknown raw mode or unconfirmed transient/submode | No radio selected; exact Current noise state copy; no guessed parent mapping | U, Q, H |
| CMD-11 | Device gesture changes a confirmed top-level mode | Fresh event/readback updates UI on all monitors without a plugin write | I, H |
| CMD-12 | Shell/plugin/helper reload during write | No replay; fresh snapshot determines state; correlation id from old generation is ignored | I, V, H |

### 20.6 Helper, BlueZ, reload, and update lifecycle

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| HLP-01 | Kill helper once while connected | UI changes to Restarting, clears live proprietary claims, systemd restarts after 2 seconds, fresh snapshot restores state | I, V |
| HLP-02 | Crash helper three times inside 60 seconds | Restart limit stops loop; exact failed state; shell remains responsive | I, V |
| HLP-03 | Press Restart service after HLP-02 | One argv-form reset/start attempt; no shell interpolation or privilege prompt | I, V |
| HLP-04 | One feature decoder throws/returns malformed data | Affected feature becomes unavailable; process and other features continue | U, I |
| HLP-05 | Helper emits three malformed IPC frames in 60 seconds | QML closes bad connection and enters restart/failure path without parsing unsafe content | I |
| HLP-06 | BlueZ owner vanishes during connected/full | New generation, cleared live state and pending operation, exact service-unavailable copy | I, V |
| HLP-07 | BlueZ owner returns with reused-looking object paths | Full re-enumeration; old generations ignored; correct current selection reconstructed | I |
| LIFE-01 | Save a QML file/hot-reload plugin in development | Popup closes, singleton QML reconnects, external helper survives, one bar instance per monitor returns, no command replay | V |
| LIFE-02 | Run full Omarchy shell restart | Helper remains session-scoped, shell gets one fresh snapshot, no duplicate helper/session | V |
| LIFE-03 | Theme changes while panel open | All colors, fonts, spacing, borders update live; no hardcoded visual remains | Q, V |
| LIFE-04 | Text size changes from 9 to 20 px while panel open | Content reflows and remains operable; no restart or clipped action | Q, V |
| LIFE-05 | Update plugin only to compatible next minor | Brief reconnect; old helper exposes capability intersection; no write outside intersection | I, V |
| LIFE-06 | Update helper only to compatible next minor | systemd restarts helper; old plugin accepts fresh compatible snapshot; pending work not replayed | I, V |
| LIFE-07 | Create API major mismatch in either update order | Exact Update required state and zero vendor commands | I, V |
| LIFE-08 | Plugin Git update fails manifest validation | Omarchy rolls checkout back; previous widget remains usable after rescan | V |
| LIFE-09 | Config migration fails | Preserve original backup, enter setup safely, no selected-device or telemetry cross-contamination | U, V |
| LIFE-10 | Complete documented purge/remove flow | No plugin layout entry, process, socket/unit activation, or plugin-owned config remains; unrelated Omarchy config untouched | V |
| LIFE-11 | Logout with helper active | User helper and socket stop; no linger/process remains; next login starts only on plugin client demand | V |

### 20.7 Responsive, keyboard, and accessibility

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| UI-01 | Every stock theme in supported Omarchy release | Required contrast passes for normal, muted, warning, urgent, hover, selected, focus, and disabled states | Q, M |
| UI-02 | Top and bottom bars | Correct horizontal compact layout and inward popup placement | Q, V |
| UI-03 | Left and right bars | Icon-only bar, correctly rotated edge indicator, inward popup, no rotated text | Q, V |
| UI-04 | Two monitors at different scales; open on each | Popup uses invoking screen scale/work area and only one active popup; shared state remains identical | Q, V |
| UI-05 | Hot-unplug monitor containing open popup | Popup closes cleanly; remaining monitor widget and helper continue | V |
| UI-06 | 320 x 256 DIP work area | One-axis vertical scroll only; all labels/actions reachable; no overlap/clipping | Q |
| UI-07 | Text 20 px and scale 2 | Noise controls stack; complete labels remain; no horizontal scroll | Q, V |
| UI-08 | Scale 1, 1.25, 1.5, 2 | Crisp glyph/vector, integer-aligned borders, correct hit regions and anchoring | Q, M |
| A11Y-01 | Inspect AT-SPI tree with Accerciser | One named trigger button; ordered status/static text; radio roles/states; decorative nodes ignored; no duplicate labels | Q, M |
| A11Y-02 | Orca; invoke Accessible press action | Panel opens and same action occurs as pointer click | Q, M |
| A11Y-03 | Keyboard-only standard right-section summon | First movement reveals cursor without mutation; arrows/hjkl navigate; Enter/Space acts; Escape closes | Q, V, M |
| A11Y-04 | Tab/Shift+Tab with panel open | Native neighboring-panel switching works and never traps focus | Q, V |
| A11Y-05 | Command success/failure while panel open | Orca receives one polite announcement and visible text remains; routine polling is silent | Q, M |
| A11Y-06 | Measure interactive geometry | Every control and bar trigger is at least 24 x 24 DIPs | Q, M |
| A11Y-07 | Measure text/non-text/focus contrast | Text at least 4.5:1; meaningful non-text and 2-DIP focus treatment at least 3:1 | Q, M |
| A11Y-08 | Disable or remove plugin-specific animations | All status and operation meaning remains; no flashing/pulsing/rotation exists | Q, M |
| A11Y-09 | Use color-blind simulation and monochrome capture | Setup, disconnected, pending, partial, warning, critical, limited, and error remain distinguishable by text/shape | Q, M |

### 20.8 Privacy and security

| ID | Precondition and stimulus | Required result | Layer |
|---|---|---|---|
| SEC-01 | Monitor network namespace and sockets during install-free runtime | Only same-UID Unix IPC, D-Bus, and confirmed Bluetooth transport; no IP socket/DNS | I, V, M |
| SEC-02 | Inspect helper privileges/unit | User-owned process, no root/capabilities/linger; hardening and resource bounds active | V, M |
| SEC-03 | Inject names with markup, bidi controls, newlines, shell metacharacters, 10k characters | Plain escaped bounded display; no rich-text rendering, command execution, layout denial, or log injection | U, Q, I |
| SEC-04 | Unverified exact-name spoof sends plausible protocol data | No vendor write and no persisted verified selection without allowlisted handshake | I, H |
| SEC-05 | Call helper operations directly for unselected/wrong-generation device | Structured authorization error; zero Bluetooth write | I |
| SEC-06 | Send oversized, malformed, out-of-order, repeated IPC/protocol frames | Bounded rejection, no memory growth/crash, independent valid state preserved | U, I |
| SEC-07 | Inspect normal logs after full matrix | No full address, serial, username, home path, raw packet, recording data, or battery history | I, V, M |
| SEC-08 | Search process actions and exercise hostile values | All invocations use argv arrays; no `bash -lc`, unquoted interpolation, curl, or remote URL action | Q, I, M |
| SEC-09 | Unpair then run purge | Selected identity/config deleted; telemetry was never on disk; socket cleaned on service stop | V |
| SEC-10 | Verify release artifacts | Signed tag/checksums, reproducible source package, SBOM, GPL/provenance records, no Huawei asset or opaque binary | M |

### 20.9 Actual FreeBuds Pro 5 hardware release gate

Run every `HW-*` row on every fingerprint listed as Full. Use at least two Linux Bluetooth adapters from different chipsets and one Android or iOS device for dual-connect coexistence. Record exact versions and redact addresses. Dedicated test earbuds must contain no needed Smart recordings before any destructive laboratory reset.

| ID | Physical procedure | Required result/evidence |
|---|---|---|
| HW-01 | Fresh retail unit/factory pairing using open case and two-second Function-button hold | Omarchy Bluetooth pairs; plugin observes/verifies; indicator behavior matches guide; plugin itself did not scan/pair |
| HW-02 | Existing BlueZ pair before plugin/helper install | First open finds and verifies without re-pair, auto-connect, or write |
| HW-03 | Power earbuds off/out of range, then use explicit Connect after return | Correct disconnected/connecting/success states and one call; no false success |
| HW-04 | Compare aggregate/split bud values with Huawei Audio Connect within two minutes | Component identity and percentages match the protocol's reporting step; discrepancies recorded and release blocked until explained |
| HW-05 | Place both buds in open case and wait at least 15 seconds | Case value appears/updates under confirmed conditions and is timestamped |
| HW-06 | Remove buds from case and leave case unavailable | Case value becomes historical with age; no current/bar claim |
| HW-07 | Use left earbud only, then right only | Presence/absence and conservative bar metric match confirmed semantics; no missing-bud guess |
| HW-08 | Charge buds in case and charge case by cable | Only confirmed charging semantics appear; no component icon from aggregate charging |
| HW-09 | Drain across real 20% and 10% earbud thresholds | Warning/critical boundary and accessible label are correct; no notification/sound |
| HW-10 | Set all three top-level modes from Linux and verify by earbud prompt plus fresh readback | Each direct state is correct; no hidden strength or feature changes |
| HW-11 | Change each top-level mode with pinch-and-hold gesture | Widget follows valid device-originated change without sending a write; no assumed cycle order |
| HW-12 | Trigger Conversation Awareness/other automatic behavior when available | Unknown/transient mapping follows PC-06; no false confirmed parent state |
| HW-13 | Connect phone and Omarchy concurrently, play audio and place/receive a call | Status always refers to this computer; plugin neither shows/manages phone nor disrupts priority beyond normal earbud behavior |
| HW-14 | Open Huawei Audio Connect while Linux is connected and read/control device | Vendor-channel contention follows PC-10; generic connection remains; retries are bounded; no write replay |
| HW-15 | Play stereo audio for two hours and complete a microphone call while helper runs | No plugin-induced audio profile switch, dropout, latency spike, or microphone control |
| HW-16 | Suspend/resume Omarchy, close/open case, and power adapter off/on | Observed state recovers; plugin never auto-connects or leaves discovery running |
| HW-17 | Restart BlueZ and shell independently while device is connected | Helper generation/re-enumeration and shell snapshot behavior pass; no stale object or command |
| HW-18 | Kill helper during a noise command and during telemetry read | No replay or false success; service recovery/limited state exact |
| HW-19 | Run eight-hour connected idle soak and two-hour active-control soak | Resource budgets, 60-second maximum query rate, no crash/leak, and no material audio instability |
| HW-20 | Test every firmware/protocol fingerprint proposed for allowlist | All Full-tier rows pass; one failure removes that fingerprint from Full before release |
| HW-21 | Present a real/new firmware not in allowlist or a test build with its entry removed | Generic Limited mode only; zero vendor writes; exact copy |
| HW-22 | Update firmware through Huawei-supported path on dedicated unit, then reconnect | Changed fingerprint cannot retain stale Full authorization; Limited until separately validated |
| HW-23 | Unpair/forget device through Omarchy Bluetooth | Plugin clears selected identity and values immediately and returns to setup |
| HW-24 | Update plugin then helper, and helper then plugin, while hardware is connected | Compatible rolling state remains safe; major mismatch disables writes; no reconnect/write replay |
| HW-25 | Physically remove/insert USB Bluetooth adapter while paired | Exact no-adapter/recovery states; no helper crash; selected identity survives only when BlueZ reconstructs the verified pair |

## 21. Protocol Confirmation Register

These facts are release inputs, not unresolved product choices. Every row fixes the fallback that ships when confirmation is absent.

| ID | Fact requiring confirmation | Evidence required | Selected fallback before confirmation | Release effect |
|---|---|---|---|---|
| PC-01 | Exact Pro 5 identity signals across regions, renamed aliases, and revisions | Packet/device captures plus retail units; distinguish model from spoof/name-only match | Name creates candidate only; read-only handshake; zero vendor writes | Full tier blocked without identity allowlist |
| PC-02 | Vendor transport, channel, service-resolution requirement, framing, authentication, and coexistence with audio | Separate protocol report and hardware traces | Standard BlueZ only; vendor channel disabled | Detailed telemetry/control blocked |
| PC-03 | Aggregate/left/right/case battery field mapping, units, sentinel values, packet variants | Compare captures to Huawei app and controlled battery states | Valid BlueZ aggregate labeled `Earbuds`; all component fields hidden | Full battery blocked |
| PC-04 | Presence and charging semantics, especially OpenFreebuds' aggregate charging flag | Case open/closed/charging and one-bud hardware matrix | No per-component charging icon; aggregate charging only when explicitly confirmed | Component charging remains out of scope if absent |
| PC-05 | Notification support, safe read query, minimum interval, case availability, and power/audio impact | Eight-hour trace and A/B hardware soak | No proprietary polling; standard BlueZ and confirmed unsolicited events only | Bar may show limited generic data |
| PC-06 | Raw mapping for Off, Awareness, Noise cancellation, ANC strengths, transient Conversation Awareness, and unknown values | Prompt/app/readback matrix on every allowlisted fingerprint | Only exact confirmed top-level enums; unknown has no selected parent; strength/transient controls never ship | Noise controls blocked until three mappings pass |
| PC-07 | Write acknowledgement, readback command, idempotency, and safe five-second deadline | Fault-injected captures and all six directed mode transitions | No write; once enabled, never automatic retry and success requires readback | Noise controls blocked |
| PC-08 | Noise availability with one bud, buds in case, calls, recording, wear state, and service unresolved | Physical state matrix | Helper reports unavailable; controls disabled with exact copy | Full remains possible with documented unavailable states |
| PC-09 | Firmware/protocol fingerprint location and compatibility boundaries | At least one exact retail fingerprint; update test | Unknown fingerprint Limited; clear previous Full authorization | Each Full fingerprint individually gated |
| PC-10 | Concurrent ownership with Huawei Audio Connect, dual-device hosts, and reconnect behavior | Phone/Linux contention and call/audio tests | Bounded read-channel recovery; no vendor write replay; generic BlueZ remains | Full blocked if coexistence disrupts normal audio |
| PC-11 | Device-originated state notifications after gestures/automatic features | Gesture and Conversation Awareness traces | Refresh only through confirmed safe read/event; unknown mode text otherwise | Live external-state sync can degrade without blocking generic battery |
| PC-12 | Reset/unpair/firmware update effects on protocol identity and any on-device recordings | Dedicated test unit and Huawei documentation | No reset/update operation; BlueZ unpair clears local state; fingerprint change Limited | No destructive control ever enters MVP |

The protocol implementation may use OpenFreebuds as a factual research lead because it has an explicit Pro 5 driver, RFCOMM profile, battery handler, and ANC readback. [C1] [C2] [C3] It must not treat those mappings as confirmed until the evidence above passes, and it must not copy source without satisfying license/provenance policy.

## 22. Platform Confirmation Register

The separately produced platform report must validate these integration facts before implementation merge. Product behavior does not change if a check fails; the merge/release is blocked.

| ID | Required platform confirmation | Fixed outcome if absent |
|---|---|---|
| PF-01 | Packaged Omarchy Quickshell can maintain the owner-only Unix socket client and expose validated snapshots to the plugin singleton | Block implementation; do not replace it with detached QML process or HTTP |
| PF-02 | `KeyboardPanel`, accessibility APIs, and Qt 6.8 announcement behavior work together on current layer-shell build | Block accessibility claim/release until actual Orca path passes |
| PF-03 | `freebuds.pro5` combined service/bar loading and `serviceFor()` behave correctly for third-party plugin on all monitors | Block merge; do not duplicate service per widget |
| PF-04 | Native `omarchy.bluetooth` target can be opened/switched when present and its absence can be detected | Keep local-help fallback; never add a second pairing UI |
| PF-05 | systemd user socket/service hardening permits required D-Bus/Bluetooth transport and stops at logout without linger | Block helper release; never weaken to root or broad IP networking |
| PF-06 | Helper Arch/AUR package and Git plugin can share source version/provenance while updating independently | Block stable release; never add QML install hooks or opaque downloaded binary |

## 23. Definition Of Done

`0.1.0` is releasable only when all statements are true:

- Every MVP item M-01 through M-11 is implemented and every non-goal remains absent.
- All acceptance rows pass on the declared Omarchy version; all `HW-*` rows pass on every Full fingerprint.
- PC-01 through PC-09 and PC-10 coexistence are confirmed for at least one Full fingerprint. Unconfirmed optional notifications/transients retain their specified fallback.
- PF-01 through PF-06 pass.
- No display contains an unqualified stale/aggregate/component claim and no ambiguous command result is presented as success.
- Plugin validation, add-disabled-review-enable, documented placement, update rollback, rolling helper/plugin update, purge, and removal pass in a clean VM.
- Orca/Accerciser, contrast, hit target, text-size, scale, all-edge, constrained-height, and multi-monitor tests pass.
- Runtime network audit is empty; normal logs and diagnostics are redacted; helper is unprivileged and hardened.
- Signed source, AUR recipe, SBOM, support manifest, provenance ledger, privacy/security docs, and physical test evidence are published together.
- The default branch contains exactly the release-ready code that `omarchy plugin update` will fetch.

No product decision is deferred. If a protocol fact is not confirmed, the corresponding conservative fallback above is the shipped behavior.

## 24. Primary Sources

All web sources were accessed 2026-08-18. Huawei support pages without visible update dates are identified as live, mutable pages. Source-code links are commit- or version-pinned.

### 24.1 Huawei-owned sources

- **H1.** [HUAWEI FreeBuds Pro 5 product page][H1], global product behavior and features.
- **H2.** [HUAWEI FreeBuds Pro 5 Specifications][H2], gestures, noise features, codecs, and battery-life claims.
- **H3.** [HUAWEI FreeBuds Pro 5 Quick Start Guide][H3], support catalog release 2026-02-26; pairing, reset, gestures, and firmware behavior.
- **H4.** [Viewing the battery level of my HUAWEI earbuds][H4], Pro 5 popup/app support, combined bud display, and charging-case freshness caveat; plus [Pro 5 indicator thresholds][H4b].
- **H5.** [Voice prompts on HUAWEI earbuds][H5], Pro 5 `Noise cancellation`, `Awareness`, and `Off` prompts.
- **H6.** [Connection center of HUAWEI earbuds][H6] and [Multi-device connection][H6b], Pro 5 two-device connection and retained pairings.
- **H7.** [HUAWEI Audio Connect][H7] and [official app function guide][H7b], supported mobile platforms and management feature scope.
- **H8.** [How to reset HUAWEI earbuds][H8] and [voice-prompt recording section][H5], Smart recording and reset data-loss warning.
- **H9.** [Find Device model support][H9], Pro 5 location/ringtone feature and Huawei ecosystem requirements.
- **H10.** [Huawei Audio Connect privacy statement][H10], app-side device identifiers and local/server processing boundaries; last updated 2025-07-30.
- **H11.** [Displayed battery level is not reliable][H11], open-case 15-second refresh procedure and case update condition.
- **H12.** [Connecting HUAWEI Bluetooth earbuds to a phone, tablet, or PC][H12], ordinary Bluetooth pairing and documented Windows/macOS paths.

### 24.2 Omarchy-owned sources

- **O1.** [Omarchy v4.0.0 release][O1], released 2026-08-14, and inspected `quattro` commit `f32ebbdb730c4e8fe11e4046cef4267e466264ea`.
- **O2.** [Shell architecture][O2] and [shell host README][O2b], one long-running process and plugin kinds.
- **O3.** [Third-party add/install implementation][O3], [manual security/install behavior][O3b], and [remove implementation][O3c].
- **O4.** [Plugin validator][O4] and [registry validation][O4b], schema, ids, paths, and reserved namespace.
- **O5.** [Plugin enable placement][O5] and [default anchors][O5b].
- **O6.** [Plugin update implementation][O6], fast-forward, diff, validation, and rollback.
- **O7.** [BarWidget API][O7], [WidgetButton API][O7b], and [bar process execution][O7c].
- **O8.** [Panel API][O8], integrated bar/popup lifecycle.
- **O9.** [KeyboardPanel API and focus][O9], [screen fit/placement][O9b], and [PanelKeyCatcher keyboard contract][O9c].
- **O10.** [Style spacing/font/bar tokens][O10] and [official theming guidance][O10b].
- **O11.** [Color and popup surface tokens][O11].
- **O12.** [Built-in Bluetooth panel state/actions][O12] and [native panel/button section][O12b].
- **O13.** [Built-in Bluetooth primitive battery snapshot][O13] and [single percentage rendering][O13b].
- **O14.** [Built-in Bluetooth discovery lifecycle][O14].
- **O15.** [Media combined service/bar manifest][O15] and [singleton service lookup][O15b].
- **O16.** [Third-party plugin hot reload][O16] and [component recreation][O16b].
- **O17.** [Official unsandboxed-plugin warning][O17] and the matching [current shell source tree][O17b] used for the accessibility source audit.

### 24.3 Platform owners

- **P1.** [D-Bus ObjectManager and owner-change specification][P1].
- **P2.** [BlueZ 5.85 Device1 API][P2].
- **P3.** [BlueZ 5.85 Battery1 API][P3].
- **P4.** [Quickshell Bluetooth initialization][P4] and [object-manager initialization][P4b], pinned source.
- **P5.** [Quickshell 0.3 Process lifecycle][P5].
- **P6.** [Qt D-Bus interface timeout][P6].
- **P7.** [systemd v257 service restart documentation][P7].
- **P8.** [systemd v257 unit rate-limit documentation][P8].

### 24.4 Comparable project source

- **C1.** [OpenFreebuds Pro 5 model mapping][C1] and [Pro 5 driver profile][C1b].
- **C2.** [OpenFreebuds battery handler][C2].
- **C3.** [OpenFreebuds ANC handler and readback][C3].
- **C4.** [OpenFreebuds independent handler initialization/retries][C4].
- **C5.** [OpenFreebuds manager states][C5] and [manager startup recovery][C5b].
- **C6.** [OpenFreebuds conditional tray menu][C6].
- **C7.** [NothingLinux optional battery model][C7] and [unknown rendering][C7b].
- **C8.** [NothingLinux confirmed/pending UI][C8] and [write readback verification][C8b].
- **C9.** [KDE BlueDevil pending applet state][C9] and [device-row connect state][C9b].
- **C10.** [GNOME Shell Bluetooth device busy state][C10] and [30-second transition timeout][C10b].
- **C11.** [HeadsetControl structured success/partial/failure and optional battery][C11].
- **C12.** [OpenFreebuds remote bind/auth code][C12] and [web action routes][C12b].
- **C13.** [Gadgetbridge local/no-vendor-account privacy model][C13].
- **C14.** License evidence: [OpenFreebuds GPLv3][C14], [NothingLinux GPL-3.0-or-later][C14b], [HeadsetControl GPLv3][C14c], [Waybar MIT][C14d], [KDE BlueDevil LGPL header][C14e], [GNOME Shell GPLv2][C14f], [Quickshell LGPLv3][C14g], and [Gadgetbridge AGPLv3][C14h].

### 24.5 Accessibility owners

- **A1.** [WCAG 2.2 1.4.3 Contrast (Minimum)][A1].
- **A2.** [WCAG 2.2 1.4.11 Non-text Contrast][A2] and [1.4.1 Use of Color][A2b].
- **A3.** [WCAG 2.2 2.5.8 Target Size (Minimum)][A3].
- **A4.** [WCAG 2.2 2.1.1 Keyboard][A4] and [2.4.7 Focus Visible][A4b].
- **A5.** [WCAG 2.2 1.4.4 Resize Text][A5] and [1.4.10 Reflow][A5b].
- **A6.** [Qt 6 Accessible QML type][A6], including roles, names, descriptions, actions, and `announce()` since Qt 6.8.
- **A7.** [Qt 6 High DPI guidance][A7].
- **A8.** [GNOME HIG Popovers][A8], small/low-complexity content, attached trigger, no routine Close button, and Escape dismissal.

[H1]: https://consumer.huawei.com/en/headphones/freebuds-pro-5/
[H2]: https://consumer.huawei.com/en/headphones/freebuds-pro-5/specs/
[H3]: https://consumer.huawei.com/en/support/content/en-us16085356/
[H4]: https://consumer.huawei.com/en/support/content/en-us00759662/
[H4b]: https://consumer.huawei.com/en/support/content/en-us15800819/
[H5]: https://consumer.huawei.com/en/support/content/en-us15761563/
[H6]: https://consumer.huawei.com/en/support/content/en-us15815446/
[H6b]: https://consumer.huawei.com/en/support/content/en-us15907440/
[H7]: https://consumer.huawei.com/en/mobileservices/audio-connect/
[H7b]: https://consumer.huawei.com/en/support/content/en-us16037781/
[H8]: https://consumer.huawei.com/en/support/content/en-us15868473/
[H9]: https://consumer.huawei.com/en/support/content/en-us15765532/
[H10]: https://privacy.consumer.huawei.com/legal/audio-connect/privacy-statement.htm?code=DE&language=en-US
[H11]: https://consumer.huawei.com/en/support/content/en-us00735158/
[H12]: https://consumer.huawei.com/en/support/content/en-us15868501/

[O1]: https://github.com/basecamp/omarchy/releases/tag/v4.0.0
[O2]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/docs/omarchy-shell.md#L3-L47
[O2b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/README.md#L3-L14
[O3]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/bin/omarchy-plugin-add#L89-L168
[O3b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/manual/32-shell-plugins.md#L32-L42
[O3c]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/bin/omarchy-plugin-remove#L71-L123
[O4]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/bin/omarchy-plugin-validate#L38-L116
[O4b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/services/PluginRegistry.qml#L36-L90
[O5]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/bin/omarchy-plugin-enable#L30-L85
[O5b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/services/PluginRegistry.qml#L225-L250
[O6]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/bin/omarchy-plugin-update#L39-L132
[O7]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Ui/BarWidget.qml#L4-L44
[O7b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Ui/WidgetButton.qml#L7-L117
[O7c]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/bar/Bar.qml#L611-L615
[O8]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Ui/Panel.qml#L5-L57
[O9]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Ui/KeyboardPanel.qml#L6-L63
[O9b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Ui/KeyboardPanel.qml#L151-L259
[O9c]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Ui/PanelKeyCatcher.qml#L23-L84
[O10]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Commons/Style.qml#L201-L348
[O10b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/docs/omarchy-shell.md#L268-L315
[O11]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/Commons/Color.qml#L7-L87
[O12]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/panels/bluetooth/Panel.qml#L1-L169
[O12b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/panels/bluetooth/Panel.qml#L627-L686
[O13]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/panels/bluetooth/Model.js#L83-L100
[O13b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/panels/bluetooth/Panel.qml#L909-L920
[O14]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/panels/bluetooth/Panel.qml#L500-L577
[O15]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/plugins/services/media/manifest.json#L1-L23
[O15b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/shell.qml#L273-L320
[O16]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/services/PluginRegistry.qml#L636-L660
[O16b]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell/shell.qml#L739-L778
[O17]: https://github.com/basecamp/omarchy/blob/f32ebbdb730c4e8fe11e4046cef4267e466264ea/docs/omarchy-shell.md#L84-L89
[O17b]: https://github.com/basecamp/omarchy/tree/f32ebbdb730c4e8fe11e4046cef4267e466264ea/shell

[P1]: https://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces-objectmanager
[P2]: https://github.com/bluez/bluez/blob/5.85/doc/org.bluez.Device.rst
[P3]: https://github.com/bluez/bluez/blob/5.85/doc/org.bluez.Battery.rst
[P4]: https://github.com/quickshell-mirror/quickshell/blob/783c953987dc56ff0601abe6845ed96f1d00495a/src/bluetooth/bluez.cpp
[P4b]: https://github.com/quickshell-mirror/quickshell/blob/783c953987dc56ff0601abe6845ed96f1d00495a/src/dbus/objectmanager.cpp
[P5]: https://quickshell.org/docs/v0.3.0/types/Quickshell.Io/Process/
[P6]: https://doc.qt.io/qt-6/qdbusabstractinterface.html#timeout-prop
[P7]: https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml
[P8]: https://github.com/systemd/systemd/blob/v257/man/systemd.unit.xml

[C1]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/constants.py#L4-L15
[C1b]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/driver/per_model/buds_pro_5.py#L5-L29
[C2]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/handler/battery.py#L19-L34
[C3]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/handler/anc.py#L35-L108
[C4]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/driver/generic.py#L39-L54
[C5]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/manager/generic.py#L6-L13
[C5b]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/manager/main.py#L140-L174
[C6]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds_qt/tray/menu.py#L89-L166
[C7]: https://github.com/Dospacite/NothingLinux/blob/60bb7e348d090e5a394e35d3617043a3ee1facc7/crates/protocol/src/types.rs#L94-L126
[C7b]: https://github.com/Dospacite/NothingLinux/blob/60bb7e348d090e5a394e35d3617043a3ee1facc7/crates/app/src/ui/components.rs#L103-L121
[C8]: https://github.com/Dospacite/NothingLinux/blob/60bb7e348d090e5a394e35d3617043a3ee1facc7/crates/app/src/ui.rs#L80-L132
[C8b]: https://github.com/Dospacite/NothingLinux/blob/60bb7e348d090e5a394e35d3617043a3ee1facc7/crates/core/src/session/runner.rs#L149-L174
[C9]: https://invent.kde.org/plasma/bluedevil/-/blob/51bbdc4886fdd98fbb21b0e3df9a795afa142f09/src/applet/qml/main.qml#L31-40
[C9b]: https://invent.kde.org/plasma/bluedevil/-/blob/51bbdc4886fdd98fbb21b0e3df9a795afa142f09/src/applet/qml/DeviceItem.qml#L32-44
[C10]: https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/37937dd1d33ca2bbe11557f305605c2c88dda90b/js/ui/status/bluetooth.js#L200-261
[C10b]: https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/37937dd1d33ca2bbe11557f305605c2c88dda90b/js/ui/status/bluetooth.js#L27-28
[C11]: https://github.com/Sapd/HeadsetControl/blob/9ab503180df2b172812fcc8ae26818af5f6525eb/docs/LIBRARY_USAGE.md#L25-L65
[C12]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/utils/stupid_rpc.py#L91-L128
[C12b]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/webserver.py#L17-L46
[C13]: https://github.com/Freeyourgadget/Gadgetbridge/blob/a0948ee1cbc2a870f91d313f8e37df5f524465f7/README.md#L7-L14
[C14]: https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/LICENSE#L1-L6
[C14b]: https://github.com/Dospacite/NothingLinux/blob/60bb7e348d090e5a394e35d3617043a3ee1facc7/LICENSE#L1-L3
[C14c]: https://github.com/Sapd/HeadsetControl/blob/9ab503180df2b172812fcc8ae26818af5f6525eb/license#L1-L6
[C14d]: https://github.com/Alexays/Waybar/blob/09e69e0f48214a1128d62417612bc47e8dc9e36a/LICENSE#L1-L13
[C14e]: https://invent.kde.org/plasma/bluedevil/-/blob/51bbdc4886fdd98fbb21b0e3df9a795afa142f09/src/applet/qml/main.qml#L1-7
[C14f]: https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/37937dd1d33ca2bbe11557f305605c2c88dda90b/COPYING#L1-7
[C14g]: https://github.com/quickshell-mirror/quickshell/blob/532a0606cafb05851a203e65be22c9a057447ee2/README.md#L14-L25
[C14h]: https://github.com/Freeyourgadget/Gadgetbridge/blob/a0948ee1cbc2a870f91d313f8e37df5f524465f7/README.md#L22-L26

[A1]: https://www.w3.org/TR/WCAG22/#contrast-minimum
[A2]: https://www.w3.org/TR/WCAG22/#non-text-contrast
[A2b]: https://www.w3.org/TR/WCAG22/#use-of-color
[A3]: https://www.w3.org/TR/WCAG22/#target-size-minimum
[A4]: https://www.w3.org/TR/WCAG22/#keyboard
[A4b]: https://www.w3.org/TR/WCAG22/#focus-visible
[A5]: https://www.w3.org/TR/WCAG22/#resize-text
[A5b]: https://www.w3.org/TR/WCAG22/#reflow
[A6]: https://doc.qt.io/qt-6/qml-qtquick-accessible.html
[A7]: https://doc.qt.io/qt-6/highdpi.html
[A8]: https://developer.gnome.org/hig/patterns/containers/popovers.html
