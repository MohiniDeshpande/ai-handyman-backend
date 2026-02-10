// HandyBackendBridge.ts (TEXT ONLY)
import {AudioProcessor} from "RemoteServiceGateway.lspkg/Helpers/AudioProcessor"
import {MicrophoneRecorder} from "RemoteServiceGateway.lspkg/Helpers/MicrophoneRecorder"
import {VideoController} from "RemoteServiceGateway.lspkg/Helpers/VideoController"

@component
export class HandyBackendBridge extends BaseScriptComponent {
  // ---- WebSocket ----
  @input internetModule: InternetModule
  @input wsUrl: string = "wss://ai-handyman-backend.onrender.com/ws"
  @input websocketRequirementsObj: SceneObject

  // ---- Outputs ----
  @input ttsPlayer: ScriptComponent
  @input aiOutputPanel: ScriptComponent // expects api.showMessage(text: string, isWarning: boolean)

  // ---- Inputs ----
  @input microphoneRecorder: MicrophoneRecorder
  @input haveVideoInput: boolean = true

  // ---- Behavior ----
  @input autoConnect: boolean = true
  @input autoStartVideo: boolean = true
  @input pingSeconds: number = 10.0

  // Logging
  @input logEveryNAudioChunks: number = 10
  @input logEveryNVideoFrames: number = 5
  @input logInboundPreviewChars: number = 260

  private ws: WebSocket | null = null
  private connected: boolean = false

  private videoStreaming: boolean = false
  private audioStreaming: boolean = false

  private lastPingTime: number = 0.0
  private audioChunkCount: number = 0
  private videoFrameCount: number = 0

  private audioProcessor: AudioProcessor = new AudioProcessor()
  private videoController: VideoController = new VideoController(
    1500,
    CompressionQuality.MaximumQuality,
    EncodingType.Jpg
  )

  onAwake(): void {
    if (this.websocketRequirementsObj) this.websocketRequirementsObj.enabled = true

    if (!this.internetModule) {
      print("[Bridge] ❌ Missing InternetModule")
      return
    }
    if (!this.microphoneRecorder) {
      print("[Bridge] ❌ Missing MicrophoneRecorder")
      return
    }

    this.microphoneRecorder.setSampleRate(16000)

    this.setupInputs()

    if (this.autoConnect) {
      this.connectWS()
    } else {
      print("[Bridge] autoConnect=false (call connectWSFromUI())")
    }
  }

  onUpdate(): void {
    if (!this.connected || this.pingSeconds <= 0) return
    const t = getTime()
    if (t - this.lastPingTime > this.pingSeconds) {
      this.lastPingTime = t
      this.sendJson({type: "ping", ts: Date.now()})
    }
  }

  // =========================================================
  // PUBLIC METHODS (wire UI to these)
  // =========================================================
  public connectWSFromUI(): void {
    this.connectWS()
  }

  public disconnectWSFromUI(): void {
    this.disconnect()
  }

  public startAudioFromUI(): void {
    this.startAudio()
  }

  public stopAudioFromUI(): void {
    this.stopAudio()
  }

  // Video continuous by default
  public startVideoFromUI(): void {
    this.startVideo()
  }

  // =========================================================
  // WebSocket
  // =========================================================
  private connectWS(): void {
    if (this.ws && this.connected) {
      print("[Bridge] Already connected")
      return
    }

    print("[Bridge] Connecting WS: " + this.wsUrl)
    this.ws = this.internetModule.createWebSocket(this.wsUrl)

    this.ws.onopen = () => {
      this.connected = true
      this.lastPingTime = getTime()
      print("[Bridge] ✅ WS connected")

      this.sendJson({type: "hello", device: "spectacles", ts: Date.now()})

      if (this.autoStartVideo) this.startVideo()
      print("[Bridge] Audio is manual: startAudioFromUI()/stopAudioFromUI()")
    }

    this.ws.onerror = () => {
      print("[Bridge] ❌ WS error")
    }

    this.ws.onclose = () => {
      print("[Bridge] 🔌 WS closed")
      this.connected = false
      this.ws = null
      this.videoStreaming = false
      this.audioStreaming = false
    }

    this.ws.onmessage = (event) => {
      if (typeof event.data !== "string") return

      let msg: any = null
      try {
        msg = JSON.parse(event.data)
      } catch (e) {
        print("[Bridge] ❌ inbound non-JSON: " + event.data.substring(0, 160))
        return
      }

      const msgType = msg.event || msg.type

      if (msgType !== "pong") {
        const preview = JSON.stringify(msg)
        const n = this.logInboundPreviewChars
        print("[Bridge] <- " + preview.substring(0, n) + (preview.length > n ? "..." : ""))
      }

      if (msgType === "pong") return

      if (msgType === "proactive_warning") {
        this.handleProactiveWarning(msg)
        return
      }

      if (msgType === "ai_result") {
        this.handleAiResult(msg)
        return
      }
    }
  }

  private disconnect(): void {
    try { this.stopAudio() } catch (e) {}
    try { this.stopVideo() } catch (e) {}
    try { this.ws?.close() } catch (e) {}
    this.ws = null
    this.connected = false
  }

  // =========================================================
  // Streaming controls
  // =========================================================
  private startVideo(): void {
    if (!this.connected) {
      print("[Bridge] ⚠️ startVideo: not connected")
      return
    }
    if (!this.haveVideoInput) {
      print("[Bridge] haveVideoInput=false")
      return
    }
    if (this.videoStreaming) return

    this.videoStreaming = true
    this.videoFrameCount = 0
    print("[Bridge] 📷 START video streaming")
    this.videoController.startRecording()
  }

  private stopVideo(): void {
    if (!this.videoStreaming) return
    this.videoStreaming = false
    print("[Bridge] 🛑 STOP video streaming")
    try { this.videoController.stopRecording() } catch (e) {}
  }

  private startAudio(): void {
    if (!this.connected) {
      print("[Bridge] ⚠️ startAudio: not connected")
      return
    }
    if (this.audioStreaming) return

    this.audioStreaming = true
    this.audioChunkCount = 0
    print("[Bridge] 🎙️ START audio streaming")
    this.microphoneRecorder.startRecording()
    this.sendJson({type: "start_capture", ts: Date.now()})
  }

  private stopAudio(): void {
    if (!this.audioStreaming) return
    this.audioStreaming = false
    print("[Bridge] 🛑 STOP audio streaming")
    try { this.microphoneRecorder.stopRecording() } catch (e) {}
    this.sendJson({type: "stop_capture", ts: Date.now()})
  }

  // =========================================================
  // Inputs: audio + video sending
  // =========================================================
  private setupInputs(): void {
    this.audioProcessor.onAudioChunkReady.add((b64: string) => {
      if (!this.connected || !this.audioStreaming) return

      this.audioChunkCount++
      if (this.logEveryNAudioChunks > 0 && this.audioChunkCount % this.logEveryNAudioChunks === 0) {
        print(`[Bridge] -> audio_b64 #${this.audioChunkCount} (b64Len=${b64.length})`)
      }

      this.sendJson({type: "audio_b64", data: b64})
    })

    this.microphoneRecorder.onAudioFrame.add((frame) => {
      this.audioProcessor.processFrame(frame)
    })

    if (this.haveVideoInput) {
      this.videoController.onEncodedFrame.add((b64: string) => {
        if (!this.connected || !this.videoStreaming) return

        this.videoFrameCount++
        if (this.logEveryNVideoFrames > 0 && this.videoFrameCount % this.logEveryNVideoFrames === 0) {
          print(`[Bridge] -> video_b64 #${this.videoFrameCount} (b64Len=${b64.length})`)
        }

        this.sendJson({type: "video_b64", data: b64})
      })
    }
  }

  private sendJson(obj: any): void {
    if (!this.ws || !this.connected) return
    try {
      this.ws.send(JSON.stringify(obj))
    } catch (e) {
      print("[Bridge] ❌ sendJson failed: " + e)
    }
  }

  // =========================================================
  // Inbound handlers (TEXT ONLY)
  // =========================================================
  private handleProactiveWarning(msg: any): void {
    const d = msg.data || {}
    const warningText = (d.message || d.text || "Safety warning.").toString()

    print("[Bridge] 🚨 proactive_warning received")

    const uiText = this.clampLen(warningText, 500)
    this.aiOutputPanel?.api?.showMessage?.(uiText, true)

    const ttsText = this.clampLen(this.sanitizeForTts(warningText), 220)
    this.ttsPlayer?.api?.speak?.(ttsText)
  }

  private handleAiResult(msg: any): void {
    const d = msg.data || {}
    let text = (d.speech_text || d.text || "").toString()

    // If combined format, extract spoken section
    if (text.indexOf("SPOKEN_TEXT:") !== -1) {
      const spoken = this.extractSection(text, "SPOKEN_TEXT:", "CUES:")
      if (spoken) text = spoken
    }

    if (!text || text.trim().length === 0) {
      print("[Bridge] ⚠️ ai_result had empty text")
      return
    }

    print("[Bridge] ✅ ai_result received (len=" + text.length + ")")

    // UI panel: allow longer
    this.aiOutputPanel?.api?.showMessage?.(this.clampLen(text, 900), false)

    // TTS: keep safely short
    const ttsText = this.clampLen(this.sanitizeForTts(text), 280)
    this.ttsPlayer?.api?.speak?.(ttsText)
  }

  // =========================================================
  // Text helpers
  // =========================================================
  private extractSection(full: string, start: string, end: string): string {
    const s = full.indexOf(start)
    if (s === -1) return ""
    const from = s + start.length
    const e = full.indexOf(end, from)
    const chunk = (e === -1 ? full.substring(from) : full.substring(from, e))
    return chunk.trim()
  }

  private sanitizeForTts(t: string): string {
    return (t || "")
      .replace(/[^\x00-\x7F]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
  }

  private clampLen(t: string, max: number): string {
    if (!t) return ""
    if (t.length <= max) return t
    return t.substring(0, max - 3).trim() + "..."
  }
}