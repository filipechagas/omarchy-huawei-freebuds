.pragma library

var PROTOCOL_VERSION = 1
var BRIDGE_VERSION = "0.1.0"
var TARGET_DEVICE_NAME = "HUAWEI FreeBuds Pro 5"
var MAX_JSONL_BYTES = 16 * 1024
var FRESH_SECONDS = 130
var EXPIRE_SECONDS = 10 * 60

var ANC_MODES = ["off", "anc", "awareness"]
var BRIDGE_ERROR_CODES = [
    "invalid_request",
    "busy",
    "config_invalid",
    "config_write_failed",
    "invalid_address",
    "transport_unsupported",
    "security_failed",
    "connect_failed",
    "transport_busy",
    "timeout",
    "socket_closed",
    "invalid_frame",
    "unexpected_response",
    "identity_mismatch",
    "identity_conflict",
    "battery_invalid",
    "anc_invalid",
    "anc_send_failed",
    "anc_readback_failed",
    "anc_readback_mismatch"
]

var USER_MESSAGES = {
    service_starting: "FreeBuds service is starting",
    service_unavailable: "Private controls unavailable",
    helper_unavailable: "Private helper unavailable",
    hello_timeout: "Private helper did not start",
    helper_stopped: "Private helper stopped",
    protocol_error: "Private helper protocol error",
    invalid_request: "Private helper rejected the request",
    busy: "Private request already in progress",
    no_adapter: "No Bluetooth adapter",
    adapter_off: "Bluetooth is off. Use Omarchy Bluetooth to turn it on.",
    no_candidate: "Pair FreeBuds Pro 5 in Omarchy Bluetooth",
    candidate_disconnected: "Connect the earbuds in Omarchy Bluetooth",
    multiple_candidates: "Select a device, then Retry",
    selected_unavailable: "Selected earbuds are not available",
    selected_disconnected: "Connect the earbuds in Omarchy Bluetooth",
    config_invalid: "Saved device selection is invalid",
    config_write_failed: "Could not save device selection",
    invalid_address: "Invalid selected device",
    transport_unsupported: "Secure private channel unavailable",
    security_failed: "Secure private channel unavailable",
    connect_failed: "Private channel unavailable",
    transport_busy: "Private channel unavailable",
    timeout: "Private request timed out",
    socket_closed: "Private channel unavailable",
    invalid_frame: "Invalid private response",
    unexpected_response: "Unexpected private response",
    identity_mismatch: "This device is not a verified FreeBuds Pro 5",
    identity_conflict: "Device identity conflict",
    capabilities_unverified: "Private capabilities not verified",
    battery_invalid: "Battery components not reported",
    anc_invalid: "Noise control not reported",
    anc_send_failed: "Noise control change was not confirmed",
    anc_readback_failed: "Noise control change was not confirmed",
    anc_readback_mismatch: "Earbuds reported a different mode",
    battery_stale: "Battery data is out of date",
    anc_stale: "Noise control data is out of date",
    private_expired: "Not reported"
}

function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value)
}

function hasOwn(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key)
}

function hasExactKeys(object, required, optional) {
    if (!isPlainObject(object))
        return false

    var allowed = required.concat(optional || [])
    var keys = Object.keys(object)
    for (var i = 0; i < required.length; i++) {
        if (!hasOwn(object, required[i]))
            return false
    }
    for (var k = 0; k < keys.length; k++) {
        if (allowed.indexOf(keys[k]) === -1)
            return false
    }
    return true
}

function isFiniteNumber(value) {
    return typeof value === "number" && isFinite(value)
}

function isInteger(value) {
    return isFiniteNumber(value) && Math.floor(value) === value
}

function isRequestNumber(value) {
    return isInteger(value) && value >= 0 && value <= 9007199254740991
}

function isCanonicalAddress(value) {
    return typeof value === "string" && /^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$/.test(value)
}

function isAncMode(value) {
    return typeof value === "string" && ANC_MODES.indexOf(value) !== -1
}

function isPercent(value) {
    return isInteger(value) && value >= 0 && value <= 100
}

function isNullablePercent(value) {
    return value === null || isPercent(value)
}

function genericBatteryPercent(device) {
    if (!device || device.connected !== true || device.batteryAvailable !== true)
        return null
    if (!isFiniteNumber(device.battery) || device.battery < 0 || device.battery > 1)
        return null
    return Math.round(device.battery * 100)
}

function formatPercent(value) {
    return isPercent(value) ? value + "%" : "Not reported"
}

function sanitizeDisplayText(value, fallback, maximumLength) {
    var text = typeof value === "string" ? value : ""
    text = text.replace(/[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}/g, "Device")
        .replace(/[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g, " ")
        .replace(/\s+/g, " ").trim()
    var limit = isInteger(maximumLength) && maximumLength > 0 ? maximumLength : 80
    if (text.length > limit) {
        if (text.charCodeAt(limit - 1) >= 0xd800 && text.charCodeAt(limit - 1) <= 0xdbff)
            limit -= 1
        text = text.substr(0, limit)
    }
    return text.length > 0 ? text : (fallback || "")
}

function normalizeDevice(value) {
    var source = isPlainObject(value) ? value : {}
    var address = typeof source.address === "string" ? source.address : ""
    var deviceName = typeof source.deviceName === "string" ? source.deviceName : ""
    var rawLabel = typeof source.name === "string" ? source.name : source.displayLabel
    var displayLabel = sanitizeDisplayText(rawLabel, sanitizeDisplayText(deviceName, "Device", 80), 80)
    var available = source.batteryAvailable === true
        && isFiniteNumber(source.battery)
        && source.battery >= 0
        && source.battery <= 1

    return {
        address: address,
        addressValid: isCanonicalAddress(address),
        deviceName: deviceName,
        displayLabel: displayLabel,
        paired: source.paired === true,
        bonded: source.bonded === true,
        connected: source.connected === true,
        batteryAvailable: available,
        battery: available ? source.battery : null
    }
}

function normalizeGeneric(snapshot) {
    var source = isPlainObject(snapshot) ? snapshot : {}
    var values = Array.isArray(source.devices) ? source.devices : []
    var devices = []
    for (var i = 0; i < values.length; i++)
        devices.push(normalizeDevice(values[i]))

    var adapterPresent = source.adapterPresent === true
    return {
        adapterPresent: adapterPresent,
        adapterEnabled: adapterPresent && source.adapterEnabled === true,
        devices: devices
    }
}

function compareRows(left, right) {
    var a = left.displayLabel.toLowerCase()
    var b = right.displayLabel.toLowerCase()
    if (a < b)
        return -1
    if (a > b)
        return 1
    if (left.address < right.address)
        return -1
    if (left.address > right.address)
        return 1
    return 0
}

function candidateRows(genericOrDevices) {
    var devices = Array.isArray(genericOrDevices)
        ? genericOrDevices
        : (genericOrDevices && Array.isArray(genericOrDevices.devices) ? genericOrDevices.devices : [])
    var candidates = []
    for (var i = 0; i < devices.length; i++) {
        var row = normalizeDevice(devices[i])
        if (row.addressValid
                && row.deviceName === TARGET_DEVICE_NAME
                && row.paired
                && row.bonded) {
            candidates.push(row)
        }
    }
    candidates.sort(compareRows)
    return candidates
}

function deviceForAddress(genericOrDevices, address) {
    if (!isCanonicalAddress(address))
        return null
    var devices = Array.isArray(genericOrDevices)
        ? genericOrDevices
        : (genericOrDevices && Array.isArray(genericOrDevices.devices) ? genericOrDevices.devices : [])
    for (var i = 0; i < devices.length; i++) {
        var row = normalizeDevice(devices[i])
        if (row.address === address && row.paired && row.bonded)
            return row
    }
    return null
}

function candidateForAddress(genericOrDevices, address) {
    var candidates = candidateRows(genericOrDevices)
    for (var i = 0; i < candidates.length; i++) {
        if (candidates[i].address === address)
            return candidates[i]
    }
    return null
}

function fallbackSelection(snapshot) {
    var generic = normalizeGeneric(snapshot)
    if (!generic.adapterPresent || !generic.adapterEnabled)
        return null
    var candidates = candidateRows(generic)
    var connected = []
    for (var i = 0; i < candidates.length; i++) {
        if (candidates[i].connected)
            connected.push(candidates[i])
    }
    return connected.length === 1 ? connected[0] : null
}

function fallbackView(snapshot) {
    var generic = normalizeGeneric(snapshot)
    var selected = fallbackSelection(generic)
    var percent = genericBatteryPercent(selected)
    var connection = !generic.adapterPresent ? "No Bluetooth adapter"
        : !generic.adapterEnabled ? "Bluetooth is off"
        : selected ? "Connected"
        : "No unambiguous connected earbuds"
    var spoken = "FreeBuds Pro 5, " + connection.toLowerCase()
    if (percent !== null)
        spoken += ", earbuds " + percent + " percent"

    return {
        generic: generic,
        selectedDevice: selected,
        connected: selected !== null,
        aggregatePercent: percent,
        aggregateText: percent === null ? "Not reported" : percent + "%",
        showAggregateBattery: true,
        connectionText: connection,
        barPercentText: percent === null ? "" : percent + "%",
        barAncMode: "",
        barAncText: "",
        barAccessibleName: spoken,
        barTooltip: "FreeBuds Pro 5: " + connection,
        message: "FreeBuds service is starting",
        candidates: candidateRows(generic)
    }
}

function utf8Length(value) {
    if (typeof value !== "string")
        return -1
    var length = 0
    for (var i = 0; i < value.length; i++) {
        var code = value.charCodeAt(i)
        if (code <= 0x7f) {
            length += 1
        } else if (code <= 0x7ff) {
            length += 2
        } else if (code >= 0xd800 && code <= 0xdbff) {
            if (i + 1 >= value.length)
                return -1
            var low = value.charCodeAt(i + 1)
            if (low < 0xdc00 || low > 0xdfff)
                return -1
            length += 4
            i += 1
        } else if (code >= 0xdc00 && code <= 0xdfff) {
            return -1
        } else {
            length += 3
        }
    }
    return length
}

function parseJsonLine(line) {
    var byteLength = utf8Length(line)
    if (byteLength <= 0 || byteLength + 1 > MAX_JSONL_BYTES)
        return { ok: false, code: "protocol_error" }

    var parser = { text: line, index: 0 }

    function fail() {
        throw "invalid-json"
    }

    function skipWhitespace() {
        while (parser.index < parser.text.length
               && /[\x20\x09\x0a\x0d]/.test(parser.text.charAt(parser.index))) {
            parser.index += 1
        }
    }

    function parseString() {
        if (parser.text.charAt(parser.index) !== '"')
            fail()
        var start = parser.index
        parser.index += 1
        while (parser.index < parser.text.length) {
            var code = parser.text.charCodeAt(parser.index)
            var character = parser.text.charAt(parser.index)
            if (character === '"') {
                parser.index += 1
                return JSON.parse(parser.text.substring(start, parser.index))
            }
            if (code < 0x20)
                fail()
            if (character === "\\") {
                parser.index += 1
                if (parser.index >= parser.text.length)
                    fail()
                var escaped = parser.text.charAt(parser.index)
                if ('"\\/bfnrt'.indexOf(escaped) === -1) {
                    if (escaped !== "u")
                        fail()
                    var hex = parser.text.substr(parser.index + 1, 4)
                    if (!/^[0-9a-fA-F]{4}$/.test(hex))
                        fail()
                    parser.index += 4
                }
            }
            parser.index += 1
        }
        fail()
    }

    function parseNumber() {
        var match = parser.text.substring(parser.index).match(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/)
        if (!match)
            fail()
        parser.index += match[0].length
        var number = Number(match[0])
        if (!isFinite(number))
            fail()
        return number
    }

    function parseArray(depth) {
        if (depth > 32)
            fail()
        parser.index += 1
        skipWhitespace()
        var result = []
        if (parser.text.charAt(parser.index) === "]") {
            parser.index += 1
            return result
        }
        while (parser.index < parser.text.length) {
            result.push(parseValue(depth + 1))
            skipWhitespace()
            var separator = parser.text.charAt(parser.index)
            if (separator === "]") {
                parser.index += 1
                return result
            }
            if (separator !== ",")
                fail()
            parser.index += 1
            skipWhitespace()
        }
        fail()
    }

    function parseObject(depth) {
        if (depth > 32)
            fail()
        parser.index += 1
        skipWhitespace()
        var result = {}
        var keys = []
        if (parser.text.charAt(parser.index) === "}") {
            parser.index += 1
            return result
        }
        while (parser.index < parser.text.length) {
            var key = parseString()
            if (keys.indexOf(key) !== -1)
                fail()
            if (key === "__proto__" || key === "prototype" || key === "constructor")
                fail()
            keys.push(key)
            skipWhitespace()
            if (parser.text.charAt(parser.index) !== ":")
                fail()
            parser.index += 1
            skipWhitespace()
            result[key] = parseValue(depth + 1)
            skipWhitespace()
            var separator = parser.text.charAt(parser.index)
            if (separator === "}") {
                parser.index += 1
                return result
            }
            if (separator !== ",")
                fail()
            parser.index += 1
            skipWhitespace()
        }
        fail()
    }

    function parseValue(depth) {
        skipWhitespace()
        var character = parser.text.charAt(parser.index)
        if (character === '"')
            return parseString()
        if (character === "{")
            return parseObject(depth)
        if (character === "[")
            return parseArray(depth)
        if (parser.text.substr(parser.index, 4) === "true") {
            parser.index += 4
            return true
        }
        if (parser.text.substr(parser.index, 5) === "false") {
            parser.index += 5
            return false
        }
        if (parser.text.substr(parser.index, 4) === "null") {
            parser.index += 4
            return null
        }
        if (character === "-" || /[0-9]/.test(character))
            return parseNumber()
        fail()
    }

    try {
        var value = parseValue(0)
        skipWhitespace()
        if (parser.index !== parser.text.length || !isPlainObject(value))
            fail()
        return { ok: true, value: value }
    } catch (error) {
        return { ok: false, code: "protocol_error" }
    }
}

function validateHello(message) {
    var keys = ["v", "type", "bridgeVersion", "selectedAddress"]
    if (!hasExactKeys(message, keys))
        return { ok: false }
    if (message.v !== PROTOCOL_VERSION
            || message.type !== "hello"
            || message.bridgeVersion !== BRIDGE_VERSION
            || (message.selectedAddress !== null && !isCanonicalAddress(message.selectedAddress))) {
        return { ok: false }
    }
    return {
        ok: true,
        selectedAddress: message.selectedAddress
    }
}

function validateStartupError(message) {
    if (!hasExactKeys(message, ["v", "type", "code"]))
        return { ok: false }
    if (message.v !== PROTOCOL_VERSION || message.type !== "error" || message.code !== "config_invalid")
        return { ok: false }
    return { ok: true, code: message.code }
}

function isBridgeErrorCode(value) {
    return typeof value === "string" && BRIDGE_ERROR_CODES.indexOf(value) !== -1
}

function featureErrorValid(value, feature) {
    if (value === null)
        return true
    if (feature === "battery")
        return value === "battery_invalid"
    return ["anc_invalid", "timeout", "socket_closed", "invalid_frame", "unexpected_response"]
        .indexOf(value) !== -1
}

function validateResponseBase(message, pending) {
    if (!isPlainObject(message) || !isPlainObject(pending))
        return false
    if (message.v !== PROTOCOL_VERSION)
        return false
    if (message.type !== "result" && message.type !== "error")
        return false
    if (!isRequestNumber(message.id) || message.id !== pending.id)
        return false
    if (!isRequestNumber(message.generation) || message.generation !== pending.generation)
        return false
    return true
}

function validateRefreshResult(message, pending) {
    var keys = [
        "v", "type", "id", "generation", "address", "verified", "selectedAddress",
        "left", "right", "case", "anc", "batteryError", "ancError"
    ]
    if (!hasExactKeys(message, keys) || !validateResponseBase(message, pending))
        return { ok: false }
    if (message.type !== "result"
            || message.address !== pending.address
            || !isCanonicalAddress(message.address)
            || message.verified !== true
            || message.selectedAddress !== message.address
            || !isNullablePercent(message.left)
            || !isNullablePercent(message.right)
            || !isNullablePercent(message.case)
            || (message.anc !== null && !isAncMode(message.anc))
            || !featureErrorValid(message.batteryError, "battery")
            || !featureErrorValid(message.ancError, "anc")) {
        return { ok: false }
    }

    var batteryValid = isPercent(message.left) && isPercent(message.right) && isPercent(message.case)
    var batteryEmpty = message.left === null && message.right === null && message.case === null
    if ((!batteryValid && !batteryEmpty)
            || (batteryValid && message.batteryError !== null)
            || (batteryEmpty && message.batteryError === null)) {
        return { ok: false }
    }

    var ancValid = isAncMode(message.anc)
    if ((ancValid && message.ancError !== null)
            || (!ancValid && message.ancError === null)
            || (!batteryValid && !ancValid)) {
        return { ok: false }
    }

    return {
        ok: true,
        kind: "result",
        method: "refresh",
        address: message.address,
        selectedAddress: message.selectedAddress,
        battery: batteryValid ? {
            left: message.left,
            right: message.right,
            case: message.case
        } : null,
        anc: ancValid ? message.anc : null,
        batteryError: message.batteryError,
        ancError: message.ancError
    }
}

function validateAncResult(message, pending) {
    var keys = ["v", "type", "id", "generation", "address", "verified", "anc"]
    if (!hasExactKeys(message, keys) || !validateResponseBase(message, pending))
        return { ok: false }
    if (message.type !== "result"
            || message.address !== pending.address
            || !isCanonicalAddress(message.address)
            || message.verified !== true
            || !isAncMode(message.anc)
            || !isAncMode(pending.mode)
            || message.anc !== pending.mode) {
        return { ok: false }
    }
    return {
        ok: true,
        kind: "result",
        method: "set_anc",
        address: message.address,
        anc: message.anc
    }
}

function validateLocalResult(message, pending) {
    var keys = ["v", "type", "id", "generation", "address", "selectedAddress"]
    if (!hasExactKeys(message, keys) || !validateResponseBase(message, pending))
        return { ok: false }
    if (message.type !== "result" || message.address !== null || message.selectedAddress !== null)
        return { ok: false }
    return {
        ok: true,
        kind: "result",
        method: pending.method,
        address: null,
        selectedAddress: null
    }
}

function validateError(message, pending) {
    var keys = ["v", "type", "id", "generation", "address", "code", "observedAnc"]
    if (!hasExactKeys(message, keys) || !validateResponseBase(message, pending))
        return { ok: false }
    if (message.type !== "error"
            || message.address !== (pending.address || null)
            || !isBridgeErrorCode(message.code)
            || (message.observedAnc !== null && !isAncMode(message.observedAnc))) {
        return { ok: false }
    }
    if ((message.code === "anc_readback_mismatch") !== isAncMode(message.observedAnc))
        return { ok: false }
    return {
        ok: true,
        kind: "error",
        method: pending.method,
        address: message.address,
        code: message.code,
        observedAnc: message.observedAnc
    }
}

function validateResponse(message, pending) {
    if (!validateResponseBase(message, pending))
        return { ok: false }
    if (message.type === "error")
        return validateError(message, pending)
    if (pending.method === "refresh")
        return validateRefreshResult(message, pending)
    if (pending.method === "set_anc")
        return validateAncResult(message, pending)
    if (pending.method === "clear_selection" || pending.method === "shutdown")
        return validateLocalResult(message, pending)
    return { ok: false }
}

function responseShape(message) {
    if (!isPlainObject(message)
            || message.v !== PROTOCOL_VERSION
            || (message.type !== "result" && message.type !== "error")
            || !isRequestNumber(message.id)
            || !isRequestNumber(message.generation)) {
        return { ok: false }
    }

    var address = hasOwn(message, "address") ? message.address : null
    var synthetic = {
        id: message.id,
        generation: message.generation,
        address: address,
        method: "refresh"
    }
    if (message.type === "error") {
        var error = validateError(message, synthetic)
        return error.ok ? { ok: true, kind: "error", method: "" } : { ok: false }
    }
    if (validateRefreshResult(message, synthetic).ok)
        return { ok: true, kind: "result", method: "refresh" }
    synthetic.method = "set_anc"
    synthetic.mode = message.anc
    if (validateAncResult(message, synthetic).ok)
        return { ok: true, kind: "result", method: "set_anc" }
    synthetic.method = "clear_selection"
    if (validateLocalResult(message, synthetic).ok)
        return { ok: true, kind: "result", method: "local" }
    return { ok: false }
}

function classifyResponse(message, pending) {
    var shape = responseShape(message)
    if (!shape.ok)
        return { kind: "protocol_error" }
    if (!isPlainObject(pending))
        return { kind: "stale" }
    var sameCorrelation = message.id === pending.id
        && message.generation === pending.generation
    if (shape.kind === "result") {
        var expectedMethod = pending.method === "clear_selection" || pending.method === "shutdown"
            ? "local" : pending.method
        if (shape.method !== expectedMethod)
            return { kind: sameCorrelation ? "protocol_error" : "stale" }
    }
    var validated = validateResponse(message, pending)
    if (validated.ok)
        return { kind: "accepted", value: validated }
    if (sameCorrelation
            && pending.method === "set_anc"
            && shape.method === "set_anc"
            && message.address === pending.address
            && message.anc !== pending.mode) {
        return { kind: "protocol_error" }
    }
    return { kind: "stale" }
}

function emptyPrivateState() {
    return {
        verified: false,
        address: null,
        generation: null,
        battery: null,
        anc: null,
        batteryError: null,
        ancError: null
    }
}

function initialState() {
    return {
        generation: 0,
        helperPhase: "waiting",
        helperError: null,
        selectionLoaded: false,
        selectedAddress: null,
        markedAddress: null,
        configInvalid: false,
        generic: normalizeGeneric(null),
        pending: null,
        privateState: emptyPrivateState(),
        lastCode: null
    }
}

function copyState(state) {
    return {
        generation: state.generation,
        helperPhase: state.helperPhase,
        helperError: state.helperError,
        selectionLoaded: state.selectionLoaded,
        selectedAddress: state.selectedAddress,
        markedAddress: state.markedAddress,
        configInvalid: state.configInvalid,
        generic: state.generic,
        pending: state.pending,
        privateState: state.privateState,
        lastCode: state.lastCode
    }
}

function observation(address, generation, receivedAtMs, values) {
    var result = {
        address: address,
        generation: generation,
        receivedAtMs: receivedAtMs,
        lastAgedAtMs: receivedAtMs,
        ageSeconds: 0
    }
    var keys = Object.keys(values)
    for (var i = 0; i < keys.length; i++)
        result[keys[i]] = values[keys[i]]
    return result
}

function selectedDevice(state) {
    return deviceForAddress(state.generic, state.selectedAddress)
}

function displayDevice(state) {
    return state.selectedAddress === null
        ? fallbackSelection(state.generic) : selectedDevice(state)
}

function contactDecision(state, trigger) {
    if (state.helperPhase !== "ready")
        return { ok: false, reason: "helper_unavailable" }
    if (state.pending !== null)
        return { ok: false, reason: "busy" }
    if (!state.generic.adapterPresent)
        return { ok: false, reason: "no_adapter" }
    if (!state.generic.adapterEnabled)
        return { ok: false, reason: "adapter_off" }

    if (state.selectedAddress !== null) {
        var persisted = selectedDevice(state)
        if (!persisted)
            return { ok: false, reason: "selected_unavailable" }
        if (!persisted.connected)
            return { ok: false, reason: "selected_disconnected" }
        return {
            ok: true,
            address: persisted.address,
            selectOnSuccess: false
        }
    }

    var candidates = candidateRows(state.generic)
    if (candidates.length === 0)
        return { ok: false, reason: "no_candidate" }
    if (candidates.length === 1) {
        if (!candidates[0].connected)
            return { ok: false, reason: "candidate_disconnected" }
        return {
            ok: true,
            address: candidates[0].address,
            selectOnSuccess: true
        }
    }
    if (trigger === "panel")
        return { ok: false, reason: "multiple_candidates" }
    if (!isCanonicalAddress(state.markedAddress))
        return { ok: false, reason: "multiple_candidates" }
    for (var i = 0; i < candidates.length; i++) {
        if (candidates[i].address === state.markedAddress) {
            if (!candidates[i].connected)
                return { ok: false, reason: "candidate_disconnected" }
            return {
                ok: true,
                address: candidates[i].address,
                selectOnSuccess: true
            }
        }
    }
    return { ok: false, reason: "multiple_candidates" }
}

function isTopologyStatusCode(code) {
    return [
        "no_adapter",
        "adapter_off",
        "no_candidate",
        "candidate_disconnected",
        "multiple_candidates",
        "selected_unavailable",
        "selected_disconnected"
    ].indexOf(code) !== -1
}

function reduceGeneric(state, snapshot) {
    var next = copyState(state)
    var previousGeneric = state.generic
    var generic = normalizeGeneric(snapshot)
    var oldSelected = deviceForAddress(previousGeneric, state.selectedAddress)
    var newSelected = deviceForAddress(generic, state.selectedAddress)
    var pendingAddress = state.pending && state.pending.address ? state.pending.address : null
    var oldPending = state.pending && state.pending.selectOnSuccess
        ? candidateForAddress(previousGeneric, pendingAddress)
        : deviceForAddress(previousGeneric, pendingAddress)
    var newPending = state.pending && state.pending.selectOnSuccess
        ? candidateForAddress(generic, pendingAddress)
        : deviceForAddress(generic, pendingAddress)
    var adapterLost = previousGeneric.adapterPresent && !generic.adapterPresent
    var adapterPoweredOff = previousGeneric.adapterPresent
        && previousGeneric.adapterEnabled
        && generic.adapterPresent
        && !generic.adapterEnabled
    var disconnected = oldSelected && oldSelected.connected && (!newSelected || !newSelected.connected)
    var pendingInvalidated = oldPending && oldPending.connected
        && (!newPending || !newPending.connected)
    var invalidates = adapterLost || adapterPoweredOff || disconnected || pendingInvalidated

    next.generic = generic
    if (isTopologyStatusCode(next.lastCode))
        next.lastCode = null
    if (next.markedAddress !== null) {
        var candidates = candidateRows(generic)
        var markedStillPresent = false
        for (var i = 0; i < candidates.length; i++) {
            if (candidates[i].address === next.markedAddress) {
                markedStillPresent = true
                break
            }
        }
        if (!markedStillPresent)
            next.markedAddress = null
    }

    if (invalidates) {
        next.generation += 1
        next.pending = state.pending && state.pending.method === "clear_selection"
            ? state.pending : null
        next.privateState = emptyPrivateState()
        next.lastCode = disconnected ? (newSelected ? "selected_disconnected" : "selected_unavailable")
            : pendingInvalidated && state.selectedAddress === null
                ? (newPending ? "candidate_disconnected" : "no_candidate")
            : (!generic.adapterPresent ? "no_adapter" : "adapter_off")
    } else if (!generic.adapterPresent || !generic.adapterEnabled
               || (newSelected && !newSelected.connected)) {
        next.privateState = emptyPrivateState()
    }
    return next
}

function ageObservation(value, nowMs) {
    if (!value)
        return null
    if (!isFiniteNumber(nowMs) || !isFiniteNumber(value.receivedAtMs))
        return null
    var previousAge = isFiniteNumber(value.ageSeconds) && value.ageSeconds >= 0
        ? value.ageSeconds : 0
    var lastAgedAtMs = isFiniteNumber(value.lastAgedAtMs)
        ? value.lastAgedAtMs : value.receivedAtMs + previousAge * 1000
    if (!isFiniteNumber(lastAgedAtMs) || nowMs < lastAgedAtMs)
        return null
    var elapsed = Math.max(0, (nowMs - value.receivedAtMs) / 1000)
    var age = Math.max(previousAge, elapsed)
    if (age > EXPIRE_SECONDS)
        return null
    var next = {}
    var keys = Object.keys(value)
    for (var i = 0; i < keys.length; i++)
        next[keys[i]] = value[keys[i]]
    next.ageSeconds = age
    next.lastAgedAtMs = nowMs
    return next
}

function observationClockRolledBack(value, nowMs) {
    if (!value)
        return false
    if (!isFiniteNumber(nowMs) || !isFiniteNumber(value.receivedAtMs))
        return true
    var previousAge = isFiniteNumber(value.ageSeconds) && value.ageSeconds >= 0
        ? value.ageSeconds : 0
    var lastAgedAtMs = isFiniteNumber(value.lastAgedAtMs)
        ? value.lastAgedAtMs : value.receivedAtMs + previousAge * 1000
    return !isFiniteNumber(lastAgedAtMs) || nowMs < lastAgedAtMs
}

function observationFreshness(value) {
    if (!value)
        return "missing"
    if (!isFiniteNumber(value.ageSeconds) || value.ageSeconds < 0)
        return "missing"
    if (Math.floor(value.ageSeconds) <= FRESH_SECONDS)
        return "fresh"
    if (value.ageSeconds <= EXPIRE_SECONDS)
        return "stale"
    return "expired"
}

function reduce(state, event) {
    if (!isPlainObject(state) || !isPlainObject(event) || typeof event.type !== "string")
        return state

    if (event.type === "generic")
        return reduceGeneric(state, event.snapshot)

    var next = copyState(state)

    if (event.type === "helper_start") {
        next.generation += 1
        next.helperPhase = "starting"
        next.helperError = null
        next.pending = null
        next.privateState = emptyPrivateState()
        next.lastCode = null
        return next
    }

    if (event.type === "hello") {
        var hello = validateHello(event.message)
        if (!hello.ok)
            return state
        next.helperPhase = "ready"
        next.helperError = null
        next.selectionLoaded = true
        if (next.selectedAddress !== hello.selectedAddress) {
            next.generation += 1
            next.selectedAddress = hello.selectedAddress
            next.markedAddress = null
            next.pending = null
            next.privateState = emptyPrivateState()
        }
        next.configInvalid = false
        next.lastCode = null
        return next
    }

    if (event.type === "startup_error") {
        if (event.code !== "config_invalid")
            return state
        if (next.selectedAddress !== null)
            next.generation += 1
        next.selectionLoaded = true
        next.selectedAddress = null
        next.markedAddress = null
        next.pending = null
        next.privateState = emptyPrivateState()
        next.configInvalid = true
        next.lastCode = "config_invalid"
        return next
    }

    if (event.type === "helper_failed") {
        next.generation += 1
        next.helperPhase = "failed"
        next.helperError = typeof event.code === "string" ? event.code : "helper_stopped"
        next.pending = null
        next.privateState = emptyPrivateState()
        next.lastCode = next.helperError
        return next
    }

    if (event.type === "mark_candidate") {
        if (next.pending !== null)
            return state
        var candidates = candidateRows(next.generic)
        for (var c = 0; c < candidates.length; c++) {
            if (candidates[c].address === event.address) {
                next.markedAddress = event.address
                next.lastCode = null
                return next
            }
        }
        return state
    }

    if (event.type === "request_started") {
        if (next.pending !== null || !isPlainObject(event.pending))
            return state
        next.pending = event.pending
        next.lastCode = null
        if (event.pending.method === "refresh") {
            next.privateState = emptyPrivateState()
        } else if (event.pending.method === "set_anc") {
            var privateCopy = {
                verified: next.privateState.verified,
                address: next.privateState.address,
                generation: next.privateState.generation,
                battery: next.privateState.battery,
                anc: null,
                batteryError: next.privateState.batteryError,
                ancError: null
            }
            next.privateState = privateCopy
        }
        return next
    }

    if (event.type === "request_rejected") {
        next.lastCode = typeof event.code === "string" ? event.code : "invalid_request"
        return next
    }

    if (event.type === "age") {
        if (observationClockRolledBack(next.privateState.battery, event.nowMs)
                || observationClockRolledBack(next.privateState.anc, event.nowMs)) {
            next.privateState = emptyPrivateState()
            next.lastCode = "private_expired"
            return next
        }
        var agedBattery = ageObservation(next.privateState.battery, event.nowMs)
        var agedAnc = ageObservation(next.privateState.anc, event.nowMs)
        var batteryExpired = next.privateState.battery !== null && agedBattery === null
        var ancExpired = next.privateState.anc !== null && agedAnc === null
        next.privateState = {
            verified: next.privateState.verified && (agedBattery !== null || agedAnc !== null),
            address: agedBattery || agedAnc ? next.privateState.address : null,
            generation: agedBattery || agedAnc ? next.privateState.generation : null,
            battery: agedBattery,
            anc: agedAnc,
            batteryError: agedBattery || agedAnc ? next.privateState.batteryError : null,
            ancError: agedBattery || agedAnc ? next.privateState.ancError : null
        }
        if (batteryExpired || ancExpired)
            next.lastCode = "private_expired"
        return next
    }

    if (event.type === "clear_error") {
        next.lastCode = null
        return next
    }

    return state
}

function pendingMatchesCurrentState(state, pending) {
    if (!pending || state.helperPhase !== "ready")
        return false
    if (pending.method === "clear_selection")
        return true
    if (pending.generation !== state.generation)
        return false
    if (pending.method === "shutdown")
        return true
    if (!state.generic.adapterPresent || !state.generic.adapterEnabled)
        return false
    var device = deviceForAddress(state.generic, pending.address)
    if (!device || !device.connected)
        return false
    if (pending.selectOnSuccess === true)
        return state.selectedAddress === null
            && candidateForAddress(state.generic, pending.address) !== null
    return state.selectedAddress === pending.address
}

function applyValidatedResponse(state, result, nowMs) {
    var next = copyState(state)
    var pending = state.pending
    next.pending = null

    if (result.kind === "error") {
        next.lastCode = pending.method === "refresh"
                && (result.code === "battery_invalid" || result.code === "anc_invalid")
            ? "capabilities_unverified" : result.code
        if (pending.method === "refresh"
                || result.code === "identity_mismatch"
                || result.code === "identity_conflict") {
            next.privateState = emptyPrivateState()
        } else if (pending.method === "set_anc") {
            var observed = result.code === "anc_readback_mismatch"
                ? observation(result.address, next.generation, nowMs, { mode: result.observedAnc })
                : null
            next.privateState = observed === null ? emptyPrivateState() : {
                verified: true,
                address: result.address,
                generation: next.generation,
                battery: null,
                anc: observed,
                batteryError: null,
                ancError: result.code
            }
        }
        return next
    }

    if (result.method === "clear_selection") {
        if (next.selectedAddress !== null)
            next.generation += 1
        next.selectedAddress = null
        next.markedAddress = null
        next.configInvalid = false
        next.privateState = emptyPrivateState()
        next.lastCode = null
        return next
    }

    if (result.method === "shutdown")
        return next

    if (result.method === "refresh") {
        if (pending.selectOnSuccess === true && next.selectedAddress !== result.selectedAddress) {
            next.generation += 1
            next.selectedAddress = result.selectedAddress
            next.markedAddress = null
        }
        next.configInvalid = false
        next.privateState = {
            verified: true,
            address: result.address,
            generation: next.generation,
            battery: result.battery === null ? null
                : observation(result.address, next.generation, nowMs, result.battery),
            anc: result.anc === null ? null
                : observation(result.address, next.generation, nowMs, { mode: result.anc }),
            batteryError: result.batteryError,
            ancError: result.ancError
        }
        next.lastCode = null
        return next
    }

    if (result.method === "set_anc") {
        next.privateState = {
            verified: true,
            address: result.address,
            generation: next.generation,
            battery: next.privateState.battery,
            anc: observation(result.address, next.generation, nowMs, { mode: result.anc }),
            batteryError: next.privateState.batteryError,
            ancError: null
        }
        next.lastCode = null
        return next
    }

    return state
}

function applyBridgeMessage(state, message, nowMs) {
    if (!state.pending)
        return state
    var result = validateResponse(message, state.pending)
    if (!result.ok || !pendingMatchesCurrentState(state, state.pending))
        return state
    return applyValidatedResponse(state, result, nowMs)
}

function privateStateCurrent(state) {
    return state.privateState.verified
        && state.privateState.address === state.selectedAddress
        && state.privateState.generation === state.generation
}

function ancCapability(state) {
    if (state.pending
            && state.pending.method === "set_anc"
            && privateStateCurrent(state)) {
        return { visible: true, enabled: false, mode: null, freshness: "missing" }
    }
    if (!privateStateCurrent(state) || !state.privateState.anc)
        return { visible: false, enabled: false, mode: null, freshness: "missing" }
    var freshness = observationFreshness(state.privateState.anc)
    var selected = selectedDevice(state)
    return {
        visible: freshness === "fresh" || freshness === "stale",
        enabled: freshness === "fresh"
            && state.helperPhase === "ready"
            && state.pending === null
            && state.generic.adapterPresent
            && state.generic.adapterEnabled
            && selected !== null
            && selected.connected,
        mode: state.privateState.anc.mode,
        freshness: freshness
    }
}

function ageLabel(observationValue) {
    if (!observationValue || !isFiniteNumber(observationValue.ageSeconds))
        return "Not reported"
    var seconds = Math.max(0, Math.floor(observationValue.ageSeconds))
    if (seconds < 5)
        return "Reported just now"
    if (seconds < 60)
        return "Last reported " + seconds + " seconds ago"
    var minutes = Math.floor(seconds / 60)
    return "Last reported " + minutes + (minutes === 1 ? " minute ago" : " minutes ago")
}

function errorMessage(code) {
    return typeof code === "string" && hasOwn(USER_MESSAGES, code)
        ? USER_MESSAGES[code]
        : "Private controls unavailable"
}

function connectionText(state) {
    if (!state.generic.adapterPresent)
        return "No Bluetooth adapter"
    if (!state.generic.adapterEnabled)
        return "Bluetooth is off"
    if (state.selectedAddress === null)
        return fallbackSelection(state.generic) ? "Connected" : "No earbuds selected"
    var device = selectedDevice(state)
    if (!device)
        return "Selected earbuds are not available"
    return device.connected ? "Connected" : "Disconnected"
}

function primaryAction(state, batteryFreshness, ancFreshness) {
    if (state.pending !== null)
        return { kind: "none", label: "", enabled: false }
    if (state.helperPhase === "failed")
        return { kind: "retry", label: "Retry", enabled: true }
    if (!state.generic.adapterPresent || !state.generic.adapterEnabled)
        return { kind: "none", label: "", enabled: false }
    if (state.selectedAddress !== null) {
        var selected = selectedDevice(state)
        if (!selected)
            return { kind: "choose", label: "Choose another device", enabled: state.helperPhase === "ready" }
        if (!selected.connected)
            return { kind: "choose", label: "Choose another device", enabled: state.helperPhase === "ready" }
        if (state.lastCode === "identity_mismatch" || state.lastCode === "identity_conflict")
            return { kind: "choose", label: "Choose another device", enabled: state.helperPhase === "ready" }
        var current = privateStateCurrent(state)
        if (!current)
            return { kind: "retry", label: "Retry", enabled: state.helperPhase === "ready" }
        var featureFailed = current
            && ((state.privateState.battery === null && state.privateState.batteryError !== null)
                || (state.privateState.anc === null && state.privateState.ancError !== null))
        if (state.lastCode !== null || featureFailed
                || batteryFreshness === "stale" || ancFreshness === "stale")
            return { kind: "retry", label: "Retry", enabled: state.helperPhase === "ready" }
        return { kind: "choose", label: "Choose another device", enabled: state.helperPhase === "ready" }
    }

    var decision = contactDecision(state, "retry")
    if (decision.ok)
        return { kind: "retry", label: "Retry", enabled: true }
    if (decision.reason === "multiple_candidates") {
        return {
            kind: "retry",
            label: "Retry",
            enabled: isCanonicalAddress(state.markedAddress) && state.helperPhase === "ready"
        }
    }
    return { kind: "none", label: "", enabled: false }
}

function unselectedBlockingTopologyCode(state) {
    var candidates = candidateRows(state.generic)
    if (candidates.length === 0)
        return "no_candidate"
    var marked = candidateForAddress(state.generic, state.markedAddress)
    if ((marked && !marked.connected)
            || (candidates.length === 1 && !candidates[0].connected)) {
        return "candidate_disconnected"
    }
    return null
}

function statusCode(state, batteryFreshness, ancFreshness) {
    if (state.helperPhase === "waiting" || state.helperPhase === "starting")
        return "service_starting"
    if (state.helperPhase === "failed")
        return state.helperError || "helper_stopped"
    if (!state.generic.adapterPresent)
        return "no_adapter"
    if (!state.generic.adapterEnabled)
        return "adapter_off"
    if (state.pending !== null)
        return null
    var unselectedTopology = state.selectedAddress === null
        ? unselectedBlockingTopologyCode(state) : null
    if (unselectedTopology !== null && state.lastCode !== "config_invalid")
        return unselectedTopology
    if (state.lastCode !== null)
        return state.lastCode
    if (state.configInvalid)
        return "config_invalid"
    if (batteryFreshness === "stale")
        return "battery_stale"
    if (ancFreshness === "stale")
        return "anc_stale"
    if (privateStateCurrent(state)) {
        if (state.privateState.battery === null && state.privateState.batteryError !== null)
            return state.privateState.batteryError
        if (state.privateState.anc === null && state.privateState.ancError !== null)
            return state.privateState.ancError
    }
    if (state.selectedAddress !== null) {
        var selected = selectedDevice(state)
        if (!selected)
            return "selected_unavailable"
        if (!selected.connected)
            return "selected_disconnected"
        return null
    }

    return unselectedTopology || "multiple_candidates"
}

function deriveView(state) {
    var selected = selectedDevice(state)
    var displayed = displayDevice(state)
    var aggregate = state.generic.adapterPresent && state.generic.adapterEnabled
        ? genericBatteryPercent(displayed) : null
    var current = privateStateCurrent(state)
    var battery = current ? state.privateState.battery : null
    var anc = current ? state.privateState.anc : null
    var batteryFreshness = observationFreshness(battery)
    var ancFreshness = observationFreshness(anc)
    var splitBatteryFresh = batteryFreshness === "fresh"
        && isPercent(battery.left) && isPercent(battery.right)
    var showAggregateBattery = battery === null
    var barBatteryPercent = splitBatteryFresh ? Math.min(battery.left, battery.right)
        : showAggregateBattery ? aggregate : null
    var capability = ancCapability(state)
    var barAncMode = capability.freshness === "fresh" && isAncMode(capability.mode)
        ? capability.mode : ""
    var barAncText = barAncMode === "off" ? "OFF"
        : barAncMode === "anc" ? "ANC"
        : barAncMode === "awareness" ? "AWR" : ""
    var barAncSpoken = barAncMode === "off" ? "off"
        : barAncMode === "anc" ? "noise cancellation"
        : barAncMode === "awareness" ? "awareness" : ""
    var code = statusCode(state, batteryFreshness, ancFreshness)
    var action = primaryAction(state, batteryFreshness, ancFreshness)
    var connection = connectionText(state)
    var barName = "FreeBuds Pro 5, " + connection.toLowerCase()
    if (splitBatteryFresh)
        barName += ", lowest earbud " + barBatteryPercent + " percent"
    else if (barBatteryPercent !== null)
        barName += ", earbuds " + barBatteryPercent + " percent"
    if (barAncSpoken !== "")
        barName += ", noise control " + barAncSpoken
    if (state.helperPhase === "failed")
        barName += ", private controls unavailable"

    var rows = []
    if (battery) {
        rows = [
            { key: "left", label: "Left", value: battery.left, text: formatPercent(battery.left) },
            { key: "right", label: "Right", value: battery.right, text: formatPercent(battery.right) },
            { key: "case", label: "Case", value: battery.case, text: formatPercent(battery.case) }
        ]
    }

    var message = code === null ? "" : errorMessage(code)
    if (state.pending !== null) {
        message = state.lastCode === "busy" ? errorMessage("busy")
            : state.pending.method === "set_anc" ? "Changing noise control"
            : state.pending.method === "clear_selection" ? "Clearing device selection"
            : "Refreshing private status"
    }

    return {
        generic: state.generic,
        candidates: candidateRows(state.generic),
        selectedDevice: displayed,
        selectedAddress: state.selectedAddress,
        markedAddress: state.markedAddress,
        helperPhase: state.helperPhase,
        pending: state.pending !== null,
        pendingMethod: state.pending ? state.pending.method : "",
        connected: state.generic.adapterPresent && state.generic.adapterEnabled
            && displayed !== null && displayed.connected,
        connectionText: connection,
        aggregatePercent: aggregate,
        aggregateText: aggregate === null ? "Not reported" : aggregate + "%",
        showAggregateBattery: showAggregateBattery,
        batteryRows: rows,
        batteryFreshness: batteryFreshness,
        privateAgeText: ageLabel(battery || anc),
        ancVisible: capability.visible,
        ancEnabled: capability.enabled,
        ancMode: capability.mode,
        ancFreshness: capability.freshness,
        message: message,
        messageCode: code,
        primaryAction: action.kind,
        primaryActionLabel: action.label,
        primaryActionEnabled: action.enabled,
        barPercentText: barBatteryPercent === null ? "" : barBatteryPercent + "%",
        barAncMode: barAncMode,
        barAncText: barAncText,
        barAccessibleName: barName,
        barTooltip: "FreeBuds Pro 5: " + connection
            + (splitBatteryFresh ? "; Lowest earbud " + barBatteryPercent + "%"
                : barBatteryPercent === null ? "" : "; Earbuds " + barBatteryPercent + "%")
            + (barAncText === "" ? "" : "; Noise control: " + barAncText)
    }
}

function shouldStackInfoRow(rowWidth, labelWidth, valueWidth, spacing) {
    if (!isFiniteNumber(rowWidth) || rowWidth < 0
            || !isFiniteNumber(labelWidth) || labelWidth < 0
            || !isFiniteNumber(valueWidth) || valueWidth < 0
            || !isFiniteNumber(spacing) || spacing < 0) {
        return true
    }
    return labelWidth + valueWidth + spacing > rowWidth
}

function candidateAccessibleDescription(hasService, pending, connected) {
    if (!hasService)
        return "Private controls unavailable"
    if (pending)
        return "Wait for the current private request to finish"
    return connected
        ? "Select this connected candidate, then activate Retry"
        : "Select this candidate; connect it in Omarchy Bluetooth before Retry"
}
