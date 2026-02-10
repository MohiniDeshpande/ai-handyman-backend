// SpectaclesWSClient.js
//@input Asset.InternetModule internetModule
//@input string wsUrl = "wss://AI_handyman.onrender.com/ws/spectacles"
//@input Component.ScriptComponent pcmPlayer
//@input float reconnectSeconds = 1.5
//@input float heartbeatSeconds = 10.0

var socket = null;
var connected = false;

// We expect: header (text JSON) then payload (binary blob)
var pendingHeader = null;
var pendingHeaderSetAt = 0.0;
var PENDING_HEADER_TIMEOUT = 2.0;

// queue messages while connecting/reconnecting
var outbox = []; // { data: string|Uint8Array }

function log(m) { print("[WS] " + m); }

function flushOutbox() {
    if (!socket || !connected) return;
    while (outbox.length > 0) {
        var item = outbox.shift();
        socket.send(item.data);
    }
}

function enqueueSendText(str) {
    if (socket && connected) socket.send(str);
    else outbox.push({ data: str });
}

function enqueueSendBinary(u8) {
    if (socket && connected) socket.send(u8);
    else outbox.push({ data: u8 });
}

function connect() {
    if (!script.internetModule) {
        log("ERROR: InternetModule not assigned.");
        return;
    }

    log("Connecting to " + script.wsUrl);
    socket = script.internetModule.createWebSocket(script.wsUrl);
    socket.binaryType = "blob";

    socket.onopen = function () {
        connected = true;
        log("Connected ✅");

        // Hello handshake (optional)
        sendJson({
            type: "hello",
            sessionId: "spectacles-demo",
            device: "spectacles",
            ts: Date.now()
        });

        flushOutbox();
    };

    socket.onmessage = async function (event) {
        try {
            var data = event.data;

            // TEXT message = JSON header
            if (typeof data === "string") {
                try {
                    pendingHeader = JSON.parse(data);
                    pendingHeaderSetAt = getTime();
                } catch (e) {
                    log("Got non-JSON text: " + data.substring(0, 80));
                    pendingHeader = null;
                }
                return;
            }

            // BINARY message = Blob
            if (data instanceof Blob) {
                if (!pendingHeader) {
                    log("Binary received without header (ignored)");
                    return;
                }

                var u8 = await data.bytes();

                if (pendingHeader.type === "audio_out") {
                    var sr = pendingHeader.sampleRate || 24000;
                    if (script.pcmPlayer && script.pcmPlayer.api && script.pcmPlayer.api.pushPcmBytes) {
                        script.pcmPlayer.api.pushPcmBytes(u8, sr);
                    } else {
                        log("audio_out bytes=" + u8.length + " (no pcmPlayer wired)");
                    }
                } else if (pendingHeader.type === "pong") {
                    // ignore
                } else {
                    log("Binary for type=" + pendingHeader.type + " bytes=" + u8.length);
                }

                pendingHeader = null;
                return;
            }

            log("Unknown message type received");
        } catch (err) {
            log("onmessage error: " + err);
        }
    };

    socket.onerror = function () { log("WebSocket error ❌"); };

    socket.onclose = function () {
        log("Disconnected. Reconnecting in " + script.reconnectSeconds + "s…");
        connected = false;
        pendingHeader = null;

        var delayed = script.createEvent("DelayedCallbackEvent");
        delayed.bind(function () { connect(); });
        delayed.reset(script.reconnectSeconds);
    };
}

function sendJson(obj) {
    enqueueSendText(JSON.stringify(obj));
}

function sendBinary(u8) {
    enqueueSendBinary(u8);
}

script.api.sendJson = sendJson;
script.api.sendBinary = sendBinary;
script.api.isConnected = function () { return connected; };

// Heartbeat + pendingHeader timeout watchdog
var updateEvt = script.createEvent("UpdateEvent");
var lastHeartbeat = 0.0;

updateEvt.bind(function () {
    var t = getTime();

    if (pendingHeader && (t - pendingHeaderSetAt) > PENDING_HEADER_TIMEOUT) {
        log("Pending header timed out; clearing");
        pendingHeader = null;
    }

    if (connected && (t - lastHeartbeat) > script.heartbeatSeconds) {
        lastHeartbeat = t;
        sendJson({ type: "ping", ts: Date.now() });
    }
});

connect();
