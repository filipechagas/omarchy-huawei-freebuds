pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import Quickshell.Bluetooth
import qs.Commons as Commons
import qs.Ui as Ui
import "Model.js" as Model

Ui.Panel {
    id: root

    manageIpc: false

    property bool serviceWaitExpired: false
    property bool everHadService: false
    property bool cursorActive: false
    property int cursorIndex: 0
    property string cursorKind: ""
    property string cursorKey: ""

    readonly property var freebuds: {
        var hostShell = dynamicProperty(bar, "shell");
        return hostShell && typeof hostShell.serviceFor === "function" ? hostShell.serviceFor(moduleName) : null;
    }
    readonly property var directAdapter: dynamicProperty(Bluetooth, "defaultAdapter")
    readonly property var directDeviceModel: directAdapter ? dynamicProperty(directAdapter, "devices") : null
    readonly property var directDevices: directDeviceModel ? dynamicProperty(directDeviceModel, "values") : []
    readonly property var directSnapshot: projectDirectBluetooth()
    readonly property var fallback: Model.fallbackView(directSnapshot)
    readonly property var currentView: freebuds ? freebuds.view : fallback
    readonly property var generic: currentView.generic || Model.normalizeGeneric(null)
    readonly property var candidates: currentView.candidates || []
    readonly property var batteryRows: currentView.batteryRows || []
    readonly property var selectedAddress: currentView.selectedAddress || null
    readonly property var markedAddress: currentView.markedAddress || null
    readonly property bool hasService: freebuds !== null && freebuds !== undefined
    readonly property bool verticalBar: dynamicProperty(bar, "vertical") === true
    readonly property var barFontFamily: dynamicProperty(bar, "fontFamily")
    readonly property string fontFamily: typeof barFontFamily === "string" ? barFontFamily : Commons.Style.fontFamily
    readonly property int captionFontSize: Commons.Style.fontToken("caption", Commons.Style.fontPx(0.833))
    readonly property int bodySmallFontSize: Commons.Style.fontToken("body-small", Commons.Style.fontPx(0.917))
    readonly property int bodyFontSize: Commons.Style.fontToken("body", Commons.Style.fontPx(1))
    readonly property int displayFontSize: Commons.Style.fontToken("display", Commons.Style.fontPx(2))
    readonly property string statusMessage: hasService ? (currentView.message || "") : (serviceWaitExpired || everHadService ? "Private controls unavailable" : "FreeBuds service is starting")
    readonly property string adapterText: !generic.adapterPresent ? "No Bluetooth adapter" : generic.adapterEnabled ? "On" : "Off"
    readonly property string connectionText: currentView.connectionText || "No earbuds selected"
    readonly property string barPercentText: currentView.barPercentText || ""
    readonly property string barAncMode: currentView.barAncMode || ""
    readonly property string barAncText: currentView.barAncText || ""
    readonly property string barIconText: barAncMode === "off" ? "󰟎" : barAncMode === "anc" ? "󱑽" : barAncMode === "awareness" ? "󰟅" : "󰋋"
    readonly property real barSlotWidth: verticalBar ? Commons.Style.barToken("icon-slot", 27) : Commons.Style.barToken("icon-slot", 27) + (barPercentText === "" ? 0 : Commons.Style.space(34)) + (barAncText === "" ? 0 : Commons.Style.space(30))
    readonly property bool candidatePickerVisible: selectedAddress === null && candidates.length > 0
    readonly property bool ancVisible: currentView.ancVisible === true
    readonly property bool ancEnabled: currentView.ancEnabled === true
    readonly property string ancMode: currentView.ancMode || ""
    readonly property string ancDisabledReason: {
        if (ancEnabled)
            return "Select a noise-control mode";
        if (currentView.pending)
            return "Wait for the current private request to finish";
        if (!currentView.connected)
            return "Connect the earbuds in Omarchy Bluetooth";
        if (currentView.ancFreshness === "stale")
            return "Retry to refresh noise control before changing it";
        return "Noise control is not currently available";
    }
    // The bar can switch to dark text over a bright wallpaper. Popup text
    // must follow its own surface palette instead of inheriting that color.
    readonly property color panelForeground: Commons.Color.popups.text
    readonly property color panelSecondary: Qt.rgba(panelForeground.r, panelForeground.g, panelForeground.b, 0.78)
    readonly property string statusDetail: {
        var code = currentView.messageCode || "";
        if (code === "identity_timeout")
            return "The control channel connected but did not answer. Reconnect the earbuds in Omarchy Bluetooth, then retry.";
        if (code === "transport_busy")
            return "The control channel is still occupied. Reconnect the earbuds in Omarchy Bluetooth, then retry.";
        if (code === "timeout" || code === "connect_failed" || code === "transport_busy" || code === "socket_closed")
            return currentView.connected ? "Bluetooth audio is connected, but the control channel is unavailable. Reconnect the earbuds in Omarchy Bluetooth, then retry." : "Connect the earbuds in Omarchy Bluetooth, then retry.";
        if (code === "security_failed" || code === "transport_unsupported")
            return "The secure control channel is unavailable. Bluetooth battery status remains available.";
        return "";
    }
    readonly property var cursorRows: buildCursorRows()

    visible: true
    implicitWidth: barButton.implicitWidth
    implicitHeight: barButton.implicitHeight

    function dynamicProperty(object, name) {
        return object ? object[name] : null;
    }

    function projectDirectBluetooth() {
        var rows = [];
        var devices = directDevices || [];
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
            adapterPresent: directAdapter !== null,
            adapterEnabled: directAdapter !== null && directAdapter.enabled === true,
            devices: rows
        };
    }

    function buildCursorRows() {
        var rows = [];
        if (hasService && candidatePickerVisible && !currentView.pending) {
            for (var i = 0; i < candidates.length; i++)
                rows.push({
                    kind: "candidate",
                    key: candidates[i].address
                });
        }
        if (hasService && ancVisible && ancEnabled) {
            rows.push({
                kind: "anc",
                key: "off"
            });
            rows.push({
                kind: "anc",
                key: "anc"
            });
            rows.push({
                kind: "anc",
                key: "awareness"
            });
        }
        if (hasService && currentView.canRefreshFresh)
            rows.push({
                kind: "refresh",
                key: "refresh"
            });
        if (hasService && currentView.primaryAction && currentView.primaryAction !== "none" && currentView.primaryActionEnabled) {
            rows.push({
                kind: "primary",
                key: currentView.primaryAction
            });
        }
        return rows;
    }

    function rowIndex(kind, key) {
        for (var i = 0; i < cursorRows.length; i++) {
            if (cursorRows[i].kind === kind && cursorRows[i].key === key)
                return i;
        }
        return -1;
    }

    function setCursor(kind, key) {
        var index = rowIndex(kind, key);
        if (index < 0)
            return;
        cursorActive = true;
        cursorIndex = index;
        cursorKind = kind;
        cursorKey = key;
    }

    function setCursorIndex(index) {
        if (index < 0 || index >= cursorRows.length)
            return;
        cursorActive = true;
        cursorIndex = index;
        cursorKind = cursorRows[index].kind;
        cursorKey = cursorRows[index].key;
    }

    function keepVisible(item) {
        if (!item || !bodyFlickable || bodyFlickable.height <= 0)
            return;
        var point = item.mapToItem(contentColumn, 0, 0);
        var top = point.y;
        var bottom = top + item.height;
        if (top < bodyFlickable.contentY)
            bodyFlickable.contentY = Math.max(0, top);
        else if (bottom > bodyFlickable.contentY + bodyFlickable.height)
            bodyFlickable.contentY = Math.min(Math.max(0, bodyFlickable.contentHeight - bodyFlickable.height), bottom - bodyFlickable.height);
    }

    function keepCurrentVisible() {
        if (!cursorActive || cursorIndex < 0 || cursorIndex >= cursorRows.length)
            return;
        var row = cursorRows[cursorIndex];
        if (row.kind === "anc")
            keepVisible(noiseGrid);
        else if (row.kind === "refresh")
            keepVisible(refreshButton);
        else if (row.kind === "primary")
            keepVisible(primaryButton);
    }

    function moveCursor(dx, dy) {
        if (cursorRows.length === 0)
            return;
        if (!cursorActive) {
            setCursorIndex(Math.min(cursorIndex, cursorRows.length - 1));
            Qt.callLater(keepCurrentVisible);
            return;
        }

        var current = cursorRows[cursorIndex];
        var next = cursorIndex;
        if (current.kind === "anc" && noiseGrid.columns === 3) {
            if (dx !== 0) {
                var adjacent = cursorIndex + dx;
                if (adjacent >= 0 && adjacent < cursorRows.length && cursorRows[adjacent].kind === "anc") {
                    next = adjacent;
                }
            } else if (dy > 0) {
                while (next < cursorRows.length && cursorRows[next].kind === "anc")
                    next += 1;
                if (next >= cursorRows.length)
                    next = cursorIndex;
            }
        } else if (current.kind === "anc" && noiseGrid.columns === 1) {
            if (dy !== 0)
                next = Math.max(0, Math.min(cursorRows.length - 1, cursorIndex + dy));
        } else if (current.kind === "candidate") {
            if (dy !== 0)
                next = Math.max(0, Math.min(cursorRows.length - 1, cursorIndex + dy));
        } else if ((current.kind === "refresh" || (current.kind === "primary" && !currentView.canRefreshFresh)) && dy < 0 && ancVisible && noiseGrid.columns === 3) {
            var selectedMode = rowIndex("anc", ancMode);
            next = selectedMode >= 0 ? selectedMode : rowIndex("anc", "off");
        } else if ((current.kind === "primary" || current.kind === "refresh") && dy !== 0) {
            next = Math.max(0, Math.min(cursorRows.length - 1, cursorIndex + dy));
        }
        setCursorIndex(next);
        Qt.callLater(keepCurrentVisible);
    }

    function activateCursor() {
        if (!cursorActive || cursorIndex < 0 || cursorIndex >= cursorRows.length || !hasService)
            return;
        var row = cursorRows[cursorIndex];
        if (row.kind === "candidate")
            freebuds.markCandidate(row.key);
        else if (row.kind === "anc")
            freebuds.setAnc(row.key);
        else if (row.kind === "refresh" && currentView.canRefreshFresh)
            freebuds.retry();
        else if (row.kind === "primary")
            activatePrimary();
    }

    function activatePrimary() {
        if (!hasService || !currentView.primaryActionEnabled)
            return;
        if (currentView.primaryAction === "retry")
            freebuds.retry();
        else if (currentView.primaryAction === "choose")
            freebuds.clearSelection();
    }

    function privateRowAccessibleName(row) {
        var label = row.key === "case" ? "Charging case" : row.label + " earbud";
        return label + " battery, " + row.value + " percent, " + (row.status ? row.status + ", " : "") + String(currentView.batteryAgeText || "last report unavailable").toLowerCase();
    }

    onFreebudsChanged: {
        if (hasService) {
            everHadService = true;
            serviceWaitExpired = false;
            serviceWait.stop();
        } else if (everHadService) {
            serviceWaitExpired = true;
        } else {
            serviceWait.restart();
        }
    }

    onCursorRowsChanged: {
        if (cursorRows.length === 0) {
            cursorActive = false;
            cursorIndex = 0;
            cursorKind = "";
            cursorKey = "";
        } else if (cursorActive) {
            var preservedIndex = rowIndex(cursorKind, cursorKey);
            if (preservedIndex >= 0) {
                cursorIndex = preservedIndex;
            } else {
                cursorActive = false;
                cursorIndex = 0;
                cursorKind = "";
                cursorKey = "";
            }
        } else if (cursorIndex >= cursorRows.length) {
            cursorIndex = cursorRows.length - 1;
        }
    }

    onOpenedChanged: {
        if (!opened)
            return;
        cursorActive = false;
        cursorIndex = 0;
        cursorKind = "";
        cursorKey = "";
        bodyFlickable.contentY = 0;
        if (hasService)
            freebuds.panelOpened();
    }

    Timer {
        id: serviceWait
        interval: 2000
        repeat: false
        running: !root.hasService && !root.serviceWaitExpired
        onTriggered: root.serviceWaitExpired = true
    }

    Component {
        id: barContent

        Item {
            Row {
                anchors.centerIn: parent
                spacing: Commons.Style.space(4)

                Text {
                    text: root.barIconText
                    color: root.barForeground
                    font.family: root.fontFamily
                    font.pixelSize: Commons.Style.barToken("icon-font", 13)
                    Accessible.ignored: true
                }

                Text {
                    visible: !root.verticalBar && root.barPercentText !== ""
                    text: root.barPercentText
                    color: root.barForeground
                    font.family: root.fontFamily
                    font.pixelSize: root.bodySmallFontSize
                    font.bold: true
                    Accessible.ignored: true
                }

                Text {
                    visible: !root.verticalBar && root.barAncText !== ""
                    text: root.barAncText
                    color: root.barForeground
                    font.family: root.fontFamily
                    font.pixelSize: root.captionFontSize
                    font.bold: true
                    Accessible.ignored: true
                }
            }
        }
    }

    Ui.BarIconButton {
        id: barButton
        anchors.fill: parent
        bar: root.bar
        dimmed: !root.generic.adapterPresent || !root.generic.adapterEnabled || !root.currentView.connected
        slotSize: root.barSlotWidth
        opticalSize: root.barSlotWidth
        iconComponent: barContent
        tooltipText: root.currentView.barTooltip || "FreeBuds Pro 5"
        onPressed: function (button) {
            if (button === Qt.LeftButton)
                root.toggle();
        }

        Accessible.role: Accessible.Button
        Accessible.name: root.currentView.barAccessibleName || "FreeBuds Pro 5"
        Accessible.description: root.opened ? "Closes FreeBuds status" : "Opens FreeBuds status"
        Accessible.onPressAction: root.toggle()
    }

    Ui.KeyboardPanel {
        id: popup
        anchorItem: barButton
        owner: root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: fittedContentWidth(Commons.Style.space(380))
        contentHeight: fittedContentHeight(contentColumn.implicitHeight, Commons.Style.space(560))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onMoveRequested: function (dx, dy) {
                root.moveCursor(dx, dy);
            }
            onActivateRequested: root.activateCursor()
            onCloseRequested: root.close()
            onTabRequested: function (direction) {
                root.switchPanel(direction);
            }

            Flickable {
                id: bodyFlickable
                anchors.fill: parent
                contentWidth: width
                contentHeight: contentColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height
                clip: true

                Controls.ScrollBar.vertical: Controls.ScrollBar {
                    policy: Controls.ScrollBar.AsNeeded
                }

                Column {
                    id: contentColumn
                    width: bodyFlickable.width
                    spacing: Commons.Style.space(14)

                    Ui.PanelHero {
                        title: "FreeBuds Pro 5"
                        meta: root.connectionText
                        foreground: root.panelForeground
                        fontFamily: root.fontFamily
                        iconComponent: Component {
                            Text {
                                text: "󰋋"
                                color: root.panelForeground
                                font.family: root.fontFamily
                                font.pixelSize: root.displayFontSize
                                Accessible.ignored: true
                            }
                        }
                    }

                    Ui.PanelSeparator {
                        foreground: root.panelForeground
                        Accessible.ignored: true
                    }

                    Column {
                        width: parent.width
                        spacing: Commons.Style.space(8)

                        Ui.PanelSectionHeader {
                            text: "STATUS"
                            foreground: root.panelForeground
                            fontFamily: root.fontFamily
                        }

                        InfoRow {
                            label: "Bluetooth adapter"
                            value: root.adapterText
                            accessibleName: "Bluetooth adapter, " + root.adapterText
                        }

                        InfoRow {
                            label: "Connection"
                            value: root.connectionText
                            accessibleName: "FreeBuds connection, " + root.connectionText
                        }
                    }

                    Ui.PanelSeparator {
                        foreground: root.panelForeground
                        Accessible.ignored: true
                    }

                    Column {
                        width: parent.width
                        spacing: Commons.Style.space(8)

                        Ui.PanelSectionHeader {
                            text: "BATTERY"
                            foreground: root.panelForeground
                            fontFamily: root.fontFamily
                        }

                        InfoRow {
                            visible: root.currentView.showAggregateBattery !== false
                            label: "Earbuds"
                            value: root.currentView.aggregateText || "Not reported"
                            batteryPercent: root.currentView.aggregatePercent === null || root.currentView.aggregatePercent === undefined ? -1 : root.currentView.aggregatePercent
                            accessibleName: root.currentView.aggregatePercent === null || root.currentView.aggregatePercent === undefined ? "Earbuds battery not reported" : "Earbuds battery, " + root.currentView.aggregatePercent + " percent"
                        }

                        Repeater {
                            model: root.batteryRows

                            delegate: InfoRow {
                                required property var modelData
                                label: modelData.label
                                value: modelData.text
                                detail: modelData.status || ""
                                batteryPercent: modelData.value
                                accessibleName: root.privateRowAccessibleName(modelData)
                            }
                        }

                        Text {
                            visible: root.batteryRows.length > 0
                            width: parent.width
                            text: root.currentView.batteryAgeText || ""
                            color: root.panelSecondary
                            font.family: root.fontFamily
                            font.pixelSize: root.captionFontSize
                            wrapMode: Text.WordWrap
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                    }

                    Column {
                        visible: root.ancVisible
                        width: parent.width
                        spacing: Commons.Style.space(8)

                        Ui.PanelSeparator {
                            foreground: root.panelForeground
                            Accessible.ignored: true
                        }

                        Ui.PanelSectionHeader {
                            text: "NOISE CONTROL"
                            foreground: root.panelForeground
                            fontFamily: root.fontFamily
                        }

                        Grid {
                            id: noiseGrid
                            width: parent.width
                            columns: width >= Commons.Style.space(320) ? 3 : 1
                            columnSpacing: Commons.Style.space(6)
                            rowSpacing: Commons.Style.space(6)
                            Accessible.role: Accessible.Grouping
                            Accessible.name: "Noise control"

                            Repeater {
                                model: [
                                    {
                                        key: "off",
                                        label: "Off"
                                    },
                                    {
                                        key: "anc",
                                        label: "ANC"
                                    },
                                    {
                                        key: "awareness",
                                        label: "Awareness"
                                    }
                                ]

                                delegate: Ui.Button {
                                    id: modeButton
                                    required property var modelData
                                    width: noiseGrid.columns === 1 ? noiseGrid.width : (noiseGrid.width - noiseGrid.columnSpacing * 2) / 3
                                    text: modelData.label + (root.currentView.pendingAncMode === modelData.key ? "…" : "")
                                    bordered: true
                                    selected: root.ancMode === modelData.key
                                    enabled: root.ancEnabled
                                    opacity: enabled ? 1 : 0.5
                                    foreground: root.panelForeground
                                    fontFamily: root.fontFamily
                                    hasCursor: root.cursorActive && root.cursorIndex === root.rowIndex("anc", modelData.key)
                                    onClicked: if (root.hasService)
                                        root.freebuds.setAnc(modelData.key)
                                    onHovered: function (hovered) {
                                        if (hovered && enabled)
                                            root.setCursor("anc", modelData.key);
                                    }
                                    onHasCursorChanged: if (hasCursor)
                                        Qt.callLater(function () {
                                            root.keepVisible(noiseGrid);
                                        })

                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData.label
                                    Accessible.description: root.ancDisabledReason
                                    Accessible.checkable: true
                                    Accessible.checked: modeButton.selected
                                    Accessible.onPressAction: if (modeButton.enabled && root.hasService)
                                        root.freebuds.setAnc(modelData.key)
                                }
                            }
                        }

                        Text {
                            visible: true
                            width: parent.width
                            text: root.currentView.pendingAncMode ? root.currentView.message : (root.currentView.ancAgeText || "Not reported") + (!root.ancEnabled ? ". " + root.ancDisabledReason : "")
                            color: root.panelSecondary
                            font.family: root.fontFamily
                            font.pixelSize: root.captionFontSize
                            wrapMode: Text.WordWrap
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                    }

                    Column {
                        visible: root.candidatePickerVisible
                        width: parent.width
                        spacing: Commons.Style.space(8)
                        Accessible.role: Accessible.Grouping
                        Accessible.name: "FreeBuds candidates"

                        Ui.PanelSeparator {
                            foreground: root.panelForeground
                            Accessible.ignored: true
                        }

                        Ui.PanelSectionHeader {
                            text: "DEVICE"
                            foreground: root.panelForeground
                            fontFamily: root.fontFamily
                        }

                        Repeater {
                            model: root.candidates

                            delegate: CandidateRow {
                                required property var modelData
                                candidate: modelData
                            }
                        }
                    }

                    Rectangle {
                        visible: root.statusMessage !== ""
                        width: parent.width
                        implicitHeight: statusColumn.implicitHeight + Commons.Style.space(12) * 2
                        radius: Commons.Style.cornerRadius
                        color: Qt.rgba(root.panelForeground.r, root.panelForeground.g, root.panelForeground.b, 0.06)

                        Column {
                            id: statusColumn
                            x: Commons.Style.space(12)
                            y: Commons.Style.space(12)
                            width: parent.width - x * 2
                            spacing: Commons.Style.space(6)

                            Text {
                                width: parent.width
                                text: root.statusMessage
                                textFormat: Text.PlainText
                                color: root.panelForeground
                                font.family: root.fontFamily
                                font.pixelSize: root.bodySmallFontSize
                                font.bold: true
                                wrapMode: Text.WordWrap
                                Accessible.role: Accessible.StaticText
                                Accessible.name: text
                            }

                            Text {
                                visible: root.statusDetail !== ""
                                width: parent.width
                                text: root.statusDetail
                                textFormat: Text.PlainText
                                color: root.panelSecondary
                                font.family: root.fontFamily
                                font.pixelSize: root.bodySmallFontSize
                                wrapMode: Text.WordWrap
                                Accessible.role: Accessible.StaticText
                                Accessible.name: text
                            }

                            Controls.ProgressBar {
                                visible: root.currentView.pending === true
                                width: parent.width
                                indeterminate: visible
                                Accessible.name: "Request in progress"
                            }
                        }
                    }

                    Ui.Button {
                        id: refreshButton
                        visible: root.hasService && root.currentView.canRefreshFresh === true
                        enabled: visible
                        width: parent.width
                        text: "Refresh"
                        bordered: true
                        focusable: false
                        foreground: root.panelForeground
                        fontFamily: root.fontFamily
                        hasCursor: root.cursorActive && root.cursorKind === "refresh"
                        onClicked: if (enabled)
                            root.freebuds.retry()
                        onHovered: function (hovered) {
                            if (hovered && enabled)
                                root.setCursor("refresh", "refresh");
                        }
                        onHasCursorChanged: if (hasCursor)
                            Qt.callLater(function () {
                                root.keepVisible(refreshButton);
                            })
                        Accessible.role: Accessible.Button
                        Accessible.name: text
                        Accessible.description: "Refreshes battery and noise control once"
                        Accessible.onPressAction: if (enabled)
                            root.freebuds.retry()
                    }

                    Ui.Button {
                        id: primaryButton
                        visible: root.hasService && typeof root.currentView.primaryAction === "string" && root.currentView.primaryAction !== "" && root.currentView.primaryAction !== "none"
                        width: parent.width
                        text: root.currentView.primaryActionLabel || ""
                        bordered: true
                        focusable: false
                        enabled: root.currentView.primaryActionEnabled === true
                        opacity: enabled ? 1 : 0.5
                        foreground: root.panelForeground
                        fontFamily: root.fontFamily
                        hasCursor: root.cursorActive && root.cursorIndex === root.rowIndex("primary", root.currentView.primaryAction || "")
                        onClicked: root.activatePrimary()
                        onHovered: function (hovered) {
                            if (hovered && enabled)
                                root.setCursor("primary", root.currentView.primaryAction);
                        }
                        onHasCursorChanged: if (hasCursor)
                            Qt.callLater(function () {
                                root.keepVisible(primaryButton);
                            })

                        Accessible.role: Accessible.Button
                        Accessible.name: text
                        Accessible.description: enabled ? (root.currentView.primaryAction === "retry" ? "Attempts one private status refresh" : "Clears only the locally saved device selection") : "This action is unavailable until the current status changes"
                        Accessible.onPressAction: if (enabled)
                            root.activatePrimary()
                    }
                }
            }
        }
    }

    component InfoRow: Item {
        id: infoRow

        required property string label
        required property string value
        required property string accessibleName
        property string detail: ""
        property real batteryPercent: -1
        readonly property bool hasBattery: batteryPercent >= 0 && batteryPercent <= 100
        readonly property int columnSpacing: Commons.Style.space(8)
        readonly property bool stacked: Model.shouldStackInfoRow(width, infoLabel.implicitWidth, infoValue.implicitWidth, columnSpacing)

        width: parent ? parent.width : implicitWidth
        readonly property real labelHeight: stacked ? infoLabel.implicitHeight + columnSpacing + infoValue.implicitHeight : Math.max(infoLabel.implicitHeight, infoValue.implicitHeight)
        implicitHeight: labelHeight + (hasBattery ? Commons.Style.space(12) : 0) + (detail === "" ? 0 : infoDetail.implicitHeight + Commons.Style.space(4))
        Accessible.role: Accessible.StaticText
        Accessible.name: accessibleName

        Text {
            id: infoLabel
            x: 0
            y: 0
            width: infoRow.stacked ? infoRow.width : Math.min(implicitWidth, Math.max(0, infoRow.width - infoRow.columnSpacing))
            text: infoRow.label
            textFormat: Text.PlainText
            color: root.panelForeground
            font.family: root.fontFamily
            font.pixelSize: root.bodyFontSize
            elide: Text.ElideRight
            maximumLineCount: 1
            Accessible.ignored: true
        }

        Text {
            id: infoValue
            x: infoRow.stacked ? 0 : infoLabel.width + infoRow.columnSpacing
            y: infoRow.stacked ? infoLabel.implicitHeight + infoRow.columnSpacing : 0
            width: infoRow.stacked ? infoRow.width : Math.max(0, infoRow.width - x)
            text: infoRow.value
            textFormat: Text.PlainText
            color: root.panelForeground
            font.family: root.fontFamily
            font.pixelSize: infoRow.hasBattery ? root.bodyFontSize * 1.5 : root.bodyFontSize
            font.bold: true
            horizontalAlignment: infoRow.stacked ? Text.AlignLeft : Text.AlignRight
            elide: Text.ElideRight
            maximumLineCount: 1
            Accessible.ignored: true
        }
        Rectangle {
            visible: infoRow.hasBattery
            y: infoRow.labelHeight + Commons.Style.space(6)
            width: infoRow.width
            height: Commons.Style.space(4)
            radius: height / 2
            color: Qt.rgba(root.panelForeground.r, root.panelForeground.g, root.panelForeground.b, 0.14)
            Accessible.ignored: true

            Rectangle {
                width: parent.width * Math.max(0, Math.min(100, infoRow.batteryPercent)) / 100
                height: parent.height
                radius: parent.radius
                color: infoRow.batteryPercent <= 20 ? Commons.Color.urgent : root.panelForeground
            }
        }

        Text {
            id: infoDetail
            visible: infoRow.detail !== ""
            y: infoRow.labelHeight + (infoRow.hasBattery ? Commons.Style.space(12) : 0) + Commons.Style.space(4)
            width: infoRow.width
            text: infoRow.detail
            color: root.panelSecondary
            font.family: root.fontFamily
            font.pixelSize: root.captionFontSize
            wrapMode: Text.WordWrap
            Accessible.ignored: true
        }
    }

    component CandidateRow: Ui.CursorSurface {
        id: candidateRow

        required property var candidate

        readonly property int actionIndex: root.rowIndex("candidate", candidateRow.candidate.address)

        width: parent ? parent.width : implicitWidth
        implicitHeight: Math.max(candidateLabel.implicitHeight, candidateStatus.implicitHeight) + Commons.Style.space(6) * 2
        hasCursor: root.cursorActive && root.cursorIndex === actionIndex
        current: root.markedAddress === candidateRow.candidate.address
        bordered: true
        foreground: root.panelForeground
        enabled: root.hasService && !root.currentView.pending
        opacity: enabled ? 1 : 0.5
        onHasCursorChanged: if (hasCursor)
            Qt.callLater(function () {
                root.keepVisible(candidateRow);
            })

        Accessible.role: Accessible.RadioButton
        Accessible.name: candidateRow.candidate.displayLabel
        Accessible.description: Model.candidateAccessibleDescription(root.hasService, root.currentView.pending === true, candidateRow.candidate.connected)
        Accessible.checkable: true
        Accessible.checked: candidateRow.current
        Accessible.onPressAction: if (candidateRow.enabled)
            root.freebuds.markCandidate(candidateRow.candidate.address)

        Text {
            id: candidateLabel
            anchors.left: parent.left
            anchors.right: candidateStatus.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: Commons.Style.space(10)
            anchors.rightMargin: Commons.Style.space(8)
            text: candidateRow.candidate.displayLabel
            textFormat: Text.PlainText
            color: root.panelForeground
            font.family: root.fontFamily
            font.pixelSize: root.bodyFontSize
            font.bold: parent.current
            elide: Text.ElideRight
            Accessible.ignored: true
        }

        Text {
            id: candidateStatus
            anchors.right: parent.right
            anchors.rightMargin: Commons.Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            text: candidateRow.candidate.connected ? "Connected" : "Disconnected"
            color: candidateRow.candidate.connected ? root.panelForeground : root.panelSecondary
            font.family: root.fontFamily
            font.pixelSize: root.captionFontSize
            font.bold: true
            Accessible.ignored: true
        }

        MouseArea {
            anchors.fill: parent
            enabled: candidateRow.enabled
            hoverEnabled: true
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onContainsMouseChanged: {
                if (containsMouse) {
                    root.setCursor("candidate", candidateRow.candidate.address);
                    Qt.callLater(function () {
                        root.keepVisible(candidateRow);
                    });
                }
            }
            onClicked: root.freebuds.markCandidate(candidateRow.candidate.address)
        }
    }
}
