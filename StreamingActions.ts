@component
export class StreamingActions extends BaseScriptComponent {
  @input bridge: ScriptComponent  // drag HandyBackendBridge here

  private streaming = false

  public StartStreaming() {
    this.streaming = true
    this.bridge?.api?.streamData(true)
    print("[Actions] StartStreaming()")
  }

  public StopStreaming() {
    this.streaming = false
    this.bridge?.api?.streamData(false)
    print("[Actions] StopStreaming()")
  }

  public ToggleStreaming() {
    this.streaming = !this.streaming
    this.bridge?.api?.streamData(this.streaming)
    print("[Actions] ToggleStreaming() -> " + this.streaming)
  }
}
