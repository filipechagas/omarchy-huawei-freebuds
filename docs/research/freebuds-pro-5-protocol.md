# HUAWEI FreeBuds Pro 5 on Linux: protocol and feasibility research

> [!WARNING]
> **Evidence only; superseded.** This report preserves research inputs and is
> not implementation, product, platform, hardware-status, or release authority.
> Follow [`../architecture.md`](../architecture.md),
> [`../implementation-plan.md`](../implementation-plan.md), and
> [`../hardware-validation.md`](../hardware-validation.md). Conflicting
> recommendations below, including unverified diagnostic values, reconnect
> refreshes, queued work, retry, and broader protocol behavior, must not be
> implemented.

Status: research complete for a no-active-hardware-interaction pass
Research date: 2026-08-18
Target product: HUAWEI FreeBuds Pro 5, public model T0023
Primary question: what can a Linux application support safely with public evidence today?

## Executive conclusion

FreeBuds Pro 5 support on Linux separates into four support areas:

| Layer | Feasibility | Confidence | Recommended scope |
|---|---|---:|---|
| Stereo music and media controls | Feasible now through BlueZ, PipeWire, and WirePlumber | High; strengthened by cached profiles and historical local A2DP/AVRCP evidence | Use the standard Linux Bluetooth audio stack without a custom audio transport |
| HFP call audio | Standards-feasible and discovered locally | Medium; local HFP attempts include refused/not-connected results | Advertise as available by profile, not locally reliability-validated |
| Left, right, and case battery readings | Feasible as an experimental private-protocol feature | Medium-high for packet semantics; medium-low for discovery and identity | Read only over a tightly gated RFCOMM session |
| Off, ANC, and transparency control | Feasible as an explicit experimental feature | Medium-high for the three packets; medium-low for discovery, identity, and firmware coverage | Allow only the three retained Pro 5 writes, then verify with a readback |

The public evidence does **not** justify a broad "fully supported" claim. Huawei does not publish the private control protocol. The strongest public device-specific evidence is a set of retained FreeBuds Pro 5 request, response, and write frames in HuaweiPods tests. Those fixtures cover a battery response, three noise-control readbacks, and three noise-control writes. They do not cover every firmware, error response, notification, pairing state, or concurrent audio/control scenario.

The largest release blocker is device identification. HuaweiPods maps private DeviceInfo model ID `00016D` to FreeBuds Pro 5 and says its map contains only real-device-proven IDs, but its repository does not retain a raw Pro 5 DeviceInfo frame. The public Huawei model `T0023` and private ID `00016D` are different identifiers. A device name is not an adequate substitute because BlueZ aliases are mutable and names are spoofable.

The disconnected local target has a cached SerialPort UUID `0x1101`, alongside A2DP, AVRCP, and HFP service classes. This is useful class E evidence that BlueZ previously discovered standard SPP on the selected unit. It does not reveal the RFCOMM server channel, prove that channel 1 is correct, or attach semantics to the two unknown cached UUIDs. Historical local logs verify prior A2DP media file-descriptor readiness and AVRCP input creation, but do not record the selected codec. HFP was discovered but is not reliability-validated locally.

No live target battery source was present in the disconnected snapshot. There was no target `Battery1`, GATT child, UPower device, or BlueZ battery-provider object. Historical UPower samples are `0.000`/`unknown` and are not usable battery evidence. The MVP must hide battery until a live `Battery1` is cross-validated or a strictly gated private response succeeds.

A safe near-term result is therefore:

- Keep all audio profile and codec work in BlueZ/PipeWire/WirePlumber.
- Require a device that is already paired and bonded by the desktop environment.
- Never pair, trust, untrust, connect all profiles, disconnect, reset, or update firmware from this application.
- Respect the existing WirePlumber A2DP auto-connect policy and do not add an application reconnect loop.
- Open at most one authenticated and encrypted RFCOMM control session for the selected device.
- Start read-only. Require strict framing, CRC, identity, and Pro 5-shaped response checks before enabling writes.
- Expose only Off, ANC, and Transparency writes. Read back after every write and fail closed on disagreement.
- Treat battery values as timestamped observations, not durable state.
- Do not implement ANC sub-levels, gesture configuration, EQ, low-latency mode, wear-setting writes, multipoint management, or firmware functions from the current evidence.

This is sufficient for an opt-in experimental MVP. It is not sufficient for unattended background control or an unqualified stable-support promise.

## Scope and non-interaction statement

This pass examined:

- Huawei product, support, manual, and Bluetooth qualification material.
- Bluetooth SIG profile and assigned-number material.
- Current BlueZ, PipeWire, WirePlumber, and Linux kernel source.
- OpenFreebuds and HuaweiPods source and history at fixed commits.
- Local package, service, codec-plugin, WirePlumber configuration/state, cached BlueZ object state, UPower history, and historical journal state.

The local target inspection read only host-resident cache, state, and logs while the target was disconnected. It did **not** request a live service refresh. The full BD_ADDR is intentionally omitted throughout this report.

This pass deliberately did **not**:

- Start Bluetooth discovery or active SDP/GATT resolution.
- Open an RFCOMM, A2DP, AVRCP, HFP, GATT, or other target connection.
- Pair, bond, trust, untrust, connect, disconnect, forget, reset, or update the target.
- Request a live battery value or change a Bluetooth, PipeWire, WirePlumber, kernel, or desktop setting.
- Capture Bluetooth traffic.
- Copy temporary research artifacts into this project.

Only [Local Linux observations](#local-linux-observations) describes the selected local unit. Those observations are either a disconnected cached snapshot, historical host records, or host capability. They are not a live protocol measurement and are not generalized to all FreeBuds Pro 5 units.

## Evidence model

The report uses five evidence classes. Confidence is scoped to the claim being made; an official feature claim does not reveal private bytes, while a captured packet does not establish official support policy.

| Class | Meaning | Examples | Appropriate use |
|---|---|---|---|
| A: first-party | Huawei, Bluetooth SIG, or the owner of a standard publishes the fact | T0023, supported codecs, SPP behavior, assigned UUIDs | Product and standards facts |
| B: upstream implementation | BlueZ, PipeWire, WirePlumber, or Linux source defines actual host behavior | `Battery1`, RFCOMM security levels, available codec names | Linux architecture and security |
| C: retained Pro 5 capture | Public tests retain exact bytes explicitly labeled as captured from Pro 5 | Battery frame and three ANC state frames | Exact experimental protocol support |
| D: implementation assertion | A project claims testing or maps a value but does not retain the corresponding raw Pro 5 evidence | Channel 1, ID `00016D`, broad OpenFreebuds feature list | Provisional gating or a lead for future capture, not a settled fact |
| E: local observation | Read-only inspection of disconnected cache, historical host records, and host software | Cached UUIDs, prior A2DP/AVRCP events, installed codec modules | Local corroboration only; never upgrades an unknown packet/channel/codec meaning by itself |

Decision rules used here:

- Device-specific writes require class C evidence for the exact model and operation.
- Read-only probing may use class C request evidence, but it must be bounded and user initiated until discovery and identity are stronger.
- Class D alone does not enable a write.
- Facts inferred from FreeBuds 5, 6i, Pro 3, or Pro 4 are not promoted to Pro 5 facts.
- An absent public capture is recorded as unknown, not unsupported.
- Invalid, ambiguous, or conflicting input disables the feature instead of selecting a default interpretation.
- Cached service UUIDs prove only that BlueZ retained those service classes. They do not prove a current service resolution, RFCOMM channel, selected codec, or runtime reliability.
- Module presence proves host capability only. A peer offer and successful negotiation remain separate evidence requirements.

## First-party product facts

### Identity and radio capabilities

Huawei's global support page identifies the downloadable product as `HUAWEI FreeBuds Pro 5 Wireless Charging (T0023)`. The Bluetooth qualification listing also associates marketing name `HUAWEI FreeBuds Pro 5` with model `T0023`. Listing `303574` names Huawei Technologies Co., Ltd., declaration `R075602`, design `Q367365`/QDID `367365`, qualification date 2025-08-25, and listing date 2025-11-30. The listing additionally references HiSilicon and Barrot designs; it does not expose the private application protocol.[^huawei-support][^bt-listing]

The Huawei-delivered multilingual Quick Start Guide identifies the earbuds as `T0023` and the charging case as `T0023C`. Its technical-specification section lists A2DP 1.3, HFP 1.7, and AVRCP 1.6. The local research copy has SHA-256 `a7743fc64189501da2d62bd8da6cd431902a2bdd2bbd871f300472408046e4fc` and was obtained from the T0023 download entry on Huawei's support page.[^huawei-support]

Huawei's global specifications state Bluetooth 6 compatibility, dual-device Bluetooth connection, 60 mAh minimum per earbud, and a 537 mAh minimum charging-case battery. Huawei's China specifications additionally list NearLink E2.0 and audio codecs SBC, AAC, L2HC, and LDAC, while explicitly saying LHDC and aptX are not supported.[^huawei-global-spec][^huawei-cn-spec]

Important boundaries follow from those statements:

- NearLink is listed separately from Bluetooth. A Bluetooth 6 controller or BlueZ version does not imply NearLink support.
- A product codec claim does not imply that a stock Linux encoder exists for it.
- A2DP/HFP/AVRCP versions describe standard audio/control profiles, not Huawei's ANC and component-battery protocol.

### User-visible behavior relevant to Linux

Huawei documents the following product behavior:

- Noise control includes ANC and Awareness/Transparency modes.[^huawei-global-spec]
- Smart wear detection can pause/resume playback and alter call routing; FreeBuds Pro 5 is listed as compatible with non-Huawei phones and tablets for that feature.[^huawei-wear]
- The product supports dual-device Bluetooth connection. Huawei's account-based multi-device feature retains up to ten pairing records but connects only two devices at a time, with one active audio source and calls taking priority.[^huawei-multidevice]
- In an open, interference-free area Huawei states a range of up to 10 m. FreeBuds Pro 5 automatically reconnects to the last device when it returns within range within three minutes.[^huawei-range]
- Huawei's pairing instructions put FreeBuds/FreeClip products into pairing mode by opening the case and holding the Function button for at least two seconds until the light flashes white.[^huawei-pairing]
- Huawei's battery support material says its app can show earbud and case battery. It also warns that case battery for FreeBuds/FreeClip products updates after the earbuds are placed in the case.[^huawei-battery]

These are user-facing capabilities, not evidence of Linux D-Bus objects or private command bytes.

## Standards and Linux primitives

### Standard audio profiles

The Bluetooth SIG describes A2DP as the profile for high-quality audio distribution.[^a2dp] The FreeBuds manual's A2DP 1.3, HFP 1.7, and AVRCP 1.6 declarations align with normal Linux roles:

| Product function | Standard path on Linux | Owner |
|---|---|---|
| Stereo music playback | A2DP, with the computer acting as source and earbuds as sink | BlueZ + PipeWire + WirePlumber |
| Call audio and headset signaling | HFP, normally computer as Audio Gateway and earbuds as Hands-Free unit | BlueZ + PipeWire |
| Play/pause, track, and volume controls | AVRCP plus PipeWire session integration | BlueZ + PipeWire/WirePlumber |
| Huawei settings and component battery | No public standard mapping established | Experimental private RFCOMM client |

PipeWire's current Bluetooth property reference lists `a2dp_sink`, `a2dp_source`, `hfp_hf`, and `hfp_ag` roles and lists enabled codec names including SBC, SBC-XQ, AAC, LDAC, aptX variants, LC3, and Opus variants.[^pw-props] WirePlumber exposes those monitor properties and profile auto-connect rules; it documents that all available codecs are enabled by default unless configured otherwise.[^wp-bluetooth]

No `L2HC` or `NearLink` implementation was found in the fixed BlueZ, PipeWire, or WirePlumber trees. PipeWire does contain optional **LHDC** build support, but LHDC is a different codec and Huawei explicitly lists it as unsupported by this product.[^pw-codec-build] The MVP must not relabel LDAC, LHDC, LC3, or another codec as L2HC.

Recommended audio policy:

- Do not implement or proxy A2DP/HFP in the application.
- Do not force a codec merely because Huawei lists it.
- Let BlueZ/PipeWire negotiate the intersection of device-advertised and host-installed codecs.
- Prefer the desktop's existing policy. If higher-level policy offers a codec choice, expose only codecs actually available for the current BlueZ card/profile.
- Treat SBC as the deterministic compatibility fallback; use AAC or LDAC only when negotiation makes it available.
- Exclude L2HC and NearLink from the Linux MVP.

### SPP and RFCOMM

The Bluetooth SIG Serial Port Profile 1.2 defines emulated serial connections between peers over RFCOMM. Its connection procedure performs SDP discovery of an RFCOMM server channel, optionally requests authentication and encryption, opens the RFCOMM session, and then opens the selected data-link channel. SPP permits security features to be optional for a particular service, while requiring devices to support authentication and encryption when requested.[^spp]

Bluetooth SIG assigned numbers define:

| Item | Assigned value |
|---|---:|
| Serial Port service class | `0x1101`, full UUID `00001101-0000-1000-8000-00805F9B34FB` |
| Battery Service | `0x180F` |
| Battery Level characteristic | `0x2A19` |

The values are present in the SIG's official YAML repository at fixed commit `3cfa46a13ac1aac7440fd3df99f6b96fbf073354`.[^assigned-page][^assigned-spp][^assigned-bas][^assigned-level]

RFCOMM itself uses L2CAP PSM `0x0003`; the application selects an RFCOMM **server channel**, not a separate vendor PSM. Linux defines `L2CAP_PSM_RFCOMM` as `0x0003` and a `sockaddr_rc` containing a Bluetooth address plus an 8-bit RFCOMM channel.[^linux-l2cap][^linux-rfcomm-h]

OpenFreebuds opens an `AF_BLUETOOTH`, `SOCK_STREAM`, `BTPROTO_RFCOMM` socket and connects it to `(address, channel)`. Its Pro 5 driver sets that channel to `1`.[^ofb-transport][^ofb-pro5] The corresponding commit says the driver was tested, but it does not retain the Pro 5 SDP record or a channel-discovery capture.[^ofb-pro5-commit] Consequently:

- Channel 1 is a useful class D implementation assertion.
- The actual Pro 5 SDP UUID/channel tuple remains unverified in public raw evidence.
- A Linux client must not scan channels 1 through 8 or try unrelated SDP UUIDs.
- A future hardware pass should retain the actual SDP service record.
- Until then, channel 1 may be used only behind explicit experimental support and the identity/readback gates described below.

The disconnected local target's cached `Device1.UUIDs` includes the standard SerialPort UUID `00001101-0000-1000-8000-00805f9b34fb`. This strengthens the conclusion that this unit previously advertised an SPP-class service. Because `ServicesResolved=false` in the snapshot and no raw SDP record was retained, it does not establish the current service state or server channel. It also does not promote OpenFreebuds' channel-1 assertion from class D to captured fact.

### BlueZ device and battery APIs

BlueZ `org.bluez.Device1` exposes cached remote UUIDs and read-only `Paired`, `Bonded`, `Connected`, and `ServicesResolved` state. It defines `Paired` as completion of the information exchange needed for an encrypted connection and `Bonded` as persistence of that information. `Trusted` is a separate read/write policy property. `Connect()` attempts all auto-connectable profiles, while `ConnectProfile(uuid)` targets one remote service UUID.[^bluez-device]

This distinction matters. The application should inspect `Device1` but should not call `Pair()`, write `Trusted`, or call broad `Connect()`/`Disconnect()`. Pairing belongs to the desktop's normal UI and agent.

The Bluetooth SIG Battery Service exposes level and related information for a battery within a device, but its existence on this model has not been established.[^bas] BlueZ `org.bluez.Battery1` exposes one read-only byte `Percentage` and an optional informational `Source`.[^bluez-battery] BlueZ's built-in GATT battery plugin looks specifically for Battery Service UUID `0x180F` and registers its value with source `GATT Battery Service`.[^bluez-battery-plugin] PipeWire can also derive one headset battery percentage from HFP indicators such as `AT+BIEV`, `AT+XEVENT=BATTERY`, and `AT+IPHONEACCEV`, then publish it through BlueZ's experimental Battery Provider API.[^pw-hfp-battery][^pw-battery-provider]

BlueZ exposes `BatteryProviderManager1` on the local adapter, which proves only that the host can accept a provider. In the disconnected target snapshot there was no target `Battery1`, target battery-provider object, GATT child, current UPower device, cached Battery Service UUID, `ManufacturerData`, or `ServiceData`. `ServicesResolved=false` means this absence cannot establish what appears during a live connection. Historical UPower files contain only connection-timestamped `0.000`/`unknown` samples; those samples must not be displayed as zero-percent battery.

Therefore, the presence of `Battery1` does not establish:

- That Pro 5 exposes the standard GATT Battery Service.
- That the value came from GATT rather than HFP or another provider.
- That the value represents left, right, case, minimum, maximum, or an aggregate.
- That three component values are available through standard BlueZ APIs.

Do not display a generic battery merely because stale UPower history exists. A future live `Battery1` may be used only after its target association, freshness, range, and source/meaning are cross-validated. Use the private packet only for strictly gated, explicitly labeled left/right/case observations.

BlueZ also exposes remote GATT characteristics through `org.bluez.GattCharacteristic1` with read, write, and notify methods.[^bluez-gatt] No public Pro 5 GATT service/characteristic capture was found, so no vendor GATT path belongs in the MVP.

## Capability matrix

`Yes` means evidence supports an implementation decision. `Experimental` means exact scope and guards are mandatory. `No` means deliberately excluded, not necessarily that the product lacks the feature.

| Capability | Product evidence | Pro 5 protocol evidence | Linux support | MVP decision |
|---|---|---|---|---|
| Pair through desktop UI | Huawei documents normal Bluetooth pairing | Not needed | BlueZ | Yes, outside this app |
| Stereo playback | A2DP 1.3; product codecs listed | Not needed | Cached Audio Sink/A2DP UUIDs, historical A2DP fd readiness, persistent `a2dp-sink` | Yes |
| Call audio | HFP 1.7 | Not needed | Hands-Free UUID cached; historical attempts sometimes refused/not connected | Discovered, but local reliability unvalidated |
| Media controls | AVRCP 1.6; controls documented | Not needed | Cached AVRCP UUIDs and historical kernel input creation | Yes |
| Private SPP transport | SPP UUID cached on the local target | No raw SDP record/channel capture | Direct RFCOMM available; channel 1 remains an implementation assertion | Experimental only |
| SBC | Huawei lists support | Not needed | Host module installed; peer negotiation not recorded | Yes, only if negotiated |
| AAC | Huawei lists support | Not needed | Host module installed; peer negotiation not recorded | Yes, only if negotiated |
| LDAC | Huawei lists support | Not needed | Host module links `libldac`; peer negotiation not recorded | Yes, only if negotiated |
| L2HC | Huawei lists support | None | No implementation found in examined stock stack | No |
| NearLink E2.0 | Huawei China page lists it separately | None | No implementation found | No |
| One host battery percentage | Huawei documents host displays | Source on Pro 5 unknown | No live target `Battery1`; UPower history is `0.000`/`unknown` | Hide until a live value is cross-validated |
| Left/right/case percentages | Huawei app documents component display | Exact Pro 5 battery frame retained | Direct RFCOMM | Experimental read-only |
| Per-component charging flags | Product has rechargeable components | Pro 5 frame has three captured bytes in TLV `03`; zero observed | Direct RFCOMM | Experimental read-only; nonzero semantics need capture coverage |
| Earbud in/out-of-case state | Product has case and wear behavior | Pro 5 tests label TLV `05`: `0` out, `1` in | Direct RFCOMM | Experimental read-only |
| Read current noise-control mode | ANC/transparency official | Three exact Pro 5 response frames retained | Direct RFCOMM | Experimental |
| Set Off/ANC/Transparency | Modes official | Three exact Pro 5 writes retained | Direct RFCOMM | Experimental, user initiated and readback verified |
| Discrete ANC strength | Advanced ANC official at a product level | No retained Pro 5 write/read mapping; HuaweiPods intentionally leaves it disabled | None standard | No |
| Voice-transparency submode | Human Voice Transparency official | No retained Pro 5 command corpus beyond generic transparency | None standard | No |
| Wear-detection setting | Feature official | OpenFreebuds claim only for private configuration | None standard established | Observe standard playback behavior only; no setting writes |
| Gesture configuration | Gestures official | OpenFreebuds claim conflicts with HuaweiPods capability gate; no Pro 5 raw corpus | None standard for configuration | No |
| EQ and sound-quality preference | Product advertises EQ/audio features | OpenFreebuds claim only; no retained Pro 5 corpus | PipeWire EQ is unrelated to device-persistent EQ | No device writes |
| Low-latency control | HuaweiPods capability assertion and OpenFreebuds claim | No retained Pro 5 frame cited | No standard setting path | No |
| Multipoint management | Dual-device behavior official | OpenFreebuds claim only for private control | BlueZ handles each host connection, not Huawei account policy | No management writes |
| Firmware update | Product firmware exists | None | Not appropriate for this project | No |

## Private Huawei frame format

### Wire representation

OpenFreebuds' serializer and parser establish the general framing, and the retained HuaweiPods fixtures confirm it for every Pro 5 frame considered here.[^ofb-frame][^ofb-crc]

| Offset | Size | Meaning |
|---:|---:|---|
| `0` | 1 | Magic `0x5A` (`Z`) |
| `1` | 2 | Big-endian declared length `L` |
| `3` | 1 | Version, observed as `0x00` |
| `4` | 1 | Service ID |
| `5` | 1 | Command ID |
| `6..` | variable | Repeated TLVs: one-byte type, one-byte value length, then value bytes |
| final 2 | 2 | Big-endian CRC-16/XMODEM |

Length semantics:

```text
total frame bytes = L + 5
L = bytes from version through the final TLV
5 excluded bytes = magic + two length bytes + two CRC bytes
```

For example, the 14-byte battery query declares `L = 9`; the 32-byte Pro 5 battery response declares `L = 27`.

CRC semantics:

- Algorithm: CRC-16/XMODEM.
- Polynomial: `0x1021`.
- Initial value: `0x0000`.
- Input: every byte from magic through the final TLV, excluding the trailing CRC.
- Output: high byte then low byte.

All ten Pro 5-relevant frames in the command corpus below were independently checked on 2026-08-18 with Python `binascii.crc_hqx(frame_without_crc, 0)`. Every declared length and CRC matched.

### Required parser behavior

RFCOMM is a byte stream. Reads may split one frame or combine several frames. No request sequence number is visible in this corpus, so request/response matching must use one outstanding transaction and the expected service/command pair.

A production parser should:

1. Accumulate bytes in a bounded buffer.
2. Search for magic `0x5A` without assuming a read begins at a frame boundary.
3. Require all three prefix bytes before decoding `L` as big-endian.
4. Reject `L < 3` because version, service, and command must fit.
5. Apply an implementation maximum before allocating or waiting. A 4096-byte maximum is a conservative application policy, not a discovered protocol limit.
6. Wait until exactly `L + 5` bytes are available.
7. Require version `0x00` for this protocol generation.
8. Verify CRC before interpreting service, command, or TLVs.
9. Parse every TLV with checked addition and a bound ending two bytes before the frame end.
10. Reject truncated known TLVs and duplicate known TLVs. Ignore well-formed unknown TLVs while retaining them in debug output.
11. Match only the expected service and command for the active transaction.
12. Continue parsing complete trailing frames; do not discard a combined RFCOMM read after the first frame.
13. Redact addresses and likely serial-number TLVs from normal logs.

Neither public project should be copied verbatim as the production parser:

- HuaweiPods' generic battery/ANC parser bounds frames and TLVs but does not validate CRC before semantic parsing; one test deliberately uses a `0000` placeholder CRC and still parses it.[^hp-parser][^hp-parser-tests]
- Its generic frame-length code assumes the observed high length byte is zero when reconstructing `L`; the identity parser has the same limitation for frames longer than 255 bytes.[^hp-parser][^hp-identity]
- OpenFreebuds implements CRC generation and optional validation, but `from_bytes()` defaults validation off and its receive path calls it without enabling validation. Its stream reader also uses `read()` rather than `readexactly()` for the declared remainder.[^ofb-frame][^ofb-generic]

Those are implementation cautions, not reasons to reject the retained byte fixtures. The independent CRC checks establish that the cited fixtures themselves are internally consistent.

## Verified command corpus

The HuaweiPods packet object says it contains only commands confirmed through real-device capture. Its tests explicitly label the three mode writes and the corresponding readbacks as FreeBuds Pro 5 captures.[^hp-packets][^hp-packet-tests][^hp-parser-tests]

### Requests and writes

| Operation | Service/command | TLV payload | Complete frame | Pro 5 provenance |
|---|---|---|---|---|
| Read battery | `01/08` | `01 00 02 00 03 00` | `5A0009000108010002000300FBB9` | Query included for Pro 5 in capture-gated tests |
| Read DeviceInfo | `01/07` | Empty requests for tags `01..0C`, `0F`, `18`, `19` | `5A00210001070100020003000400050006000700080009000A000B000C000F0018001900DFF3` | Shared modern-device query; no retained Pro 5 response |
| Read ANC state | `2B/2A` | `01 00` | `5A0005002B2A0100427E` | Test enables query for Pro 5 and retained responses exist |
| Set Off | `2B/04` | `01 02 00 00` | `5A0007002B0401020000D22D` | Test explicitly says Pro 5 verified capture |
| Set ANC | `2B/04` | `01 02 01 FF` | `5A0007002B04010201FFFFEC` | Test explicitly says Pro 5 verified capture |
| Set Transparency | `2B/04` | `01 02 02 FF` | `5A0007002B04010202FFAABF` | Test explicitly says Pro 5 verified capture |

The zero-length TLVs in read requests mean "return these fields" in the observed implementation pattern. That interpretation is strong for these exact requests but should not be generalized to untested services.

### Pro 5 noise-control responses

| State | Complete captured frame | Known TLV `01` | Additional TLV |
|---|---|---|---|
| Off | `5A000A002B2A01020000020105B843` | `00 00` = submode `0`, mode Off | `02 01 05`, semantic unknown |
| ANC | `5A000A002B2A010203010201052025` | `03 01` = submode `3`, mode ANC | `02 01 05`, semantic unknown |
| Transparency | `5A000A002B2A0102020202010511A8` | `02 02` = submode `2`, mode Transparency | `02 01 05`, semantic unknown |

The response's two-byte state is `[submode, mode]`, while the basic write value is `[mode, requested submode]`. Only the second response byte should select the top-level mode: `00` Off, `01` ANC, `02` Transparency. The first byte may be displayed in diagnostics but must not enable Pro 5 sub-level controls from these three examples alone.[^hp-parser]

The shorter 12-byte frames such as `5A0007002B2A010203015043` are **not** Pro 5 fixtures. HuaweiPods labels them as FreeBuds 5/Pro 3/6i captures. Using them as Pro 5 provenance would erase an important model boundary.[^hp-parser-tests]

### Pro 5 battery response

Captured frame:

```text
5A001B0001080101640203646455030300000004020A140502000106010A4D9B
```

Decomposition:

| Bytes | Interpretation | Confidence |
|---|---|---|
| `5A 001B 00 01 08` | Header; `L=27`, service `01`, command `08` | Frame format verified |
| `01 01 64` | Tag `01`, aggregate/global value 100 | Cross-project parser agreement; captured value |
| `02 03 64 64 55` | Tag `02`, left 100, right 100, case 85 | Pro 5 test asserts all three values |
| `03 03 00 00 00` | Tag `03`, three charging-state bytes, all zero in this capture | Field association supported; nonzero Pro 5 values not retained here |
| `04 02 0A 14` | Unknown tag `04` | Do not infer |
| `05 02 00 01` | Tag `05`: left out of case, right stored in case | Pro 5 tests assert `0=out`, `1=in` for left/right |
| `06 01 0A` | Unknown tag `06` | Do not infer |
| `4D 9B` | CRC-16/XMODEM | Independently verified |

HuaweiPods has a second retained Pro 5 frame with tag `05 = 01 01`, which its test interprets as both earbuds stored in the case.[^hp-parser-tests] Its implementation restricts this tag-05 interpretation to the Pro 5 route because the same tag has different or transient behavior on another model.[^hp-capabilities][^hp-parser] That model-specific restraint should be preserved.

Battery rules for the MVP:

- Accept percentages only in `0..100`.
- Require tag `02` length exactly three for a TWS component update.
- Associate tag `03` positions with left, right, case only when it has three bytes.
- Interpret tag `05` only after the Pro 5 gate and only when it has exactly two values from `{0,1}`.
- Keep a zero-percent earbud available when tag `05` explicitly says it is out of the case; zero is then a real level, not an absence sentinel.
- Do not assign names to tags `04` and `06`.
- Do not infer case availability from its percentage. Store its observation timestamp.
- Do not treat this single capture as proof of notification command `01/27`; support request/response command `01/08` only.

## Device identity and capability gating

### What is known

HuaweiPods' strict DeviceInfo parser expects a CRC-valid `01/07` response and cross-checks:

- Tag `02`: a two-byte model code.
- Tag `0A`: an ASCII value ending in a six-hex-digit model ID.
- Tag `0F`: an ASCII model prefix matching the prefix in tag `0A`.
- Tag `19`: a one-byte submodel/color ID.

It rejects missing, duplicate, malformed, conflicting, oversized, and bad-CRC identities.[^hp-identity] Its retained fixtures cover IDs `000141`, `00014F`, `000153`, and `000163`, but not `00016D`.[^hp-identity-tests]

The route policy maps `00016D` to `HUAWEI_FREEBUDS_PRO5` and comments that only model IDs proven by real DeviceInfo frames are included.[^hp-route] That is useful evidence of developer observation, but without the raw response it is class D rather than class C.

OpenFreebuds instead dispatches its Pro 5 driver by the Bluetooth name `HUAWEI FreeBuds Pro 5` and assigns channel 1.[^ofb-pro5][^ofb-driver-map] A display name alone is not a safe protocol capability gate.

### Provisional gate for an experimental MVP

Use a monotonic state machine. Never infer a later state from a timeout or default value.

| State | Entry requirements | Allowed operations |
|---|---|---|
| `Ineligible` | Not paired, not bonded, wrong device type, or user did not opt in | Standard audio observation only |
| `Selected` | User explicitly selects one already paired/bonded device | Read cached BlueZ metadata; no private write |
| `SecureTransport` | One RFCOMM channel-1 connection succeeds with explicit medium security | DeviceInfo query only |
| `IdentityProvisional` | Strict DeviceInfo parser returns `00016D`; no conflicting valid identity | Battery and ANC-state reads |
| `ReadVerified` | At least one CRC-valid response has a Pro 5-retained shape: component battery with valid tag `05`, or extended ANC response with tag `02 01 05` | Show experimental read data |
| `WriteEnabled` | User separately enables experimental controls and a fresh ANC state read succeeds | Three exact mode writes, one at a time, with readback |
| `Faulted` | Security downgrade, bad CRC threshold, malformed known TLV, identity conflict, timeout during verification, or post-write mismatch | Close transport; no more writes until explicit retry |

Additional rules:

- The BlueZ `Name` or `Alias` may help the user choose but must not advance the gate.
- Public model `T0023` must not be substituted for private ID `00016D` unless an actual protocol field carrying T0023 is captured.
- If the DeviceInfo query is unanswered but the battery query works, an opt-in **read-only battery diagnostic** may show the decoded frame with an "unverified Huawei model" warning; writes stay disabled.
- A future retained Pro 5 DeviceInfo frame should replace the provisional classification and become a regression fixture.
- A firmware version, when safely obtained from DeviceInfo, should be recorded with every future capture and shown in diagnostics. It must not be used as an unbounded string or logged if it embeds a serial number.

## Recommended Linux architecture

### Separation of responsibilities

| Module | Responsibility | Must not do |
|---|---|---|
| `BluezInventory` | Read `Device1` paired/bonded/connected/services state and optional `Battery1` | Pair, trust, connect all profiles, disconnect, or mutate aliases |
| `AudioStatus` | Observe PipeWire/WirePlumber profile and negotiated codec | Create a competing A2DP/HFP transport or force unsupported codecs |
| `ControlTransport` | Own one medium-security RFCOMM socket, bounded reads, deadlines, close/idle policy | Scan channels, fall back to insecure sockets, or open parallel sessions |
| `HuaweiFramer` | Encode exact fixtures; buffer, length-check, CRC-check, and parse TLVs | Interpret device capabilities or update UI state |
| `Pro5Gate` | Apply identity and response-shape policy | Guess from name/color or accept conflicting identities |
| `BatteryFeature` | Produce timestamped left/right/case observations | Publish unknown private semantics as facts |
| `NoiseControlFeature` | Serialize read/write/readback transactions | Support uncaptured levels or optimistic state changes |

The important seam is between byte validity and device semantics. `HuaweiFramer` should be model-agnostic and strict. `Pro5Gate` and feature decoders should accept only model-specific known fields.

### Control-session lifecycle

Recommended behavior:

1. Require `Paired=true`, `Bonded=true`, and `Connected=true` from BlueZ before opening the private channel.
2. Open one direct RFCOMM socket to channel 1 with explicit medium security.
3. Run DeviceInfo, then the requested read or control transaction through one serialized queue.
4. Keep no more than one request outstanding because no sequence field is known.
5. Match response service/command and ignore unrelated valid frames after logging only safe metadata.
6. Use bounded connect and response deadlines. The public Android implementation uses 2-3 second connect deadlines and roughly 1.2-1.5 second response windows; these are implementation evidence, not device guarantees.[^hp-controller]
7. Close after a short idle period rather than holding an indefinite background session. The exact idle value should be measured later.
8. Close immediately when BlueZ reports disconnect, suspend begins, the selected address changes, or the gate faults.
9. Do not automatically reopen during a call, profile switch, or rapid reconnect loop.
10. Use bounded exponential retry only for user-visible reads. Do not retry a write automatically because delivery may have succeeded before the response was lost.

OpenFreebuds demonstrates a normal user-space direct RFCOMM socket path, and its Flatpak manifest requests `--allow=bluetooth` plus BlueZ D-Bus access.[^ofb-transport][^ofb-flatpak] The Linux application should run as the user, not root. Packaging still needs the appropriate host and sandbox permission.

### Noise-control transaction

For each user action:

1. Obtain a fresh `2B/2A` state response.
2. If the requested top-level mode is already active, do not write.
3. Write exactly one of the three retained packets.
4. Do not update displayed state from socket-write success.
5. Query `2B/2A` once after the write.
6. Commit UI state only if the response is CRC-valid, Pro 5-shaped, and matches the requested top-level mode.
7. If readback fails or disagrees, show state as unknown, close the session, and require explicit retry. Do not replay the write.

This mirrors an important general rule visible in HuaweiPods: a successful RFCOMM write only proves that bytes left the host, not that the earbuds applied the state.[^hp-write-state]

### Battery transaction

Recommended precedence:

1. Hide battery by default. Ignore historical UPower `0.000`/`unknown` samples completely.
2. If a live target `Battery1` appears, first cross-validate its target association, freshness, `0..100` range, `Source`, and meaning against an independent live observation. Until then, do not show it as a usable percentage.
3. If the private gate reaches `ReadVerified`, query `01/08` and show left/right/case with one shared observation timestamp.
4. Use tag `05` to mark each earbud in/out of case only for the Pro 5 route.
5. Show charging only for component positions whose tag-03 byte is understood. The public parser interprets zero as not charging, but the retained Pro 5 test does not assert a nonzero charging example; capture nonzero Pro 5 cases before relying on every possible status value.
6. Preserve the last valid live observation only as visibly stale data; never silently replace a failed read with zero.

Avoid continuous background polling in the first MVP. Query on opening the device panel, explicit refresh, and immediately after a relevant reconnection. A later hardware pass can measure whether a persistent session or notification command is safe and power-efficient.

### Audio and control coexistence

SPP/RFCOMM can coexist architecturally with A2DP and HFP over the same ACL link, and the SPP specification discusses concurrent profile use.[^spp] That does not prove this firmware accepts an extra vendor DLC while music, a call, and a second paired host are active.

Conservative policy:

- Never tear down or recreate the A2DP/HFP profile to get control access.
- Do not call broad `Device1.Connect()` for a control request.
- During an active call, defer nonessential battery refresh and new control-session creation.
- If another process appears to own the vendor channel, report busy rather than opening a competing socket.
- Do not attempt to manage Huawei's multipoint priority or pairing records.
- Let BlueZ, WirePlumber, and the earbuds handle reconnection. The host already has an all-device `bluez5.auto-connect = [ a2dp_sink a2dp_source ]` rule and historical boot reconnect attempts consistent with that policy. The application may retry a read after BlueZ reports a stable connected state, but must not add its own reconnect loop.

## Pairing and transport security

### Linux RFCOMM defaults

The Linux RFCOMM socket initializes `sec_level` to `BT_SECURITY_LOW`.[^linux-rfcomm-sock] Its legacy option mapping reports:

| Linux level | RFCOMM link-mode flags |
|---|---|
| Low | `RFCOMM_LM_AUTH` |
| Medium | `RFCOMM_LM_AUTH \| RFCOMM_LM_ENCRYPT` |
| High | Auth + encrypt + secure |

The modern `SOL_BLUETOOTH` / `BT_SECURITY` socket option can set the level before connection.[^linux-rfcomm-sock] RFCOMM's security check uses no-bonding authentication type for the default/low case and general bonding for medium.[^linux-rfcomm-core]

OpenFreebuds does not set an explicit security option before `connect()`, so it inherits the Linux default.[^ofb-transport] HuaweiPods first tries Android's secure SPP UUID socket, but its broad fallback list also includes insecure SPP, other SDP UUIDs, and secure/insecure channels 1 through 8.[^hp-controller] That breadth is useful for debugging unknown devices but is inappropriate for this constrained Linux client.

### Required policy

- Pair only through the trusted desktop Bluetooth UI.
- Require both `Paired` and `Bonded` before private access.
- Never write `Trusted`; trust is a local BlueZ policy separate from bonding.
- Set `BT_SECURITY_MEDIUM` before RFCOMM connect so authentication and encryption are requested.
- If medium security fails, show private controls unavailable. Do not retry low or insecure.
- Do not register a pairing agent.
- Do not ask for a PIN, passkey, or confirmation inside this application.
- Do not scan RFCOMM channels or replay packets against devices that merely share a Huawei-like name.
- Do not retain Bluetooth addresses in telemetry. Hashing a small address space is not sufficient anonymization; omit or locally redact it.
- Do not expose a raw-packet send box in normal builds.

Whether every FreeBuds Pro 5 firmware accepts an explicitly medium-security channel-1 connection is an evidence gap. This policy intentionally prefers fail-closed behavior over the wider compatibility of an insecure fallback.

## Deterministic fallback policy

| Condition | Required result |
|---|---|
| Device not paired or not bonded | Show instructions to use desktop Bluetooth settings; perform no private operation |
| Device connected for audio but private channel unavailable | Leave normal audio working; hide/disable private controls |
| Medium-security RFCOMM rejected | Do not downgrade; report secure control unavailable |
| SPP/channel identity uncertain | Do not scan; remain read-only or unavailable |
| DeviceInfo absent or model ID unknown | No writes; optionally permit an explicitly requested raw read-only diagnostic |
| DeviceInfo identities conflict in one stream | Fault session and close |
| Invalid length, oversized frame, truncated TLV, or bad CRC | Discard frame; do not update state; close after a small bounded fault threshold |
| Unknown well-formed TLV | Retain only in redacted diagnostics; do not infer meaning |
| Duplicate known TLV | Reject semantic frame as ambiguous |
| Battery tag missing or percentage outside `0..100` | Keep component unknown; never clamp protocol data into a valid-looking value |
| Private battery read times out | Show last valid value as stale with timestamp, or unknown if none |
| No live `Battery1`, only UPower `0.000`/`unknown` history | Hide battery; zero/unknown history is not a percentage |
| Live `Battery1` exists but freshness/source/semantics are not cross-validated | Hide it pending validation; do not merge it with private component values |
| Requested ANC state already active | No write |
| ANC write succeeds but readback fails | State becomes unknown; no automatic retry or inverse write |
| Requested codec unavailable | Let PipeWire negotiate another codec, ultimately SBC |
| L2HC or NearLink requested | Explain that the examined stock Linux stack has no implementation; do not substitute another codec |
| Another private-control owner is active | Wait or report busy; do not create a second vendor session |
| BlueZ disconnects, system suspends, or active device changes | Cancel queued reads, close socket, invalidate all pending callbacks |

## Explicit exclusions

The following should not be implemented from the current public corpus:

- Discrete ANC strengths such as comfort, balanced, ultra/deep, or dynamic.
- Voice-boost or human-voice transparency selection.
- Gesture assignment or long-press cycle configuration.
- Device-persistent EQ, sound-quality preference, spatial audio, or volume adaptation.
- Low-latency/game mode.
- Smart wear detection enable/disable writes.
- Multipoint pairing-record or connection-priority management.
- Find-device sounds.
- Factory reset, unpair, trust/untrust, or pairing-mode control.
- Firmware version changes or firmware update.
- Raw vendor notification subscription without a Pro 5 capture.
- Any command borrowed only from FreeBuds 5, 6i, Pro 3, Pro 4, 7i, FreeClip, or Eyewear.

OpenFreebuds' Pro 5 commit says it tested device info, battery, ANC levels, voice boost, sound quality, EQ presets, auto-pause, dual connect, in-ear state, voice language, gestures, and low latency.[^ofb-pro5-commit] Its driver wires handlers for those features.[^ofb-pro5] This is valuable evidence that broader support may be possible, but the repository does not retain a Pro 5 byte corpus for each claim.

HuaweiPods is more conservative for Pro 5: it enables ANC, transparency, ANC readback, RFCOMM battery, low-latency capability, a case, and Pro 5-specific availability, but leaves `supportsDiscreteAncLevels` and `supportsGestureConfiguration` false by omission.[^hp-capabilities] The report follows the intersection backed by retained Pro 5 bytes, not the union of feature assertions.

## Safe future capture procedure

This section describes a future evidence-gathering session. It was **not executed** during this research.

### Preconditions

- Obtain the owner's explicit consent and choose one known FreeBuds Pro 5 unit.
- Record public model, case model, region, current firmware, host kernel/BlueZ/PipeWire versions, and whether another phone is connected.
- Fully charge enough to avoid shutdown, but do not perform an intentional deep discharge.
- Disable or postpone firmware update prompts. Abort if an update starts.
- Pair beforehand using the normal UI. Do not reset, unpair, or alter trust for capture convenience.
- Silence unrelated Bluetooth devices and applications where practical to reduce private data in the trace.
- Never capture third-party devices without authorization.

### Capture artifacts

Collect separately:

- A Linux `btmon -w` trace for SDP, profile establishment, and Linux requests.
- BlueZ `Device1` properties and actual SDP service record, with addresses redacted in the publishable derivative.
- A list of resolved GATT services/characteristics, read-only first.
- If official-app traffic is needed, an owner-controlled Android Bluetooth HCI snoop trace with the exact app version and operation log.
- A plain-text timeline using monotonic timestamps and one operation per line.
- SHA-256 hashes of immutable original captures before making redacted copies.

Original captures may include addresses, device serials, phone identifiers, account-linked data, call metadata, and unrelated traffic. Keep originals private and publish only minimal redacted frame excerpts needed to prove a claim.

### Sequence

1. Capture an idle baseline with the already paired earbuds disconnected, then connected without playing audio.
2. Save the actual SDP record. Confirm whether SerialPort UUID `0x1101` is advertised and which RFCOMM channel it resolves to.
3. Resolve GATT services without writes. Record whether `0x180F/0x2A19` exists and what BlueZ reports as `Battery1.Source`.
4. Start normal A2DP playback at low volume and record the negotiated codec. Stop playback before private write tests.
5. From the official app, issue DeviceInfo and retain the complete CRC-valid Pro 5 `01/07` response, including firmware and internal model fields after privacy review.
6. Capture battery query/response with both earbuds out, left in case, right in case, both in case, and at least one naturally occurring charging state. Do not infer side order until physical actions and bytes agree in repeated trials.
7. Record the initial ANC state. With the earbuds not being worn, select Off, ANC, and Transparency one at a time. After each operation, perform a separate state query and repeat the full cycle at least three times.
8. Restore the owner's initial ANC state using the already verified operation.
9. Test the same read-only queries from Linux using medium-security RFCOMM, one request at a time.
10. Only after reviewing the trace offline, test the three already captured writes from Linux, each followed by readback.
11. Repeat read-only control access while A2DP is active, while HFP is idle, and with a second paired host connected. Do not test during a real call.
12. Close the control socket and confirm standard audio remains unchanged.

### Abort conditions

Abort immediately if:

- An unexpected pairing, authorization, firmware update, reset, or account prompt appears.
- The earbuds disconnect repeatedly, audio becomes unstable, or the case/earbuds become hot.
- A packet destination cannot be tied unambiguously to the owner's device.
- A write differs from the exact reviewed bytes.
- More than one private-control socket appears active.
- The initial state cannot be recovered safely.

### Evidence publication checklist

For each claimed command, retain:

- Exact full frame including CRC.
- Direction, transport, SDP UUID/channel, and security level.
- Device public model, internal model ID, submodel, and firmware.
- Official app/version or Linux client commit that produced it.
- Physical precondition and visible before/after result.
- At least two repeated observations, preferably across two Pro 5 units or firmware versions.
- Negative/error response and timeout behavior where obtainable without destructive actions.

## Evidence gaps and release gates

### Required before stable private controls

- A retained, privacy-reviewed FreeBuds Pro 5 DeviceInfo response proving `00016D` and its field layout.
- The actual Pro 5 SDP record proving the RFCOMM channel. The cached `0x1101` service class is useful but insufficient.
- A successful explicit-medium-security Linux RFCOMM connection, with no insecure fallback.
- ANC read/write/readback repetitions on at least two firmware revisions or a documented firmware compatibility range.
- Concurrency tests with A2DP playback, HFP profile availability/reliability, suspend/resume, and a second connected host.
- A recorded peer codec offer and selected codec; host codec-module presence is not negotiation evidence.
- Captured error/negative responses and behavior after a lost reply.

### Needed to improve battery quality

- Nonzero Pro 5 charging-state captures for left, right, and case.
- Repeated physical validation of tag `05` side ordering and all known values.
- Meaning of tags `04` and `06`, if the UI needs them; otherwise continue ignoring them.
- Whether `01/27` is a Pro 5 notification and how subscription/lifetime works.
- When case battery becomes stale and whether the firmware reports explicit case availability.
- Whether a live `Battery1` appears on Pro 5 and, if so, its source, freshness, and aggregation rule.

### Needed for advanced features

- Pro 5-specific request, response, and notification fixtures for every ANC sub-level.
- Pro 5-specific gesture reads/writes and accepted-value maps.
- Low-latency state read, write, acknowledgement, and interaction with codec negotiation.
- Wear-detection setting protocol and rollback behavior.
- EQ/sound preference capability discovery rather than copied model assumptions.

## Offline verification plan

Most implementation quality can be established without touching hardware.

### Framer tests

- Encode every request/write byte-for-byte.
- Recompute every fixture CRC independently.
- Feed every frame split at every possible byte boundary.
- Feed multiple valid frames in one read.
- Feed garbage before magic and between frames.
- Reject bad CRC, wrong version, invalid minimum length, over-limit length, and truncated TLVs.
- Reject duplicate known TLVs and retain unknown well-formed TLVs without interpreting them.
- Fuzz length/TLV arithmetic and assert bounded memory use and no panic.

### Semantic tests

- Decode all three Pro 5 ANC responses and keep shorter other-model fixtures isolated.
- Decode left/right/case `100/100/85` and tag-05 `out/in` from the captured battery frame.
- Preserve zero percent when tag `05` says out of case.
- Reject percentages over 100 and incorrect known-field lengths.
- Reject a valid frame for an unexpected service/command during a transaction.
- Require a strict DeviceInfo identity and reject conflicting valid identities.

### Transaction tests

- One outstanding request at a time.
- Cancellation invalidates queued and late callbacks after disconnect or device switch.
- A write never updates UI state without readback.
- A lost write response does not trigger automatic replay.
- Faulting one private feature never tears down standard PipeWire audio.
- A fake BlueZ object with `Paired=false` or `Bonded=false` can never open the transport.
- A medium-security failure can never select low/insecure fallback.

## Local Linux observations

These observations were collected or reviewed read-only on 2026-08-18. The target remained disconnected. No connection, discovery, service refresh, pairing, disconnection, or setting change was made.

Local evidence has three sub-tiers:

| Local tier | Content | What it can prove | What it cannot prove |
|---|---|---|---|
| E-cache | Disconnected BlueZ `Device1` and object tree | What BlueZ currently retains for this local target | Current peer offer, live service resolution, channel, codec, or battery |
| E-history | June-August 2026 journal, UPower files, and WirePlumber state | Specific events/state previously recorded by this host | Current behavior, selected codec when omitted, or universal device behavior |
| E-host | Installed packages/modules, linkage, services, and policy | What this host is capable of attempting | What the target offers or what a past session negotiated |

### Privacy-redacted target snapshot

The full BD_ADDR is omitted. It must remain omitted from logs, screenshots, fixtures, issue reports, and generated diagnostics unless the owner explicitly requests otherwise.

| Cached `Device1` field | Read-only observation | Interpretation limit |
|---|---|---|
| `Name` / `Alias` | `HUAWEI FreeBuds Pro 5` / `HUAWEI FreeBuds Pro 5` | Useful for user selection only; not a secure model identity |
| `AddressType` | `public` | Address value redacted; public type is not a product identifier |
| `Paired` / `Bonded` / `Trusted` | `true` / `true` / `true` | Confirms local BlueZ policy/cache; no link was active, and `Trusted` does not prove private-protocol identity |
| `Connected` | `false` | Confirms this was not a live target query |
| `ServicesResolved` | `false` | Cached UUIDs may remain, but no current resolution can be inferred |
| `LegacyPairing` | `false` | Does not prove the security level of a future RFCOMM socket |
| `Class` | `0x00240418` | Retain the raw value; do not use it as the Pro 5 identity gate |
| `Modalias` | `bluetooth:v027Dp4114d0000` | Retain as local diagnostic metadata; no mapping to private ID `00016D` is established |

While disconnected, the target object had no GATT child, `Battery1` object, `ManufacturerData`, or `ServiceData`. There was no current target UPower device or BlueZ battery-provider child. These absences are bounded by `Connected=false` and `ServicesResolved=false`; they do not prove that the objects/data never appear while connected.

### Cached service UUIDs

The standard names below come from Bluetooth SIG assigned numbers.[^assigned-cached-profiles] The last two UUIDs are intentionally not assigned a transport or meaning.

| Cached UUID | Standards-backed interpretation | Local conclusion |
|---|---|---|
| `00001000-0000-1000-8000-00805f9b34fb` | Service Discovery Server service class | Cached standard service class only |
| `00001101-0000-1000-8000-00805f9b34fb` | SerialPort | This unit previously exposed an SPP-class service; server channel remains unknown |
| `0000110b-0000-1000-8000-00805f9b34fb` | Audio Sink | Supports the standard A2DP interpretation together with local history |
| `0000110c-0000-1000-8000-00805f9b34fb` | A/V Remote Control Target | Supports AVRCP discovery; not a private-control path |
| `0000110d-0000-1000-8000-00805f9b34fb` | Advanced Audio Distribution | Supports A2DP discovery; no selected codec is encoded here |
| `0000110e-0000-1000-8000-00805f9b34fb` | A/V Remote Control | Supports AVRCP discovery |
| `0000111e-0000-1000-8000-00805f9b34fb` | Hands-Free | HFP was discovered; reliability remains unvalidated locally |
| `00001200-0000-1000-8000-00805f9b34fb` | PnP Information | Standard identification service class; not the Huawei DeviceInfo protocol |
| `0000fd9a-0000-1000-8000-00805f9b34fb` | **Unknown in this report** | Do not assign battery, transport, discovery, pairing, or vendor-control semantics |
| `00101020-4c42-0065-636e-614465747942` | **Opaque vendor UUID** | Do not infer RFCOMM, GATT, codec, or command semantics |

The UUID cache materially strengthens standard profile discovery, especially SPP `0x1101`. It does not contain a Battery Service `0x180F` entry, but the disconnected unresolved snapshot is insufficient to conclude that BAS is unsupported.

### Battery evidence

| Observation | Evidence value | MVP consequence |
|---|---|---|
| No live target `Battery1` | No current BlueZ percentage/source | Show no generic battery |
| Adapter has `BatteryProviderManager1` | Host can accept a provider | Does not mean PipeWire or another process currently publishes this target |
| No target provider/object | No current provider percentage | Show no provider-derived battery |
| No current target UPower device | No current UPower percentage | Do not synthesize a device from history |
| Historical target UPower files | Every connection-timestamped sample inspected was `0.000` and/or `unknown` | Invalid as a usable battery percentage; do not display zero |
| No target GATT children and no cached `0x180F` | No disconnected BAS evidence | Does not prove BAS absence while connected |

The local battery result is therefore **unknown**, not zero and not unsupported. The MVP must hide battery unless a live target `Battery1` is cross-validated or the private `01/08` response passes framing, CRC, identity, model-shape, and freshness checks.

### Historical audio evidence

Journal entries dated from June through August 2026 provide target-specific historical corroboration:

| Historical record | What it verifies | What remains unknown |
|---|---|---|
| Repeated A2DP media file-descriptor readiness | The target previously reached usable A2DP media transport on this host | Selected codec, bitrate, and current reliability |
| AVRCP kernel input-device creation | The target previously instantiated a standard media-control input path | Which controls were exercised in each session |
| HFP attempts returning refused or not-connected in some sessions | HFP was attempted and was not consistently ready | Root cause and steady-state call reliability |
| WirePlumber persistent route `a2dp-sink` | This host previously selected/stored the high-quality playback profile | Current profile and negotiated codec |

The report therefore treats A2DP playback and AVRCP controls as locally corroborated. It treats HFP as discovered and standards-feasible, but not locally reliability-validated. No historical line inspected records the selected A2DP codec.

### Host stack and policy

| Item | Read-only observation | Evidence boundary |
|---|---|---|
| Kernel | `Linux 7.1.8-arch1-3 x86_64 GNU/Linux` | Host only |
| BlueZ | `bluez 5.87-2`, `bluez-utils 5.87-2` | Host only |
| PipeWire | `pipewire 1:1.6.8-1`, `pipewire-audio 1:1.6.8-1` | Host only |
| WirePlumber | `wireplumber 0.5.15-1` | Host only |
| Codec libraries | `libldac 2.0.2.6-1`, `libfdk-aac 2.0.3-2` | Host libraries only |
| User services | `pipewire.service` and `wireplumber.service` active | Does not imply a target connection |
| Installed BlueZ SPA codecs | SBC, AAC, LDAC, aptX, FastStream, LC3, Opus, G.722, and HFP codec modules | Module presence is not peer offer or negotiation |
| LDAC module linkage | `libspa-codec-bluez5-ldac.so` dynamically links `libldac` | Confirms a functional host dependency, not target selection |
| WirePlumber profile preference | `bluetooth.profile-preference = "quality"` | Influences host profile choice; does not identify a codec |
| WirePlumber persistent storage | Enabled; target route history records `a2dp-sink` | Historical host policy/state only |
| FreeBuds-specific package | None installed | Historical standard-profile events came from the normal stack, not a known FreeBuds package |

The existing user configuration file
`~/.config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf`
contains an all-device rule:

```ini
bluez5.auto-connect = [ a2dp_sink a2dp_source ]
```

This is consistent with WirePlumber's documented `bluez5.auto-connect` property.[^wp-bluetooth] Together with persistent Bluetooth storage and quality preference, it explains historical boot/profile reconnect attempts. The MVP must not modify this rule or add its own reconnect loop.

### Read-only command ledger

The local evidence was recorded on 2026-08-18. The command ledger below is privacy-redacted: `<REDACTED_BDADDR>` and `<REDACTED_BDADDR_WITH_UNDERSCORES>` replace the sole target identifier wherever it occurred. No command below initiates discovery, connection, pairing, disconnection, service resolution, or a setting write.

```bash
date --iso-8601=seconds

TARGET='/org/bluez/hci0/dev_<REDACTED_BDADDR_WITH_UNDERSCORES>'
busctl --system introspect org.bluez "$TARGET" org.bluez.Device1
busctl --system tree org.bluez "$TARGET"
busctl --system introspect org.bluez /org/bluez/hci0 org.bluez.BatteryProviderManager1

upower --enumerate
upower --dump
sudo rg -n -i '<REDACTED_BDADDR>|HUAWEI FreeBuds Pro 5' /var/lib/upower

journalctl --no-pager --since '2026-06-01 00:00:00' --until '2026-08-19 00:00:00' \
  | rg -i '<REDACTED_BDADDR>|HUAWEI FreeBuds Pro 5'

uname -srmo
pacman -Q bluez bluez-utils pipewire pipewire-audio wireplumber libldac libfdk-aac
systemctl --user is-active pipewire.service wireplumber.service

ls -1 /usr/lib/spa-0.2/bluez5/
ldd /usr/lib/spa-0.2/bluez5/libspa-codec-bluez5-ldac.so

wpctl settings
rg -n 'bluez_card\.<REDACTED_BDADDR_WITH_UNDERSCORES>:profile:a2dp-sink' \
  ~/.local/state/wireplumber
nl -ba ~/.config/wireplumber/wireplumber.conf.d/bluetooth-a2dp-autoconnect.conf

pacman -Q | rg -i '(freebuds|huaweipods|openfreebuds)'
```

The final package query returned no match. Commands that read protected UPower history require only file-read privilege; they do not contact the target.

## Source register

All web sources were accessed 2026-08-18. Source-code links are pinned to immutable commits.

### Huawei and Bluetooth SIG

[^huawei-global-spec]: Huawei, [HUAWEI FreeBuds Pro 5 Specifications](https://consumer.huawei.com/en/headphones/freebuds-pro-5/specs/), accessed 2026-08-18.
[^huawei-cn-spec]: Huawei, [HUAWEI FreeBuds Pro 5 specifications, China](https://consumer.huawei.com/cn/headphones/freebuds-pro-5/specs/), accessed 2026-08-18.
[^huawei-support]: Huawei, [HUAWEI FreeBuds Pro 5 Repair and Service](https://consumer.huawei.com/en/support/headphones/freebuds-pro-5/), T0023 download entry, accessed 2026-08-18.
[^huawei-multidevice]: Huawei, [Multi-device connection of HUAWEI earbuds](https://consumer.huawei.com/en/support/content/en-us15907440/), accessed 2026-08-18.
[^huawei-wear]: Huawei, [Smart wear detection of HUAWEI earbuds](https://consumer.huawei.com/en/support/content/en-us00759671/), accessed 2026-08-18.
[^huawei-battery]: Huawei, [How to view Huawei earbud battery](https://consumer.huawei.com/cn/support/content/zh-cn00759662/), accessed 2026-08-18.
[^huawei-range]: Huawei, [Bluetooth usage and reconnection range of HUAWEI earbuds](https://consumer.huawei.com/en/support/content/en-us15829073/), accessed 2026-08-18.
[^huawei-pairing]: Huawei, [Connecting HUAWEI Bluetooth earbuds to a phone, tablet, or PC](https://consumer.huawei.com/en/support/content/en-us15868501/), accessed 2026-08-18.
[^bt-listing]: Bluetooth SIG qualification API, [Listing 303574](https://qualificationapi.bluetooth.com/api/Platform/Listings/Details/303574), accessed 2026-08-18.
[^spp]: Bluetooth SIG, [Serial Port Profile 1.2](https://www.bluetooth.com/specifications/specs/serial-port-profile-1-2/) and [HTML specification](https://www.bluetooth.com/specifications/specs/html/?src=SPP_v1.2/out/en/index-en.html), accessed 2026-08-18.
[^a2dp]: Bluetooth SIG, [Advanced Audio Distribution Profile 1.4.1](https://www.bluetooth.com/specifications/specs/advanced-audio-distribution-profile/), accessed 2026-08-18.
[^bas]: Bluetooth SIG, [Battery Service 1.1](https://www.bluetooth.com/specifications/specs/battery-service/), accessed 2026-08-18.
[^assigned-page]: Bluetooth SIG, [Assigned Numbers](https://www.bluetooth.com/specifications/assigned-numbers/), accessed 2026-08-18.
[^assigned-spp]: Bluetooth SIG public repository at `3cfa46a13ac1aac7440fd3df99f6b96fbf073354`, [`service_class.yaml`, lines 41-43](https://bitbucket.org/bluetooth-SIG/public/src/3cfa46a13ac1aac7440fd3df99f6b96fbf073354/assigned_numbers/uuids/service_class.yaml#lines-41:43).
[^assigned-bas]: Bluetooth SIG public repository at `3cfa46a13ac1aac7440fd3df99f6b96fbf073354`, [`service_uuids.yaml`, lines 74-76](https://bitbucket.org/bluetooth-SIG/public/src/3cfa46a13ac1aac7440fd3df99f6b96fbf073354/assigned_numbers/uuids/service_uuids.yaml#lines-74:76).
[^assigned-level]: Bluetooth SIG public repository at `3cfa46a13ac1aac7440fd3df99f6b96fbf073354`, [`characteristic_uuids.yaml`, lines 101-103](https://bitbucket.org/bluetooth-SIG/public/src/3cfa46a13ac1aac7440fd3df99f6b96fbf073354/assigned_numbers/uuids/characteristic_uuids.yaml#lines-101:103).
[^assigned-cached-profiles]: Bluetooth SIG public repository at `3cfa46a13ac1aac7440fd3df99f6b96fbf073354`, [`service_class.yaml`, standard discovery/audio classes at lines 35-82](https://bitbucket.org/bluetooth-SIG/public/src/3cfa46a13ac1aac7440fd3df99f6b96fbf073354/assigned_numbers/uuids/service_class.yaml#lines-35:82), [Hands-Free at lines 128-130](https://bitbucket.org/bluetooth-SIG/public/src/3cfa46a13ac1aac7440fd3df99f6b96fbf073354/assigned_numbers/uuids/service_class.yaml#lines-128:130), and [PnP Information at lines 215-217](https://bitbucket.org/bluetooth-SIG/public/src/3cfa46a13ac1aac7440fd3df99f6b96fbf073354/assigned_numbers/uuids/service_class.yaml#lines-215:217).

### Huawei protocol projects

HuaweiPods revision: `98ab835e3473f53715c2bc2ea15b920a3ab8e05a`, 2026-08-15.
OpenFreebuds revision: `035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee`, 2026-08-10.

[^hp-packets]: HuaweiPods, [`HuaweiAncPackets.kt`, lines 3-15 and 21-107](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/HuaweiAncPackets.kt#L3-L107).
[^hp-packet-tests]: HuaweiPods, [`HuaweiAncPacketsTest.kt`, Pro 5 mode writes at lines 113-129, battery query at 155-168, DeviceInfo and ANC queries at 200-227](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/test/java/moe/chenxy/huaweipods/pods/HuaweiAncPacketsTest.kt#L113-L227).
[^hp-parser]: HuaweiPods, [`HuaweiRfcommResponseParser.kt`, battery/ANC parsing at lines 28-85, stream/TLV parsing at 184-219, Pro 5 tag-05 mapping at 239-245](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/HuaweiRfcommResponseParser.kt#L28-L245).
[^hp-parser-tests]: HuaweiPods, [`HuaweiRfcommResponseParserTest.kt`, Pro 5 ANC fixtures at lines 43-52 and battery/availability fixtures at 284-340](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/test/java/moe/chenxy/huaweipods/pods/HuaweiRfcommResponseParserTest.kt#L43-L52), [battery section](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/test/java/moe/chenxy/huaweipods/pods/HuaweiRfcommResponseParserTest.kt#L284-L340).
[^hp-identity]: HuaweiPods, [`HuaweiDeviceInfoIdentity.kt`, lines 10-149](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/HuaweiDeviceInfoIdentity.kt#L10-L149).
[^hp-identity-tests]: HuaweiPods, [`HuaweiDeviceInfoIdentityParserTest.kt`, lines 7-57](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/test/java/moe/chenxy/huaweipods/pods/HuaweiDeviceInfoIdentityParserTest.kt#L7-L57).
[^hp-route]: HuaweiPods, [`HuaweiDeviceInfoRoutePolicy.kt`, lines 3-28](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/HuaweiDeviceInfoRoutePolicy.kt#L3-L28).
[^hp-capabilities]: HuaweiPods, [`DeviceCapabilities.kt`, Pro 5 lines 95-105](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/DeviceCapabilities.kt#L95-L105) and [capability accessors at 181-212](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/DeviceCapabilities.kt#L181-L212).
[^hp-controller]: HuaweiPods, [`HuaweiL2capAncController.kt`, secure route probe at lines 159-213, serialized queue at 304-394, and broad fallback candidates at 462-490](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/HuaweiL2capAncController.kt#L159-L213), [transport section](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/HuaweiL2capAncController.kt#L304-L516).
[^hp-write-state]: HuaweiPods, [`FreeClip2AudioStateTracker.kt`, write-state warning at lines 1-8](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/app/src/main/java/moe/chenxy/huaweipods/pods/FreeClip2AudioStateTracker.kt#L1-L8).
[^ofb-frame]: OpenFreebuds, [`package.py`, serialization and parsing at lines 79-129](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/package.py#L79-L129).
[^ofb-crc]: OpenFreebuds, [`utils.py`, CRC implementation at lines 7-34](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/utils.py#L7-L34).
[^ofb-transport]: OpenFreebuds, [`spp_transport.py`, lines 17-33](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/generic/spp_transport.py#L17-L33).
[^ofb-pro5]: OpenFreebuds, [`buds_pro_5.py`, lines 5-29](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/driver/per_model/buds_pro_5.py#L5-L29).
[^ofb-driver-map]: OpenFreebuds, [`driver/constants.py`, model-name mapping](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/constants.py#L6-L18).
[^ofb-pro5-commit]: OpenFreebuds, [commit `530e2d7b5aef42e53b0ef6b76bfc3ce78caaada7`, "Add HUAWEI FreeBuds Pro 5 driver"](https://github.com/melianmiko/OpenFreebuds/commit/530e2d7b5aef42e53b0ef6b76bfc3ce78caaada7), 2026-08-02.
[^ofb-generic]: OpenFreebuds, [`generic.py`, response handling at lines 59-127](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/openfreebuds/driver/huawei/driver/generic.py#L59-L127).
[^ofb-flatpak]: OpenFreebuds, [Flatpak manifest, lines 10-22](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/scripts/flatpak/pw.mmk.OpenFreebuds.yml#L10-L22).

Both HuaweiPods and OpenFreebuds are distributed under GPLv3.[^hp-license][^ofb-license] The byte-level observations can guide an independent implementation, but anyone copying code should perform an appropriate license review.

[^hp-license]: HuaweiPods, [GPLv3 license](https://github.com/Nshpiter/HuaweiPods/blob/98ab835e3473f53715c2bc2ea15b920a3ab8e05a/LICENSE).
[^ofb-license]: OpenFreebuds, [GPLv3 license](https://github.com/melianmiko/OpenFreebuds/blob/035bf2a87cdda9e9c8e8e90c662b7fa61270c6ee/LICENSE).

### Linux stack

BlueZ revision: `bd8989620ed6e80755f06cfdb18f5b4a3913493c`, 2026-08-14.
PipeWire revision: `adfb948ec5e5817d82cb3fcf64f3a652a76312ea`, 2026-08-14.
WirePlumber revision: `d466646e0c4ee663339d5defb955ccdfa93c6c70`, 2026-08-17.
Linux revision: `0f23d56f17fdfc7db69d51f64c8b91bbab947aa9`, 2026-08-17.

[^bluez-device]: BlueZ, [`org.bluez.Device1` API, connection methods at lines 25-121 and properties at 282-313](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/doc/org.bluez.Device.rst#L25-L121), [properties](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/doc/org.bluez.Device.rst#L282-L313).
[^bluez-battery]: BlueZ, [`org.bluez.Battery1` API, lines 14-38](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/doc/org.bluez.Battery.rst#L14-L38).
[^bluez-battery-plugin]: BlueZ, [GATT battery plugin UUID and registration, lines 45-61 and 91-147](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/profiles/battery/battery.c#L45-L61), [registration](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/profiles/battery/battery.c#L91-L147).
[^bluez-gatt]: BlueZ, [`org.bluez.GattCharacteristic1` read/write/notify API](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/doc/org.bluez.GattCharacteristic.rst#L43-L154), [notify methods](https://github.com/bluez/bluez/blob/bd8989620ed6e80755f06cfdb18f5b4a3913493c/doc/org.bluez.GattCharacteristic.rst#L203-L287).
[^pw-props]: PipeWire, [`pipewire-props.7.md`, Bluetooth roles and codecs at lines 1166-1198](https://github.com/PipeWire/pipewire/blob/adfb948ec5e5817d82cb3fcf64f3a652a76312ea/doc/dox/config/pipewire-props.7.md#L1166-L1198).
[^pw-codec-build]: PipeWire, [`spa/meson.build`, optional LDAC, LHDC, aptX, and AAC dependencies at lines 75-103](https://github.com/PipeWire/pipewire/blob/adfb948ec5e5817d82cb3fcf64f3a652a76312ea/spa/meson.build#L75-L103).
[^pw-hfp-battery]: PipeWire, [`backend-native.c`, HFP battery conversions at lines 1010-1070 and input parsing at 1397-1437](https://github.com/PipeWire/pipewire/blob/adfb948ec5e5817d82cb3fcf64f3a652a76312ea/spa/plugins/bluez5/backend-native.c#L1010-L1070), [AT parsing](https://github.com/PipeWire/pipewire/blob/adfb948ec5e5817d82cb3fcf64f3a652a76312ea/spa/plugins/bluez5/backend-native.c#L1397-L1437).
[^pw-battery-provider]: PipeWire, [`bluez5-dbus.c`, Battery Provider registration at lines 296-479 and reporting at 7919-7947](https://github.com/PipeWire/pipewire/blob/adfb948ec5e5817d82cb3fcf64f3a652a76312ea/spa/plugins/bluez5/bluez5-dbus.c#L296-L479), [reporting](https://github.com/PipeWire/pipewire/blob/adfb948ec5e5817d82cb3fcf64f3a652a76312ea/spa/plugins/bluez5/bluez5-dbus.c#L7919-L7947).
[^wp-bluetooth]: WirePlumber, [Bluetooth roles/codecs at lines 59-115](https://github.com/PipeWire/wireplumber/blob/d466646e0c4ee663339d5defb955ccdfa93c6c70/docs/rst/daemon/configuration/bluetooth.rst#L59-L115), [device rules and auto-connect at lines 180-280](https://github.com/PipeWire/wireplumber/blob/d466646e0c4ee663339d5defb955ccdfa93c6c70/docs/rst/daemon/configuration/bluetooth.rst#L180-L280).
[^linux-l2cap]: Linux, [`L2CAP_PSM_RFCOMM = 0x0003`](https://github.com/torvalds/linux/blob/0f23d56f17fdfc7db69d51f64c8b91bbab947aa9/include/net/bluetooth/l2cap.h#L240-L249).
[^linux-rfcomm-h]: Linux, [`sockaddr_rc` and RFCOMM link-mode flags](https://github.com/torvalds/linux/blob/0f23d56f17fdfc7db69d51f64c8b91bbab947aa9/include/net/bluetooth/rfcomm.h#L279-L310).
[^linux-rfcomm-sock]: Linux, [RFCOMM default low security at `sock.c` lines 249-273](https://github.com/torvalds/linux/blob/0f23d56f17fdfc7db69d51f64c8b91bbab947aa9/net/bluetooth/rfcomm/sock.c#L249-L273), [security setters/getters at lines 635-778](https://github.com/torvalds/linux/blob/0f23d56f17fdfc7db69d51f64c8b91bbab947aa9/net/bluetooth/rfcomm/sock.c#L635-L778).
[^linux-rfcomm-core]: Linux, [RFCOMM authentication type selection and default at `core.c` lines 209-230 and 285-298](https://github.com/torvalds/linux/blob/0f23d56f17fdfc7db69d51f64c8b91bbab947aa9/net/bluetooth/rfcomm/core.c#L209-L230), [default](https://github.com/torvalds/linux/blob/0f23d56f17fdfc7db69d51f64c8b91bbab947aa9/net/bluetooth/rfcomm/core.c#L285-L298).

## Final recommendation

Proceed with a staged Linux implementation only if the product is presented honestly as experimental private-protocol support:

1. Build standard audio integration by observing, not replacing, BlueZ/PipeWire/WirePlumber.
2. Implement and exhaustively test the strict offline framer and fixture corpus.
3. Add a read-only, explicitly selected, paired/bonded, medium-security RFCOMM diagnostic path.
4. Require strict DeviceInfo plus Pro 5-shaped read evidence before exposing component battery.
5. Put the three exact ANC writes behind a second opt-in and mandatory readback.
6. Gather and retain the missing SDP, DeviceInfo, security, and concurrency captures before calling private controls stable.

If those gates cannot be met, the deterministic product is still useful: locally corroborated standard A2DP/AVRCP audio, HFP labeled as discovered but not reliability-validated, battery hidden until live cross-validation, and Huawei-private controls unavailable rather than guessed.
