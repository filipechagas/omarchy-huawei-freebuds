import QtQuick
import Quickshell
import qs.Commons as Commons

ShellRoot {
    id: root

    readonly property string pluginRoot: Quickshell.env("FREEBUDS_PLUGIN_ROOT")
    readonly property string bridgeRoot: Quickshell.env("FREEBUDS_BRIDGE_ROOT")
    readonly property string candidateAddress: Quickshell.env("FREEBUDS_FAKE_ADDRESS")
    readonly property string startupMode: Quickshell.env("FREEBUDS_FAKE_STARTUP")
    readonly property bool startupInvalid: startupMode === "invalid"
    readonly property bool startupDuplicateInvalid: startupMode === "duplicate-invalid"
    property var failures: []
    property var serviceComponent: null
    property var panelComponent: null
    property var serviceObject: null
    property var firstPanel: null
    property var secondPanel: null
    property bool replacementPhase: false

    function check(condition, message) {
        if (!condition)
            failures.push(message)
    }

    function load(name) {
        var component = Qt.createComponent(
            "file://" + pluginRoot + "/" + name,
            Component.PreferSynchronous)
        check(component.status === Component.Ready, name + ": " + component.errorString())
        return component.status === Component.Ready ? component : null
    }

    function createPanel(component, barObject) {
        var panel = component.createObject(host)
        check(panel !== null, "Panel.qml createObject returned null")
        if (!panel)
            return null
        check(panel.bar === null || panel.bar === undefined,
              "Panel must construct before bar injection")
        panel.moduleName = "io.github.filipechagas.freebuds"
        panel.settings = {}
        panel.bar = barObject
        return panel
    }

    function injectCandidate(service) {
        var previous = service.modelState
        service._state = {
            generation: previous.generation,
            helperPhase: previous.helperPhase,
            helperError: previous.helperError,
            selectionLoaded: previous.selectionLoaded,
            selectedAddress: previous.selectedAddress,
            markedAddress: previous.markedAddress,
            configInvalid: previous.configInvalid,
            generic: {
                adapterPresent: true,
                adapterEnabled: true,
                devices: [{
                    address: candidateAddress,
                    deviceName: "HUAWEI FreeBuds Pro 5",
                    name: "Smoke-test FreeBuds",
                    paired: true,
                    bonded: true,
                    connected: true,
                    batteryAvailable: true,
                    battery: 0.68
                }]
            },
            pending: previous.pending,
            privateState: previous.privateState,
            lastCode: previous.lastCode
        }
    }

    function createService() {
        if (!serviceComponent)
            return null
        var service = serviceComponent.createObject(host)
        check(service !== null, "Service.qml createObject returned null")
        if (!service)
            return null
        check(service.shell === null || service.shell === undefined,
              "Service must construct before shell injection")
        check(service.manifest === null || service.manifest === undefined,
              "Service must construct before manifest injection")
        service.shell = fakeShell
        injectCandidate(service)
        service.manifest = {
            schemaVersion: 1,
            id: "io.github.filipechagas.freebuds",
            version: "0.1.2",
            __sourceDir: bridgeRoot
        }
        return service
    }

    function destroyService() {
        var service = serviceObject
        serviceObject = null
        if (service)
            service.destroy()
    }

    function checkPanelFallback() {
        check(firstPanel && firstPanel.freebuds === null,
              "First panel retained a destroyed service")
        check(secondPanel && secondPanel.freebuds === null,
              "Second panel retained a destroyed service")
        check(firstPanel && firstPanel.visible,
              "First panel disappeared with the service")
        check(secondPanel && secondPanel.visible,
              "Second panel disappeared with the service")
    }

    function findText(item, text) {
        if (item instanceof Text && item.text === text && item.visible)
            return item
        var children = item.children || []
        for (var i = 0; i < children.length; i++) {
            var match = findText(children[i], text)
            if (match)
                return match
        }
        return null
    }

    function checkBarRendering(panel) {
        if (!panel)
            return
        var glyph = findText(panel, panel.barIconText)
        check(glyph !== null, "Bar icon is missing")
        if (glyph) {
            var bounds = glyph.mapToItem(panel, 0, 0, glyph.width, glyph.height)
            check(bounds.height >= 8, "Bar icon was shrunk below readable size: " + bounds.height)
            var suffixes = ["OFF", "ANC", "AWR"]
            for (var suffix = 0; suffix < suffixes.length; suffix++)
                check(findText(glyph.parent, suffixes[suffix]) === null,
                      "Bar has a redundant noise-control suffix: " + suffixes[suffix])
        }
        var expectedWidth = Commons.Style.barToken("icon-slot", 27)
            + (panel.verticalBar || panel.barPercentText === "" ? 0 : Commons.Style.space(34))
        check(panel.barSlotWidth === expectedWidth, "Bar reserves space for a removed suffix")
        var texts = [panel.barPercentText]
        for (var i = 0; i < texts.length; i++) {
            if (texts[i] === "")
                continue
            var label = findText(panel, texts[i])
            if (panel.verticalBar) {
                check(label === null, "Vertical bar did not hide its compact labels")
                continue
            }
            check(label !== null, "Bar label is missing: " + texts[i])
            if (label) {
                var labelBounds = label.mapToItem(panel, 0, 0, label.width, label.height)
                check(labelBounds.height >= label.font.pixelSize * 0.8,
                      "Bar labels were shrunk with the icon: " + labelBounds.height)
            }
        }
    }

    function checkBarModes() {
        var original = serviceObject._state
        var icons = { off: "󰟎", anc: "󱑽", awareness: "󰟅" }
        var modes = Object.keys(icons)
        for (var i = 0; i < modes.length; i++) {
            var state = JSON.parse(JSON.stringify(original))
            state.privateState.anc.mode = modes[i]
            serviceObject._state = state
            var panels = [firstPanel, secondPanel]
            for (var p = 0; p < panels.length; p++) {
                check(panels[p].barIconText === icons[modes[i]],
                      "Bar icon does not reflect mode " + modes[i])
                checkBarRendering(panels[p])
            }
        }
        serviceObject._state = original
    }

    function run() {
        serviceComponent = load("Service.qml")
        panelComponent = load("Panel.qml")
        serviceObject = createService()
        if (panelComponent) {
            firstPanel = createPanel(panelComponent, firstBar)
            secondPanel = createPanel(panelComponent, secondBar)
        }
        startupSettle.start()
    }

    function verifyStartupState() {
        checkBarRendering(firstPanel)
        checkBarRendering(secondPanel)
        if (startupDuplicateInvalid) {
            check(serviceObject && serviceObject.helperPhase === "failed",
                  "Duplicate startup error did not fail the helper")
            check(serviceObject && serviceObject.modelState.helperError === "protocol_error",
                  "Duplicate startup error did not report a protocol failure")
            check(serviceObject && serviceObject.pending === false,
                  "Duplicate startup error left a request pending")
            destroyService()
            finalServiceGone.start()
            return
        }

        check(serviceObject && serviceObject.helperPhase === "ready",
              "Service did not accept the bridge hello")
        check(serviceObject && serviceObject.pending === false,
              "Startup did not settle")
        if (startupInvalid) {
            check(serviceObject && serviceObject.selectedAddress === null,
                  "Invalid config authorized a device before Retry")
            check(serviceObject && serviceObject.modelState.configInvalid,
                  "Invalid config was not retained after hello")
            check(serviceObject && serviceObject.componentBatteryRows.length === 0,
                  "Invalid config triggered private contact from panel open")
            if (firstPanel)
                firstPanel.open()
            if (secondPanel)
                secondPanel.open()
            invalidPanelSettle.start()
            return
        }

        if (firstPanel)
            firstPanel.open()
        check(serviceObject && serviceObject.pending,
              "First panel open did not start a refresh")
        pendingSecondOpen.start()
    }

    function verifySecondOpenWhilePending() {
        check(serviceObject && serviceObject.pending,
              "Refresh settled before the second panel opened")
        if (secondPanel)
            secondPanel.open()
        check(serviceObject && serviceObject.pending,
              "Second panel open replaced the pending refresh")
        refreshSettle.start()
    }

    function verifyInvalidPanelGuard() {
        check(serviceObject && serviceObject.helperPhase === "ready",
              "Invalid-config service stopped before explicit Retry")
        check(serviceObject && serviceObject.pending === false,
              "Post-hello panel open bypassed invalid-config gating")
        check(serviceObject && serviceObject.selectedAddress === null,
              "Post-hello panel open authorized the invalid config")
        check(serviceObject && serviceObject.modelState.configInvalid,
              "Post-hello panel open cleared invalid-config state")
        if (firstPanel) {
            firstPanel.close()
            firstPanel.open()
        }
        check(serviceObject && serviceObject.pending === false,
              "Repeated panel open bypassed invalid-config gating")
        check(serviceObject && serviceObject.retry(),
              "Explicit Retry did not start invalid-config recovery")
        check(serviceObject && serviceObject.pending,
              "Explicit Retry did not remain pending")
        if (secondPanel) {
            secondPanel.close()
            secondPanel.open()
        }
        check(serviceObject && serviceObject.pending,
              "Panel open queued behind explicit Retry")
        refreshSettle.start()
    }

    function verifyRefreshedState() {
        check(serviceObject && serviceObject.pending === false,
              "Shared refresh did not settle")
        check(serviceObject && serviceObject.selectedAddress === candidateAddress,
              "Verified refresh did not establish the selected smoke candidate")
        check(serviceObject && serviceObject.componentBatteryRows.length === 3,
              "Fake bridge refresh result was not accepted")
        check(serviceObject && !serviceObject.modelState.configInvalid,
              "Successful verification did not clear the invalid-config state")
        check(firstPanel && firstPanel.manageIpc === false,
              "First per-monitor panel owns IPC")
        check(secondPanel && secondPanel.manageIpc === false,
              "Second per-monitor panel owns IPC")
        check(firstPanel && firstPanel.freebuds === serviceObject,
              "First panel did not resolve the shared service")
        check(secondPanel && secondPanel.freebuds === serviceObject,
              "Second panel did not resolve the shared service")
        check(firstPanel && firstPanel.opened,
              "First panel did not open")
        check(secondPanel && secondPanel.opened,
              "Second panel did not open")
        check(firstPanel && firstPanel.visible,
              "First bar widget is not always visible")
        check(secondPanel && secondPanel.visible,
              "Second bar widget is not always visible")

        checkBarRendering(firstPanel)
        checkBarRendering(secondPanel)

        checkBarModes()
        destroyService()
        if (replacementPhase)
            finalServiceGone.start()
        else
            serviceGone.start()
    }

    function recreateService() {
        checkPanelFallback()
        check(firstPanel && firstPanel.opened,
              "First panel closed across service removal")
        check(secondPanel && secondPanel.opened,
              "Second panel closed across service removal")
        replacementPhase = true
        serviceObject = createService()
        replacementSettle.start()
    }

    function verifyReplacementState() {
        check(serviceObject && serviceObject.helperPhase === "ready",
              "Replacement service did not become ready")
        check(firstPanel && firstPanel.freebuds === serviceObject,
              "First panel did not resolve the replacement service")
        check(secondPanel && secondPanel.freebuds === serviceObject,
              "Second panel did not resolve the replacement service")
        check(firstPanel && firstPanel.opened && secondPanel && secondPanel.opened,
              "Panels did not remain open across service replacement")
        check(serviceObject && serviceObject.pending === false,
              "Already-open panel contacted the replacement service")
        check(serviceObject && serviceObject.selectedAddress === null,
              "Replacement service contacted a device without a new intent")
        check(serviceObject && serviceObject.componentBatteryRows.length === 0,
              "Replacement service exposed private data without a new intent")

        if (firstPanel) {
            firstPanel.close()
            firstPanel.open()
        }
        if (startupInvalid) {
            check(serviceObject && serviceObject.pending === false,
                  "Replacement panel open bypassed invalid-config gating")
            check(serviceObject && serviceObject.retry(),
                  "Replacement explicit Retry did not start a refresh")
        }
        check(serviceObject && serviceObject.pending,
              "Replacement service did not accept the intentional trigger")
        if (secondPanel) {
            secondPanel.close()
            secondPanel.open()
        }
        check(serviceObject && serviceObject.pending,
              "Replacement panel queued behind the pending refresh")
        refreshSettle.start()
    }

    function finishAfterFinalService() {
        checkPanelFallback()
        if (firstPanel)
            firstPanel.destroy()
        if (secondPanel)
            secondPanel.destroy()
        teardown.start()
    }

    function finish() {
        for (var i = 0; i < failures.length; i++)
            console.error("HOST-SMOKE:", failures[i])
        if (failures.length === 0)
            console.log("HOST-SMOKE: PASS")
        Qt.exit(failures.length === 0 ? 0 : 1)
    }

    Item {
        id: host
    }

    QtObject {
        id: fakeShell

        function serviceFor(pluginId) {
            return pluginId === "io.github.filipechagas.freebuds"
                ? root.serviceObject : null
        }
    }

    QtObject {
        id: firstBar
        property var shell: fakeShell
        property bool vertical: false
        property int barSize: 26
        property string position: "top"
        property string fontFamily: "monospace"
        property color foreground: "white"
        property color barForeground: "white"
        property color urgent: "red"
        property bool foregroundAnimationEnabled: false
        property var activePopout: null
        property var clickTargets: []

        function requestPopout(owner) { activePopout = owner }
        function releasePopout(owner) {
            if (activePopout === owner)
                activePopout = null
        }
        function registerClickTarget(target) {}
        function unregisterClickTarget(target) {}
        function showTooltip(target, text) {}
        function hideTooltip(target) {}
        function switchPanelFrom(panel, direction) { return false }
        function moduleWidgets(name) { return [] }
    }

    QtObject {
        id: secondBar
        property var shell: fakeShell
        property bool vertical: false
        property int barSize: 26
        property string position: "top"
        property string fontFamily: "monospace"
        property color foreground: "white"
        property color barForeground: "white"
        property color urgent: "red"
        property bool foregroundAnimationEnabled: false
        property var activePopout: null
        property var clickTargets: []

        function requestPopout(owner) { activePopout = owner }
        function releasePopout(owner) {
            if (activePopout === owner)
                activePopout = null
        }
        function registerClickTarget(target) {}
        function unregisterClickTarget(target) {}
        function showTooltip(target, text) {}
        function hideTooltip(target) {}
        function switchPanelFrom(panel, direction) { return false }
        function moduleWidgets(name) { return [] }
    }

    Timer {
        id: startupSettle
        interval: 300
        repeat: false
        onTriggered: root.verifyStartupState()
    }

    Timer {
        id: pendingSecondOpen
        interval: 30
        repeat: false
        onTriggered: root.verifySecondOpenWhilePending()
    }

    Timer {
        id: invalidPanelSettle
        interval: 100
        repeat: false
        onTriggered: root.verifyInvalidPanelGuard()
    }

    Timer {
        id: refreshSettle
        interval: 600
        repeat: false
        onTriggered: root.verifyRefreshedState()
    }

    Timer {
        id: serviceGone
        interval: 200
        repeat: false
        onTriggered: root.recreateService()
    }

    Timer {
        id: replacementSettle
        interval: 300
        repeat: false
        onTriggered: root.verifyReplacementState()
    }

    Timer {
        id: finalServiceGone
        interval: 200
        repeat: false
        onTriggered: root.finishAfterFinalService()
    }

    Timer {
        id: teardown
        interval: 400
        repeat: false
        onTriggered: root.finish()
    }

    Component.onCompleted: Qt.callLater(root.run)
}
