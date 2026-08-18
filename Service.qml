pragma ComponentBehavior: Bound

import QtQuick
import Quickshell.Bluetooth
import Quickshell.Io
import "Model.js" as Model

Item {
    id: root

    property var shell: null
    property var manifest: null

    property var _state: Model.initialState()
    property double _nextRequestId: 1
    property string _deferredIntent: ""
    property bool _completed: false
    property bool _destroying: false
    property bool _childExpected: false
    property bool _stopHandled: false
    property bool _startupConfigInvalid: false
    property string _stdoutBuffer: ""

    readonly property var bluetoothAdapter: dynamicProperty(Bluetooth, "defaultAdapter")
    readonly property var bluetoothDeviceModel: bluetoothAdapter ? dynamicProperty(bluetoothAdapter, "devices") : null
    readonly property var bluetoothDevices: bluetoothDeviceModel ? dynamicProperty(bluetoothDeviceModel, "values") : []
    readonly property var modelState: _state
    readonly property var view: Model.deriveView(_state)
    readonly property string helperPhase: _state.helperPhase
    readonly property double generation: _state.generation
    readonly property bool pending: _state.pending !== null
    readonly property var genericState: view.generic
    readonly property var candidates: view.candidates
    readonly property var selectedDevice: view.selectedDevice
    readonly property var selectedAddress: view.selectedAddress
    readonly property var markedAddress: view.markedAddress
    readonly property var aggregateBatteryPercent: view.aggregatePercent
    readonly property var componentBatteryRows: view.batteryRows
    readonly property bool ancVisible: view.ancVisible
    readonly property bool ancEnabled: view.ancEnabled
    readonly property var ancMode: view.ancMode
    readonly property string privateAgeText: view.privateAgeText
    readonly property string lastMessage: view.message

    implicitWidth: 0
    implicitHeight: 0
    visible: false

    function dynamicProperty(object, name) {
        return object ? object[name] : null;
    }

    function sourceDirectory() {
        if (!manifest || typeof manifest.__sourceDir !== "string")
            return "";
        return manifest.__sourceDir.length > 0 ? manifest.__sourceDir : "";
    }

    function projectBluetooth() {
        var rows = [];
        var devices = bluetoothDevices || [];
        for (var i = 0; i < devices.length; i++) {
            var device = devices[i];
            if (!device)
                continue;
            rows.push({
                address: typeof device.address === "string" ? device.address : "",
                deviceName: typeof device.deviceName === "string" ? device.deviceName : "",
                name: typeof device.name === "string" ? device.name : "",
                paired: device.paired === true,
                bonded: device.bonded === true,
                connected: device.connected === true,
                batteryAvailable: device.batteryAvailable === true,
                battery: device.battery
            });
        }
        return {
            adapterPresent: bluetoothAdapter !== null,
            adapterEnabled: bluetoothAdapter !== null && bluetoothAdapter.enabled === true,
            devices: rows
        };
    }

    function syncBluetooth() {
        _state = Model.reduce(_state, {
            type: "generic",
            snapshot: projectBluetooth()
        });
    }

    function allocateRequestId() {
        var id = _nextRequestId;
        _nextRequestId += 1;
        return id;
    }

    function rejectRequest(code) {
        _state = Model.reduce(_state, {
            type: "request_rejected",
            code: code
        });
        return false;
    }

    function panelOpened() {
        if (_state.pending !== null)
            return rejectRequest("busy");
        if (_state.helperPhase === "waiting" || _state.helperPhase === "starting") {
            if (_deferredIntent === "")
                _deferredIntent = "panel";
            return true;
        }
        if (_state.helperPhase !== "ready")
            return false;
        if (_state.configInvalid)
            return rejectRequest("config_invalid");
        return privateTransactions.startRefresh("panel");
    }

    function retry() {
        if (_state.pending !== null)
            return rejectRequest("busy");
        if (_state.helperPhase === "starting") {
            _deferredIntent = "retry";
            return true;
        }
        if (_state.helperPhase === "ready")
            return privateTransactions.startRefresh("retry");

        _deferredIntent = "retry";
        return privateTransactions.startHelper();
    }

    function markCandidate(address) {
        _state = Model.reduce(_state, {
            type: "mark_candidate",
            address: address
        });
    }

    function setAnc(mode) {
        if (!Model.isAncMode(mode))
            return rejectRequest("invalid_request");
        if (_state.pending !== null)
            return rejectRequest("busy");
        if (!view.ancEnabled || _state.selectedAddress === null || _state.helperPhase !== "ready") {
            return rejectRequest("anc_invalid");
        }

        var requestId = allocateRequestId();
        var requestGeneration = _state.generation;
        var requestState = {
            id: requestId,
            generation: requestGeneration,
            method: "set_anc",
            address: _state.selectedAddress,
            mode: mode,
            selectOnSuccess: false
        };
        _state = Model.reduce(_state, {
            type: "request_started",
            pending: requestState
        });
        return privateTransactions.writeRequest({
            v: Model.PROTOCOL_VERSION,
            type: "request",
            id: requestId,
            generation: requestGeneration,
            method: "set_anc",
            address: requestState.address,
            mode: mode
        });
    }

    function clearSelection() {
        if (_state.pending !== null)
            return rejectRequest("busy");
        if (_state.helperPhase !== "ready")
            return rejectRequest("helper_unavailable");

        var requestId = allocateRequestId();
        var requestGeneration = _state.generation;
        var requestState = {
            id: requestId,
            generation: requestGeneration,
            method: "clear_selection",
            address: null,
            selectOnSuccess: false
        };
        _state = Model.reduce(_state, {
            type: "request_started",
            pending: requestState
        });
        return privateTransactions.writeRequest({
            v: Model.PROTOCOL_VERSION,
            type: "request",
            id: requestId,
            generation: requestGeneration,
            method: "clear_selection"
        });
    }

    function maybeStartHelper() {
        if (!_completed || sourceDirectory() === "")
            return;
        if (_state.helperPhase === "waiting")
            privateTransactions.startHelper();
    }

    function failHelper(code) {
        if (_destroying || _stopHandled)
            return;
        _stopHandled = true;
        _childExpected = false;
        _deferredIntent = "";
        _startupConfigInvalid = false;
        helloWatchdog.stop();
        _state = Model.reduce(_state, {
            type: "helper_failed",
            code: code
        });
        bridge.stdinEnabled = false;
        if (bridge.running) {
            bridge.running = false;
            childStopWatchdog.restart();
        }
    }

    function handleChildStopped() {
        if (_destroying || _stopHandled || !_childExpected)
            return;
        var code = _stdoutBuffer !== "" ? "protocol_error" : _state.helperPhase === "starting" ? "helper_unavailable" : "helper_stopped";
        failHelper(code);
    }

    function handleProcessExit() {
        if (_destroying)
            return;
        childStopWatchdog.stop();
        if (_stopHandled) {
            _childExpected = false;
            if (_deferredIntent === "retry") {
                _stopHandled = false;
                Qt.callLater(function () {
                    if (root._deferredIntent === "retry" && !bridge.running)
                        privateTransactions.startHelper();
                });
            }
            return;
        }
        handleChildStopped();
    }

    function handleHello(message) {
        var validated = Model.validateHello(message);
        if (!validated.ok) {
            failHelper("protocol_error");
            return;
        }
        if (_startupConfigInvalid && validated.selectedAddress !== null) {
            failHelper("protocol_error");
            return;
        }

        helloWatchdog.stop();
        _state = Model.reduce(_state, {
            type: "hello",
            message: message
        });
        if (_startupConfigInvalid) {
            _state = Model.reduce(_state, {
                type: "startup_error",
                code: "config_invalid"
            });
        }
        _startupConfigInvalid = false;
        var intent = _deferredIntent;
        _deferredIntent = "";
        if (intent === "retry" || (intent === "panel" && !_state.configInvalid))
            privateTransactions.startRefresh(intent);
    }

    function handleProtocolLine(line) {
        if (_destroying || _state.helperPhase === "failed")
            return;
        var parsed = Model.parseJsonLine(line);
        if (!parsed.ok) {
            failHelper("protocol_error");
            return;
        }

        var message = parsed.value;
        if (_state.helperPhase === "starting") {
            if (message.type === "hello") {
                handleHello(message);
                return;
            }
            var startup = Model.validateStartupError(message);
            if (startup.ok) {
                if (_startupConfigInvalid) {
                    failHelper("protocol_error");
                    return;
                }
                _startupConfigInvalid = true;
                return;
            }
            failHelper("protocol_error");
            return;
        }

        var classification = Model.classifyResponse(message, _state.pending);
        if (classification.kind === "protocol_error") {
            failHelper("protocol_error");
            return;
        }
        if (classification.kind === "stale")
            return;
        _state = Model.applyBridgeMessage(_state, message, Date.now());
    }

    function handleProtocolChunk(chunk) {
        if (_destroying || _state.helperPhase === "failed")
            return;
        var buffered = _stdoutBuffer + String(chunk);
        var newline = buffered.indexOf("\n");
        while (newline !== -1) {
            var line = buffered.substr(0, newline);
            var lineLength = Model.utf8Length(line);
            if (lineLength < 0 || lineLength + 1 > Model.MAX_JSONL_BYTES) {
                failHelper("protocol_error");
                return;
            }
            buffered = buffered.substr(newline + 1);
            handleProtocolLine(line);
            if (_state.helperPhase === "failed")
                return;
            newline = buffered.indexOf("\n");
        }
        var bufferedLength = Model.utf8Length(buffered);
        if (bufferedLength < 0 || bufferedLength >= Model.MAX_JSONL_BYTES) {
            failHelper("protocol_error");
            return;
        }
        _stdoutBuffer = buffered;
    }

    onManifestChanged: maybeStartHelper()
    onBluetoothAdapterChanged: syncBluetooth()
    onBluetoothDevicesChanged: syncBluetooth()

    QtObject {
        id: privateTransactions

        function writeRequest(request) {
            if (!bridge.running || root._state.helperPhase !== "ready") {
                root.failHelper("helper_stopped");
                return false;
            }
            bridge.write(JSON.stringify(request) + "\n");
            return true;
        }

        function startRefresh(trigger) {
            var decision = Model.contactDecision(root._state, trigger);
            if (!decision.ok)
                return root.rejectRequest(decision.reason);

            var requestId = root.allocateRequestId();
            var requestGeneration = root._state.generation;
            var requestState = {
                id: requestId,
                generation: requestGeneration,
                method: "refresh",
                address: decision.address,
                selectOnSuccess: decision.selectOnSuccess
            };
            root._state = Model.reduce(root._state, {
                type: "request_started",
                pending: requestState
            });
            return writeRequest({
                v: Model.PROTOCOL_VERSION,
                type: "request",
                id: requestId,
                generation: requestGeneration,
                method: "refresh",
                address: decision.address,
                selectOnSuccess: decision.selectOnSuccess
            });
        }

        function startHelper() {
            var directory = root.sourceDirectory();
            if (directory === "" || bridge.running || root._state.helperPhase === "starting")
                return false;

            root._state = Model.reduce(root._state, {
                type: "helper_start"
            });
            root._childExpected = true;
            root._stopHandled = false;
            root._stdoutBuffer = "";
            root._startupConfigInvalid = false;
            childStopWatchdog.stop();
            bridge.stdinEnabled = true;
            bridge.command = ["/usr/bin/env", "python3", directory + "/bridge/freebuds_bridge.py", "--stdio"];
            bridge.workingDirectory = directory;
            bridge.running = true;
            helloWatchdog.restart();
            return true;
        }

        function shutdownChild() {
            if (!bridge.running)
                return;
            bridge.write(JSON.stringify({
                v: Model.PROTOCOL_VERSION,
                type: "request",
                id: root.allocateRequestId(),
                generation: root._state.generation,
                method: "shutdown"
            }) + "\n");
            bridge.stdinEnabled = false;
        }
    }

    Connections {
        target: root.bluetoothAdapter

        function onEnabledChanged() {
            root.syncBluetooth();
        }
    }

    Connections {
        target: root.bluetoothDeviceModel

        function onValuesChanged() {
            root.syncBluetooth();
        }
    }

    Instantiator {
        model: root.bluetoothDevices

        delegate: Connections {
            required property var modelData
            target: modelData

            function onAddressChanged() {
                root.syncBluetooth();
            }
            function onDeviceNameChanged() {
                root.syncBluetooth();
            }
            function onNameChanged() {
                root.syncBluetooth();
            }
            function onPairedChanged() {
                root.syncBluetooth();
            }
            function onBondedChanged() {
                root.syncBluetooth();
            }
            function onConnectedChanged() {
                root.syncBluetooth();
            }
            function onBatteryAvailableChanged() {
                root.syncBluetooth();
            }
            function onBatteryChanged() {
                root.syncBluetooth();
            }
        }
    }

    Timer {
        id: helloWatchdog
        interval: 2000
        repeat: false
        onTriggered: root.failHelper("hello_timeout")
    }

    Timer {
        id: childStopWatchdog
        interval: 1000
        repeat: false
        onTriggered: if (bridge.running)
            bridge.signal(9)
    }

    Timer {
        id: requestWatchdog
        interval: 12000
        repeat: false
        running: root._state.pending !== null
        onTriggered: root.failHelper("timeout")
    }

    Timer {
        interval: 1000
        repeat: true
        running: root._state.privateState.battery !== null || root._state.privateState.anc !== null
        onTriggered: {
            root._state = Model.reduce(root._state, {
                type: "age",
                nowMs: Date.now()
            });
        }
    }

    Process {
        id: bridge
        stdinEnabled: true

        stdout: SplitParser {
            splitMarker: ""
            onRead: chunk => root.handleProtocolChunk(chunk)
        }

        stderr: SplitParser {
            splitMarker: ""
            onRead: function (chunk) {}
        }

        onRunningChanged: {
            if (!running && (root._childExpected || root._stopHandled))
                root.handleProcessExit();
        }
    }

    Component.onCompleted: {
        _completed = true;
        syncBluetooth();
        maybeStartHelper();
    }

    Component.onDestruction: {
        _destroying = true;
        helloWatchdog.stop();
        childStopWatchdog.stop();
        requestWatchdog.stop();
        privateTransactions.shutdownChild();
        _state = Model.reduce(_state, {
            type: "helper_failed",
            code: "helper_stopped"
        });
    }
}
