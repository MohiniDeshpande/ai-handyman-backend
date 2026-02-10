// MicStreamer.js
//@input Component.ScriptComponent wsManager
//@input Asset.AudioTrackAsset micTrack {"label":"Mic Audio Track Asset (Microphone Audio)"}
//@input int frameSamples = 1024 {"label":"PCM samples per chunk"}
//@input int targetSampleRate = 16000

var running = false;
var pcm16 = null;
var mic = null;

function log(m) { print("[Mic] " + m); }

function int16ToU8(int16arr) {
    return new Uint8Array(int16arr.buffer, int16arr.byteOffset, int16arr.byteLength);
}

function start() {
    if (!script.wsManager || !script.wsManager.api) { log("Missing WSManager"); return; }
    if (!script.micTrack) { log("Missing micTrack (AudioTrackAsset)"); return; }

    mic = script.micTrack.control;

    if (!mic || !mic.isOfType || !mic.isOfType("Provider.MicrophoneAudioProvider")) {
        log("micTrack.control is NOT a MicrophoneAudioProvider. Make sure the Audio Track Asset is 'Microphone Audio'.");
        return;
    }

    // Configure sample rate
    mic.sampleRate = script.targetSampleRate;

    pcm16 = new Int16Array(script.frameSamples);
    mic.start();
    running = true;

    // Send stream-start header ONCE (performance)
    if (script.wsManager.api.isConnected()) {
        script.wsManager.api.sendJson({
            type: "audio_stream_start",
            format: "pcm16le",
            sampleRate: mic.sampleRate || script.targetSampleRate,
            channels: 1
        });
    }

    log("Started, sampleRate=" + (mic.sampleRate || script.targetSampleRate));
}

function stop() {
    running = false;
    if (mic && mic.stop) mic.stop();

    var wsApi = script.wsManager && script.wsManager.api;
    if (wsApi && wsApi.isConnected()) {
        wsApi.sendJson({ type: "audio_stream_stop" });
    }

    log("Stopped");
}

script.api.start = start;
script.api.stop = stop;

var evt = script.createEvent("UpdateEvent");
evt.bind(function () {
    if (!running || !mic) return;

    var wsApi = script.wsManager.api;
    if (!wsApi.isConnected()) return;

    mic.getAudioFramePCM16(pcm16);
    wsApi.sendBinary(int16ToU8(pcm16));
});
