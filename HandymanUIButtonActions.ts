@component
export class HandybotUIButtonActions extends BaseScriptComponent {
  public startTalk(): void {
    if (!(global as any).HANDYBOT_AUDIO_START) {
      print("[UI] ❌ HANDYBOT_AUDIO_START not found (bridge not awake?)")
      return
    }
    print("[UI] StartTalk pressed")
    ;(global as any).HANDYBOT_AUDIO_START()
  }

  public stopTalk(): void {
    if (!(global as any).HANDYBOT_AUDIO_STOP) {
      print("[UI] ❌ HANDYBOT_AUDIO_STOP not found (bridge not awake?)")
      return
    }
    print("[UI] StopTalk pressed")
    ;(global as any).HANDYBOT_AUDIO_STOP()
  }

  public toggleTalk(): void {
    if (!(global as any).HANDYBOT_AUDIO_TOGGLE) {
      print("[UI] ❌ HANDYBOT_AUDIO_TOGGLE not found (bridge not awake?)")
      return
    }
    print("[UI] ToggleTalk pressed")
    ;(global as any).HANDYBOT_AUDIO_TOGGLE()
  }
}
