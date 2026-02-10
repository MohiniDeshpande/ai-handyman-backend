// TTSPlayer.js (Spectacles-safe: chunk + queue)
//@input Component.AudioComponent speaker
//@input Asset.TextToSpeechModule ttsModule
//@input string voiceName = "Sasha"
//@input int voiceStyle = 0
//@input float pace = 1.0

//@input int maxCharsPerChunk = 160   // keep small to avoid 4MB payload
//@input float gapSeconds = 0.05      // tiny pause between chunks
//@input bool debugLogs = true

function log(m) { if (script.debugLogs) print("[TTS] " + m); }

function safeEnglish(text) {
    return (text || "")
        .replace(/[^\x00-\x7F]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function paceToVoicePace(p) {
    if (p <= 0.8) return 75;
    if (p <= 1.1) return 100;
    if (p <= 1.35) return 125;
    return 150;
}

function resolveVoiceName(nameStr) {
    try {
        if (global.TextToSpeech && TextToSpeech.VoiceNames) {
            if (nameStr === "Sam" && TextToSpeech.VoiceNames.Sam) return TextToSpeech.VoiceNames.Sam;
            if (nameStr === "Sasha" && TextToSpeech.VoiceNames.Sasha) return TextToSpeech.VoiceNames.Sasha;
        }
    } catch (e) {}
    return nameStr;
}

function resolveVoiceStyle(styleIndex) {
    try {
        if (styleIndex <= 0) return null;
        if (global.TextToSpeech && TextToSpeech.VoiceStyles) {
            var map = [
                null,
                TextToSpeech.VoiceStyles.One,
                TextToSpeech.VoiceStyles.Two,
                TextToSpeech.VoiceStyles.Three,
                TextToSpeech.VoiceStyles.Four,
                TextToSpeech.VoiceStyles.Five,
                TextToSpeech.VoiceStyles.Six
            ];
            return map[Math.min(styleIndex, 6)] || null;
        }
    } catch (e) {}
    return null;
}

// ---- Hard chunking: sentence split + hard cut fallback ----
function splitIntoChunks(text, maxLen) {
    if (!text) return [];
    if (text.length <= maxLen) return [text];

    var sentences = text.split(/(?<=[\.\!\?\:\;])\s+/);
    var out = [];
    var buf = "";

    function flush() {
        buf = buf.trim();
        if (buf.length) out.push(buf);
        buf = "";
    }

    function pushHard(s) {
        s = s.trim();
        while (s.length > maxLen) {
            out.push(s.substring(0, maxLen).trim());
            s = s.substring(maxLen).trim();
        }
        if (s.length) out.push(s);
    }

    for (var i = 0; i < sentences.length; i++) {
        var s = (sentences[i] || "").trim();
        if (!s) continue;

        if (s.length > maxLen) {
            flush();
            pushHard(s);
            continue;
        }

        if ((buf.length + s.length + 1) > maxLen) {
            flush();
            buf = s;
        } else {
            buf = buf ? (buf + " " + s) : s;
        }
    }

    flush();
    return out;
}

// ---- Queue playback ----
var queue = [];
var busy = false;

function scheduleNext(delaySeconds) {
    var evt = script.createEvent("DelayedCallbackEvent");
    evt.bind(function () {
        busy = false;
        pump();
    });
    evt.reset(Math.max(0.01, delaySeconds));
}

function synthesizeAndPlay(chunk, retryMaxLen) {
    if (!script.speaker) { log("❌ Missing speaker"); busy = false; return; }
    if (!script.ttsModule) { log("❌ Missing ttsModule"); busy = false; return; }

    // absolute guard
    if (chunk.length > retryMaxLen) chunk = chunk.substring(0, retryMaxLen).trim();

    var options = TextToSpeech.Options.create();
    options.voiceName = resolveVoiceName(script.voiceName);
    options.voicePace = paceToVoicePace(script.pace);

    var style = resolveVoiceStyle(script.voiceStyle);
    if (style) options.voiceStyle = style;

    log("-> synthesize chunkLen=" + chunk.length + " remaining=" + queue.length + " max=" + retryMaxLen);

    script.ttsModule.synthesize(
        chunk,
        options,
        function (audioTrackAsset /*, eventArgs */) {
            try {
                script.speaker.audioTrack = audioTrackAsset;
                script.speaker.play(1);
                log("✅ playing chunk (" + chunk.length + " chars)");
            } catch (e) {
                log("❌ play failed: " + e);
            }

            // duration unknown; approximate from text length
            var approxSeconds = Math.max(0.6, chunk.length / 18.0);
            scheduleNext(approxSeconds + script.gapSeconds);
        },
        function (error, description) {
            var desc = "" + description;
            log("❌ synthesize error=" + error + " desc=" + desc);

            // If payload too big OR token too long -> retry smaller
            var tooBig = desc.indexOf("Received message larger than max") !== -1;
            var tooLong = desc.indexOf("maximum sequence length") !== -1;

            if ((tooBig || tooLong) && retryMaxLen > 60) {
                var smaller = Math.max(60, Math.floor(retryMaxLen * 0.6));
                log("↪ retrying smaller chunk size: " + smaller);

                // Put the current chunk back split smaller, then continue
                var re = splitIntoChunks(chunk, smaller);
                queue = re.concat(queue);

                busy = false;
                pump();
                return;
            }

            // give up on this chunk, continue
            busy = false;
            pump();
        }
    );
}

function pump() {
    if (busy) return;
    if (!queue.length) return;

    busy = true;
    var chunk = queue.shift();

    // Use current maxCharsPerChunk as the retry size baseline
    synthesizeAndPlay(chunk, script.maxCharsPerChunk);
}

function speak(text) {
    var input = safeEnglish(text);
    if (!input) { log("⚠️ Empty after sanitize"); return; }

    // IMPORTANT: cap total length too (avoid endless babble)
    if (input.length > 2000) input = input.substring(0, 2000);

    var chunks = splitIntoChunks(input, script.maxCharsPerChunk);
    log("speak() totalLen=" + input.length + " chunks=" + chunks.length);

    // Replace current queue with new request (best for assistant UX)
    queue = chunks;
    busy = false;
    pump();
}

script.api.speak = speak;
