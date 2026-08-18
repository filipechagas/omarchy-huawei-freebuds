import QtQuick
import QtTest
import "../../Model.js" as Model

TestCase {
    name: "FreeBudsModel"

    readonly property string addressA: "AA:BB:CC:DD:EE:01"
    readonly property string addressB: "AA:BB:CC:DD:EE:02"

    function device(address, values) {
        var result = {
            address: address,
            deviceName: Model.TARGET_DEVICE_NAME,
            name: Model.TARGET_DEVICE_NAME,
            paired: true,
            bonded: true,
            connected: true,
            batteryAvailable: true,
            battery: 0.68
        }
        var source = values || {}
        var keys = Object.keys(source)
        for (var i = 0; i < keys.length; i++)
            result[keys[i]] = source[keys[i]]
        return result
    }

    function generic(devices, adapterPresent, adapterEnabled) {
        return {
            adapterPresent: adapterPresent === undefined ? true : adapterPresent,
            adapterEnabled: adapterEnabled === undefined ? true : adapterEnabled,
            devices: devices || []
        }
    }

    function clone(value) {
        return JSON.parse(JSON.stringify(value))
    }

    function readyState(selectedAddress, devices) {
        var state = Model.initialState()
        state = Model.reduce(state, { type: "generic", snapshot: generic(devices) })
        state = Model.reduce(state, { type: "helper_start" })
        state = Model.reduce(state, {
            type: "hello",
            message: {
                v: 1,
                type: "hello",
                bridgeVersion: "0.1.0",
                selectedAddress: selectedAddress
            }
        })
        return state
    }

    function pending(state, method, address, selectOnSuccess) {
        return {
            id: 7,
            generation: state.generation,
            method: method,
            address: address,
            selectOnSuccess: selectOnSuccess === true
        }
    }

    function refreshResult(state, address, values) {
        var result = {
            v: 1,
            type: "result",
            id: 7,
            generation: state.generation,
            address: address,
            verified: true,
            selectedAddress: address,
            left: 72,
            right: 68,
            case: 54,
            anc: "anc",
            batteryError: null,
            ancError: null
        }
        var source = values || {}
        var keys = Object.keys(source)
        for (var i = 0; i < keys.length; i++)
            result[keys[i]] = source[keys[i]]
        return result
    }

    function withPrivateState(selectedAddress, devices, resultValues) {
        var state = readyState(selectedAddress, devices)
        var request = pending(state, "refresh", selectedAddress, false)
        state = Model.reduce(state, { type: "request_started", pending: request })
        state = Model.applyBridgeMessage(state, refreshResult(state, selectedAddress, resultValues), 1000)
        return state
    }

    function test_genericSnapshotsAreDefensive() {
        var nullSnapshot = Model.normalizeGeneric(null)
        compare(nullSnapshot.adapterPresent, false)
        compare(nullSnapshot.adapterEnabled, false)
        compare(nullSnapshot.devices.length, 0)

        var sparse = Model.normalizeGeneric({ adapterPresent: true, devices: [{}] })
        compare(sparse.adapterPresent, true)
        compare(sparse.adapterEnabled, false)
        compare(sparse.devices.length, 1)
        compare(sparse.devices[0].connected, false)
        compare(sparse.devices[0].battery, null)

        var malformed = Model.normalizeGeneric({
            adapterPresent: "yes",
            adapterEnabled: 1,
            devices: "not-an-array"
        })
        compare(malformed.adapterPresent, false)
        compare(malformed.adapterEnabled, false)
        compare(malformed.devices.length, 0)
    }

    function test_candidatesRequireImmutableExactNameAndPairing() {
        var aliasOnly = device(addressA, {
            deviceName: "Some headphones",
            name: Model.TARGET_DEVICE_NAME
        })
        var wrongCase = device(addressB, { deviceName: "Huawei FreeBuds Pro 5" })
        var unpaired = device("AA:BB:CC:DD:EE:03", { paired: false })
        var unbonded = device("AA:BB:CC:DD:EE:04", { bonded: false })
        var invalidAddress = device("not-an-address")
        var exact = device("AA:BB:CC:DD:EE:05", { name: "Office earbuds" })
        var rows = Model.candidateRows([aliasOnly, wrongCase, unpaired, unbonded, invalidAddress, exact])

        compare(rows.length, 1)
        compare(rows[0].address, "AA:BB:CC:DD:EE:05")
        compare(rows[0].displayLabel, "Office earbuds")
    }

    function test_candidatesAreDeterministicAndAliasesAreBounded() {
        var controlName = "  Desk\nEarbuds\u0000  "
        var rows = Model.candidateRows([
            device(addressB, { name: "Zulu" }),
            device(addressA, { name: controlName })
        ])
        compare(rows.length, 2)
        compare(rows[0].address, addressA)
        compare(rows[0].displayLabel, "Desk Earbuds")
        compare(rows[1].address, addressB)

        var redacted = Model.candidateRows([
            device("AA:BB:CC:DD:EE:03", { name: "Desk AA:BB:CC:DD:EE:03" })
        ])
        compare(redacted[0].displayLabel.indexOf("AA:BB:CC:DD:EE:03"), -1)
    }

    function test_candidateCardinalityAndContactDecision() {
        var state = readyState(null, [])
        compare(Model.contactDecision(state).reason, "no_candidate")

        state = Model.reduce(state, { type: "generic", snapshot: generic([device(addressA)]) })
        var oneView = Model.deriveView(state)
        compare(oneView.connected, true)
        compare(oneView.selectedAddress, null)
        compare(oneView.selectedDevice.address, addressA)
        compare(oneView.aggregatePercent, 68)
        var panelDecision = Model.contactDecision(state, "panel")
        verify(panelDecision.ok)
        compare(panelDecision.address, addressA)
        compare(panelDecision.selectOnSuccess, true)
        verify(Model.contactDecision(state, "retry").ok)

        var marked = Model.reduce(state, { type: "mark_candidate", address: addressA })
        var one = Model.contactDecision(marked, "retry")
        verify(one.ok)
        compare(one.address, addressA)
        compare(one.selectOnSuccess, true)
        verify(Model.contactDecision(marked, "panel").ok)

        state = readyState(null, [device(addressA), device(addressB)])
        compare(Model.contactDecision(state).reason, "multiple_candidates")

        marked = Model.reduce(state, { type: "mark_candidate", address: addressB })
        compare(marked.pending, null)
        compare(marked.markedAddress, addressB)
        compare(Model.contactDecision(marked).address, addressB)
        compare(Model.contactDecision(marked, "panel").ok, false)
        compare(Model.contactDecision(marked, "panel").reason, "multiple_candidates")
        compare(Model.contactDecision(marked, "retry").address, addressB)

        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA), device(addressB, { connected: false })])
        })
        marked = Model.reduce(state, { type: "mark_candidate", address: addressB })
        compare(Model.deriveView(marked).message, "Connect the earbuds in Omarchy Bluetooth")
    }

    function test_disconnectedCandidateNeverBecomesEligible() {
        var state = readyState(null, [device(addressA, { connected: false })])
        compare(Model.contactDecision(state, "panel").reason, "candidate_disconnected")
        compare(Model.contactDecision(state, "retry").reason, "candidate_disconnected")
        state = Model.reduce(state, { type: "mark_candidate", address: addressA })
        var decision = Model.contactDecision(state, "retry")
        compare(decision.ok, false)
        compare(decision.reason, "candidate_disconnected")
    }

    function test_genericBatteryValidation() {
        compare(Model.genericBatteryPercent(device(addressA, { battery: 0 })), 0)
        compare(Model.genericBatteryPercent(device(addressA, { battery: 1 })), 100)
        compare(Model.genericBatteryPercent(device(addressA, { battery: 0.675 })), 68)
        compare(Model.genericBatteryPercent(device(addressA, { batteryAvailable: false })), null)
        compare(Model.genericBatteryPercent(device(addressA, { connected: false })), null)
        compare(Model.genericBatteryPercent(device(addressA, { battery: -0.01 })), null)
        compare(Model.genericBatteryPercent(device(addressA, { battery: 1.01 })), null)
        compare(Model.genericBatteryPercent(device(addressA, { battery: NaN })), null)
        compare(Model.genericBatteryPercent(device(addressA, { battery: Infinity })), null)
    }

    function test_serviceNullFallbackRequiresOneConnectedCandidate() {
        var one = Model.fallbackView(generic([device(addressA, { battery: 0 })]))
        compare(one.connected, true)
        compare(one.aggregatePercent, 0)
        compare(one.barPercentText, "0%")

        var disconnected = Model.fallbackView(generic([device(addressA, { connected: false })]))
        compare(disconnected.selectedDevice, null)
        compare(disconnected.aggregatePercent, null)

        var ambiguous = Model.fallbackView(generic([device(addressA), device(addressB)]))
        compare(ambiguous.connected, false)
        compare(ambiguous.selectedDevice, null)
        compare(ambiguous.barPercentText, "")

        var adapterOff = Model.fallbackView(generic([device(addressA)], true, false))
        compare(adapterOff.aggregatePercent, null)
        compare(adapterOff.connected, false)
    }

    function test_jsonLineParserRejectsMalformedDuplicateAndOversizedInput() {
        compare(Model.parseJsonLine("").ok, false)
        compare(Model.parseJsonLine("[]").ok, false)
        compare(Model.parseJsonLine("{bad json}").ok, false)
        compare(Model.parseJsonLine('{"v":1,"v":1}').ok, false)
        compare(Model.parseJsonLine('{"a":1,"\\u0061":2}').ok, false)
        compare(Model.parseJsonLine('{"__proto__":{}}').ok, false)
        compare(Model.parseJsonLine('{"v":NaN}').ok, false)

        var envelope = '{"value":""}'
        var boundary = '{"value":"'
            + "x".repeat(Model.MAX_JSONL_BYTES - Model.utf8Length(envelope) - 1)
            + '"}'
        compare(Model.utf8Length(boundary) + 1, Model.MAX_JSONL_BYTES)
        verify(Model.parseJsonLine(boundary).ok)

        var newlineExcluded = boundary.replace('"}', 'x"}')
        compare(Model.utf8Length(newlineExcluded), Model.MAX_JSONL_BYTES)
        compare(Model.parseJsonLine(newlineExcluded).ok, false)

        var valid = Model.parseJsonLine('{"v":1,"type":"hello"}')
        verify(valid.ok)
        compare(valid.value.v, 1)
    }

    function test_helloValidationIsExact() {
        var hello = {
            v: 1,
            type: "hello",
            bridgeVersion: "0.1.0",
            selectedAddress: addressA
        }
        verify(Model.validateHello(hello).ok)

        var delayed = clone(hello)
        delayed.selectedAddress = null
        verify(Model.validateHello(delayed).ok)

        var wrongVersion = clone(hello)
        wrongVersion.v = 2
        compare(Model.validateHello(wrongVersion).ok, false)

        var wrongBridge = clone(hello)
        wrongBridge.bridgeVersion = "0.2.0"
        compare(Model.validateHello(wrongBridge).ok, false)

        var unknown = clone(hello)
        unknown.extra = true
        compare(Model.validateHello(unknown).ok, false)

        var badAddress = clone(hello)
        badAddress.selectedAddress = "aa:bb:cc:dd:ee:ff"
        compare(Model.validateHello(badAddress).ok, false)
    }

    function test_startupConfigErrorIsNarrowAndNonfatal() {
        var message = { v: 1, type: "error", code: "config_invalid" }
        verify(Model.validateStartupError(message).ok)

        var unknown = clone(message)
        unknown.message = "raw backend payload"
        compare(Model.validateStartupError(unknown).ok, false)

        var state = readyState(null, [device(addressA)])
        state = Model.reduce(state, { type: "startup_error", code: "config_invalid" })
        compare(state.helperPhase, "ready")
        compare(state.configInvalid, true)
        compare(state.selectedAddress, null)
        compare(Model.deriveView(state).message, "Saved device selection is invalid")
    }

    function test_refreshResultSupportsFeatureLevelPartialSuccess() {
        var state = readyState(addressA, [device(addressA)])
        var request = pending(state, "refresh", addressA, false)

        var full = refreshResult(state, addressA)
        verify(Model.validateResponse(full, request).ok)

        var batteryOnly = refreshResult(state, addressA, {
            anc: null,
            ancError: "anc_invalid"
        })
        var batteryValidation = Model.validateResponse(batteryOnly, request)
        verify(batteryValidation.ok)
        compare(batteryValidation.anc, null)

        var ancOnly = refreshResult(state, addressA, {
            left: null,
            right: null,
            case: null,
            batteryError: "battery_invalid"
        })
        var ancValidation = Model.validateResponse(ancOnly, request)
        verify(ancValidation.ok)
        compare(ancValidation.battery, null)

        var noShape = clone(ancOnly)
        noShape.anc = null
        noShape.ancError = "anc_invalid"
        compare(Model.validateResponse(noShape, request).ok, false)
    }

    function test_privatePercentagesFailClosed() {
        var state = readyState(addressA, [device(addressA)])
        var request = pending(state, "refresh", addressA, false)
        var invalid = [undefined, -1, 1.5, 101, "72"]
        for (var i = 0; i < invalid.length; i++) {
            var message = refreshResult(state, addressA)
            if (invalid[i] === undefined)
                delete message.left
            else
                message.left = invalid[i]
            compare(Model.validateResponse(message, request).ok, false)
        }

        var partialComponents = refreshResult(state, addressA, {
            left: 0,
            right: null,
            case: 54,
            batteryError: null
        })
        compare(Model.validateResponse(partialComponents, request).ok, false)

        var zero = refreshResult(state, addressA, { left: 0, right: 0, case: 0 })
        verify(Model.validateResponse(zero, request).ok)
    }

    function test_responseCorrelationRejectsWrongIdGenerationAndAddress() {
        var state = readyState(addressA, [device(addressA)])
        var request = pending(state, "refresh", addressA, false)
        state = Model.reduce(state, { type: "request_started", pending: request })
        var valid = refreshResult(state, addressA)

        var wrongId = clone(valid)
        wrongId.id = 8
        compare(Model.applyBridgeMessage(state, wrongId, 1000), state)

        var wrongGeneration = clone(valid)
        wrongGeneration.generation += 1
        compare(Model.applyBridgeMessage(state, wrongGeneration, 1000), state)

        var wrongAddress = clone(valid)
        wrongAddress.address = addressB
        wrongAddress.selectedAddress = addressB
        compare(Model.applyBridgeMessage(state, wrongAddress, 1000), state)

        compare(Model.classifyResponse(wrongId, state.pending).kind, "stale")
        var malformed = clone(valid)
        malformed.extra = true
        compare(Model.classifyResponse(malformed, state.pending).kind, "protocol_error")

        var wrongMethod = {
            v: 1,
            type: "result",
            id: 7,
            generation: state.generation,
            address: addressA,
            verified: true,
            anc: "anc"
        }
        compare(Model.classifyResponse(wrongMethod, state.pending).kind, "protocol_error")
    }

    function test_ancSuccessMustMatchRequestedMode() {
        var state = readyState(addressA, [device(addressA)])
        var request = pending(state, "set_anc", addressA, false)
        request.mode = "anc"
        state = Model.reduce(state, { type: "request_started", pending: request })
        var message = {
            v: 1,
            type: "result",
            id: 7,
            generation: state.generation,
            address: addressA,
            verified: true,
            anc: "awareness"
        }
        compare(Model.validateResponse(message, state.pending).ok, false)
        compare(Model.classifyResponse(message, state.pending).kind, "protocol_error")

        message.anc = "anc"
        verify(Model.validateResponse(message, state.pending).ok)
        state = Model.applyBridgeMessage(state, message, 1000)
        compare(state.privateState.anc.mode, "anc")
    }

    function test_clearSelectionCompletesAcrossGenericGenerationChange() {
        var state = withPrivateState(addressA, [device(addressA)])
        var request = pending(state, "clear_selection", null, false)
        state = Model.reduce(state, { type: "request_started", pending: request })
        var requestGeneration = request.generation

        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA)], true, false)
        })
        compare(state.generation, requestGeneration + 1)
        verify(state.pending !== null)

        var result = {
            v: 1,
            type: "result",
            id: 7,
            generation: requestGeneration,
            address: null,
            selectedAddress: null
        }
        state = Model.applyBridgeMessage(state, result, 1000)
        compare(state.pending, null)
        compare(state.selectedAddress, null)
        compare(state.privateState.verified, false)
    }

    function test_unpersistedCandidateDisconnectInvalidatesPendingResult() {
        var state = readyState(null, [device(addressA)])
        var request = pending(state, "refresh", addressA, true)
        state = Model.reduce(state, { type: "request_started", pending: request })
        var oldGeneration = state.generation

        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA, { connected: false })])
        })
        compare(state.generation, oldGeneration + 1)
        compare(state.pending, null)
        compare(state.lastCode, "candidate_disconnected")

        var late = refreshResult(state, addressA)
        late.generation = oldGeneration
        compare(Model.applyBridgeMessage(state, late, 1000), state)
    }

    function test_unpersistedFailureYieldsToBlockingCandidateTopology() {
        var state = readyState(null, [device(addressA)])
        var request = pending(state, "refresh", addressA, true)
        state = Model.reduce(state, { type: "request_started", pending: request })
        state = Model.applyBridgeMessage(state, {
            v: 1,
            type: "error",
            id: 7,
            generation: state.generation,
            address: addressA,
            code: "connect_failed",
            observedAnc: null
        }, 1000)
        compare(state.lastCode, "connect_failed")

        var disconnected = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA, { connected: false })])
        })
        compare(disconnected.lastCode, "connect_failed")
        compare(Model.deriveView(disconnected).messageCode, "candidate_disconnected")
        compare(Model.deriveView(disconnected).message,
                "Connect the earbuds in Omarchy Bluetooth")

        var missing = Model.reduce(state, {
            type: "generic",
            snapshot: generic([])
        })
        compare(missing.lastCode, "connect_failed")
        compare(Model.deriveView(missing).messageCode, "no_candidate")
        compare(Model.deriveView(missing).message,
                "Pair FreeBuds Pro 5 in Omarchy Bluetooth")
    }

    function test_refreshStartClearsOldPrivateData() {
        var state = withPrivateState(addressA, [device(addressA)])
        verify(state.privateState.battery !== null)
        verify(state.privateState.anc !== null)

        var request = pending(state, "refresh", addressA, false)
        state = Model.reduce(state, { type: "request_started", pending: request })
        compare(state.privateState.battery, null)
        compare(state.privateState.anc, null)
        compare(state.privateState.verified, false)

        state = Model.reduce(state, { type: "request_rejected", code: "busy" })
        compare(Model.deriveView(state).message, "Private request already in progress")
    }

    function test_noVerifiedFeatureMapsToCapabilitiesFailure() {
        var state = readyState(null, [device(addressA)])
        var request = pending(state, "refresh", addressA, true)
        state = Model.reduce(state, { type: "request_started", pending: request })
        var error = {
            v: 1,
            type: "error",
            id: 7,
            generation: state.generation,
            address: addressA,
            code: "anc_invalid",
            observedAnc: null
        }
        state = Model.applyBridgeMessage(state, error, 1000)
        compare(state.selectedAddress, null)
        compare(state.privateState.verified, false)
        compare(state.lastCode, "capabilities_unverified")
        compare(Model.deriveView(state).message, "Private capabilities not verified")
    }

    function test_ancStartClearsOnlyAncObservation() {
        var state = withPrivateState(addressA, [device(addressA)])
        var battery = state.privateState.battery
        var request = pending(state, "set_anc", addressA, false)
        state = Model.reduce(state, { type: "request_started", pending: request })
        compare(state.privateState.battery, battery)
        compare(state.privateState.anc, null)
    }

    function test_unpersistedSelectionCommitsOnlyOnVerifiedResult() {
        var state = readyState(null, [device(addressA)])
        var request = pending(state, "refresh", addressA, true)
        state = Model.reduce(state, { type: "request_started", pending: request })
        var oldGeneration = state.generation
        state = Model.applyBridgeMessage(state, refreshResult(state, addressA), 1000)

        compare(state.selectedAddress, addressA)
        compare(state.generation, oldGeneration + 1)
        compare(state.privateState.generation, state.generation)
        compare(state.privateState.address, addressA)
    }

    function test_disconnectAdapterLossHelperFailureAndSelectionChangeClearPrivate() {
        var connectedState = withPrivateState(addressA, [device(addressA)])

        var disconnected = Model.reduce(connectedState, {
            type: "generic",
            snapshot: generic([device(addressA, { connected: false })])
        })
        compare(disconnected.generation, connectedState.generation + 1)
        compare(disconnected.privateState.verified, false)
        compare(disconnected.selectedAddress, addressA)

        var unavailable = Model.reduce(connectedState, {
            type: "generic",
            snapshot: generic([])
        })
        compare(unavailable.lastCode, "selected_unavailable")
        compare(Model.deriveView(unavailable).primaryAction, "choose")

        var adapterLoss = Model.reduce(connectedState, {
            type: "generic",
            snapshot: generic([device(addressA)], false, false)
        })
        compare(adapterLoss.generation, connectedState.generation + 1)
        compare(adapterLoss.privateState.battery, null)
        compare(adapterLoss.selectedAddress, addressA)

        var disabled = Model.reduce(connectedState, {
            type: "generic",
            snapshot: generic([device(addressA)], true, false)
        })
        var removedAfterDisable = Model.reduce(disabled, {
            type: "generic",
            snapshot: generic([], false, false)
        })
        compare(removedAfterDisable.generation, disabled.generation + 1)

        var helperFailed = Model.reduce(connectedState, {
            type: "helper_failed",
            code: "helper_stopped"
        })
        compare(helperFailed.generation, connectedState.generation + 1)
        compare(helperFailed.privateState.anc, null)
        compare(helperFailed.selectedAddress, addressA)

        var restarted = Model.reduce(connectedState, { type: "helper_start" })
        restarted = Model.reduce(restarted, {
            type: "hello",
            message: {
                v: 1,
                type: "hello",
                bridgeVersion: "0.1.0",
                selectedAddress: addressB
            }
        })
        compare(restarted.selectedAddress, addressB)
        compare(restarted.privateState.verified, false)
    }

    function test_recoveredTopologyClearsObsoleteGuidance() {
        var state = withPrivateState(addressA, [device(addressA)])
        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA)], true, false)
        })
        compare(state.lastCode, "adapter_off")

        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA)])
        })
        compare(state.lastCode, null)
        compare(Model.deriveView(state).connectionText, "Connected")
        compare(Model.deriveView(state).message, "")
        compare(Model.deriveView(state).primaryAction, "retry")
        compare(Model.deriveView(state).primaryActionEnabled, true)

        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA, { connected: false })])
        })
        compare(state.lastCode, "selected_disconnected")
        state = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA)])
        })
        compare(state.lastCode, null)
        compare(Model.deriveView(state).connectionText, "Connected")
        compare(Model.deriveView(state).primaryAction, "retry")
        compare(Model.deriveView(state).primaryActionEnabled, true)
    }

    function test_connectedPersistedSelectionWithoutPrivateStateCanRetry() {
        var state = readyState(addressA, [device(addressA)])
        var view = Model.deriveView(state)
        compare(view.connected, true)
        compare(view.batteryRows.length, 0)
        compare(view.primaryAction, "retry")
        compare(view.primaryActionLabel, "Retry")
        compare(view.primaryActionEnabled, true)

        state = withPrivateState(addressA, [device(addressA)])
        view = Model.deriveView(state)
        compare(view.primaryAction, "choose")
    }

    function test_freshnessBoundariesAndBackwardClock() {
        var state = withPrivateState(addressA, [device(addressA)])
        state = Model.reduce(state, { type: "age", nowMs: 131000 })
        compare(state.privateState.battery.ageSeconds, 130)
        compare(Model.observationFreshness(state.privateState.battery), "fresh")

        state = Model.reduce(state, { type: "age", nowMs: 132000 })
        compare(state.privateState.battery.ageSeconds, 131)
        compare(Model.observationFreshness(state.privateState.battery), "stale")

        state = Model.reduce(state, { type: "age", nowMs: 601000 })
        compare(state.privateState.battery.ageSeconds, 600)
        compare(Model.observationFreshness(state.privateState.battery), "stale")

        state = Model.reduce(state, { type: "age", nowMs: 601001 })
        compare(state.privateState.battery, null)
        compare(state.privateState.anc, null)
        compare(state.privateState.verified, false)
        var expiredView = Model.deriveView(state)
        compare(expiredView.messageCode, "private_expired")
        compare(expiredView.message, "Not reported")
        compare(expiredView.primaryAction, "retry")
        compare(expiredView.primaryActionEnabled, true)

        var rolledBack = withPrivateState(addressA, [device(addressA)])
        rolledBack = Model.reduce(rolledBack, { type: "age", nowMs: 2000 })
        rolledBack = Model.reduce(rolledBack, { type: "age", nowMs: 1999 })
        compare(rolledBack.privateState.battery, null)
        compare(rolledBack.privateState.anc, null)
        compare(rolledBack.privateState.verified, false)
        compare(Model.deriveView(rolledBack).message, "Not reported")
    }

    function test_ancControlsRequireFreshCurrentCapability() {
        var state = withPrivateState(addressA, [device(addressA)])
        var capability = Model.ancCapability(state)
        compare(capability.visible, true)
        compare(capability.enabled, true)
        compare(capability.mode, "anc")

        var request = pending(state, "set_anc", addressA, false)
        var changing = Model.reduce(state, { type: "request_started", pending: request })
        capability = Model.ancCapability(changing)
        compare(capability.visible, true)
        compare(capability.enabled, false)
        compare(capability.mode, null)

        var stale = Model.reduce(state, { type: "age", nowMs: 132000 })
        capability = Model.ancCapability(stale)
        compare(capability.visible, true)
        compare(capability.enabled, false)

        var disconnected = Model.reduce(state, {
            type: "generic",
            snapshot: generic([device(addressA, { connected: false })])
        })
        compare(Model.ancCapability(disconnected).visible, false)

        var failed = Model.reduce(state, { type: "helper_failed", code: "helper_stopped" })
        compare(Model.ancCapability(failed).visible, false)
    }

    function test_batteryOnlyAndAncOnlyViewsStayCapabilityGated() {
        var batteryOnly = withPrivateState(addressA, [device(addressA)], {
            anc: null,
            ancError: "anc_invalid"
        })
        var view = Model.deriveView(batteryOnly)
        compare(view.batteryRows.length, 3)
        compare(view.ancVisible, false)
        compare(view.message, "Noise control not reported")
        compare(view.primaryAction, "retry")

        var ancOnly = withPrivateState(addressA, [device(addressA)], {
            left: null,
            right: null,
            case: null,
            batteryError: "battery_invalid"
        })
        view = Model.deriveView(ancOnly)
        compare(view.batteryRows.length, 0)
        compare(view.ancVisible, true)
        compare(view.message, "Battery components not reported")
        compare(view.primaryAction, "retry")
    }

    function test_privateBatteryNeverBecomesGenericAggregate() {
        var noGeneric = device(addressA, { batteryAvailable: false, battery: 0 })
        var state = withPrivateState(addressA, [noGeneric], {
            left: 100,
            right: 99,
            case: 85
        })
        var view = Model.deriveView(state)
        compare(view.aggregatePercent, null)
        compare(view.barPercentText, "")
        compare(view.batteryRows[0].text, "100%")

        var genericValue = withPrivateState(addressA, [device(addressA, { battery: 0.42 })], {
            left: 100,
            right: 99,
            case: 85
        })
        compare(Model.deriveView(genericValue).aggregatePercent, 42)
    }

    function test_mismatchingAncReadbackIsObservedButFailed() {
        var state = withPrivateState(addressA, [device(addressA)])
        var request = pending(state, "set_anc", addressA, false)
        state = Model.reduce(state, { type: "request_started", pending: request })
        var error = {
            v: 1,
            type: "error",
            id: 7,
            generation: state.generation,
            address: addressA,
            code: "anc_readback_mismatch",
            observedAnc: "awareness"
        }
        state = Model.applyBridgeMessage(state, error, 2000)
        compare(state.lastCode, "anc_readback_mismatch")
        compare(state.privateState.battery, null)
        compare(state.privateState.anc.mode, "awareness")
        compare(Model.deriveView(state).message, "Earbuds reported a different mode")

        var expiredDuringRequest = withPrivateState(addressA, [device(addressA)])
        request = pending(expiredDuringRequest, "set_anc", addressA, false)
        expiredDuringRequest = Model.reduce(expiredDuringRequest, {
            type: "request_started",
            pending: request
        })
        expiredDuringRequest = Model.reduce(expiredDuringRequest, {
            type: "age",
            nowMs: 700000
        })
        error.generation = expiredDuringRequest.generation
        expiredDuringRequest = Model.applyBridgeMessage(expiredDuringRequest, error, 700000)
        compare(expiredDuringRequest.privateState.verified, true)
        compare(expiredDuringRequest.privateState.battery, null)
        compare(expiredDuringRequest.privateState.anc.mode, "awareness")
    }

    function test_nonMismatchAncErrorsClearEveryPrivateObservation() {
        var codes = ["anc_send_failed", "timeout", "identity_mismatch", "identity_conflict"]
        for (var i = 0; i < codes.length; i++) {
            var state = withPrivateState(addressA, [device(addressA)])
            var request = pending(state, "set_anc", addressA, false)
            request.mode = "off"
            state = Model.reduce(state, { type: "request_started", pending: request })
            var error = {
                v: 1,
                type: "error",
                id: 7,
                generation: state.generation,
                address: addressA,
                code: codes[i],
                observedAnc: null
            }
            state = Model.applyBridgeMessage(state, error, 2000)
            compare(state.privateState.verified, false)
            compare(state.privateState.battery, null)
            compare(state.privateState.anc, null)
            compare(state.lastCode, codes[i])
        }
    }

    function test_persistedIdentityFailuresChooseAnotherDevice() {
        var codes = ["identity_mismatch", "identity_conflict"]
        for (var i = 0; i < codes.length; i++) {
            var state = withPrivateState(addressA, [device(addressA)])
            var request = pending(state, "refresh", addressA, false)
            state = Model.reduce(state, { type: "request_started", pending: request })
            state = Model.applyBridgeMessage(state, {
                v: 1,
                type: "error",
                id: 7,
                generation: state.generation,
                address: addressA,
                code: codes[i],
                observedAnc: null
            }, 2000)
            var view = Model.deriveView(state)
            compare(view.primaryAction, "choose")
            compare(view.primaryActionLabel, "Choose another device")
            compare(view.primaryActionEnabled, true)
        }
    }

    function test_narrowInfoRowsAndCandidateAccessibilityUseCurrentState() {
        compare(Model.shouldStackInfoRow(200, 70, 80, 8), false)
        compare(Model.shouldStackInfoRow(150, 70, 80, 8), true)
        compare(Model.shouldStackInfoRow(-1, 70, 80, 8), true)

        compare(Model.candidateAccessibleDescription(false, false, true),
                "Private controls unavailable")
        compare(Model.candidateAccessibleDescription(true, true, true),
                "Wait for the current private request to finish")
        compare(Model.candidateAccessibleDescription(true, false, true),
                "Select this connected candidate, then activate Retry")
        compare(Model.candidateAccessibleDescription(true, false, false),
                "Select this candidate; connect it in Omarchy Bluetooth before Retry")
    }

    function test_errorMessagesAreFixedAndNeverRenderPayloadsOrAddresses() {
        var codes = Model.BRIDGE_ERROR_CODES.concat([
            "service_starting",
            "helper_unavailable",
            "hello_timeout",
            "helper_stopped",
            "protocol_error",
            "no_adapter",
            "adapter_off",
            "no_candidate",
            "candidate_disconnected",
            "multiple_candidates",
            "selected_unavailable",
            "capabilities_unverified",
            "battery_stale",
            "anc_stale",
            "private_expired"
        ])
        for (var i = 0; i < codes.length; i++) {
            var message = Model.errorMessage(codes[i])
            verify(message.length > 0)
            compare(message.indexOf(addressA), -1)
            compare(message.indexOf("raw backend payload"), -1)
        }
        compare(Model.errorMessage("raw backend payload " + addressA), "Private controls unavailable")
    }
}
