// AIOutputPanel.ts
// Exposes: script.api.showMessage(text: string, isWarning: boolean)

@component
export class AIOutputPanel extends BaseScriptComponent {
  // Assign scene objects that have BackPlate component on them
  @input normalPlateObj: SceneObject
  @input warningPlateObj: SceneObject

  // Assign a Text component (Text or ScreenText) that is visible in Spectacles
  // In Lens Studio, use a Text component on a child object.
  @input textComponent: Component

  @input maxChars: number = 900
  @input autoShow: boolean = true

  // Optional: auto-hide after N seconds (0 disables)
  @input autoHideSeconds: number = 0

  // Internal
  private hideAt: number = 0

  onAwake(): void {
    // Start hidden unless autoShow
    if (!this.autoShow) {
      this.setVisible(false, false)
    } else {
      // show normal by default
      this.setVisible(true, false)
    }

    // Expose API expected by HandyBackendBridge.ts
    // IMPORTANT: In TS components, you expose through this.script.api (Lens Studio supports it),
    // but ONLY after awake/start. So do it inside onAwake.
    ;(this as any).api = {
      showMessage: (text: string, isWarning: boolean) => this.showMessage(text, isWarning),
      hide: () => this.setVisible(false, false),
      showNormal: () => this.setVisible(true, false),
      showWarning: () => this.setVisible(true, true),
    }
  }

  onUpdate(): void {
    if (this.autoHideSeconds <= 0) return
    if (this.hideAt <= 0) return
    if (getTime() >= this.hideAt) {
      this.hideAt = 0
      this.setVisible(false, false)
    }
  }

  private showMessage(text: string, isWarning: boolean): void {
    const clean = this.clamp(text || "", this.maxChars)

    // Toggle which plate is visible
    this.setVisible(true, isWarning)

    // Update text
    this.setText(isWarning ? this.decorateWarning(clean) : clean)

    // auto hide timer
    if (this.autoHideSeconds > 0) {
      this.hideAt = getTime() + this.autoHideSeconds
    }
  }

  private setVisible(visible: boolean, warning: boolean): void {
    if (this.normalPlateObj) this.normalPlateObj.enabled = visible && !warning
    if (this.warningPlateObj) this.warningPlateObj.enabled = visible && warning

    // Also make sure text object is enabled (some setups put text under one plate)
    // If your Text is a child under normalPlate only, move it to a shared parent.
    const tcSo = this.getTextSceneObject()
    if (tcSo) tcSo.enabled = visible
  }

  private setText(text: string): void {
    // Supports both Text and ScreenText style components:
    // - Some builds expose .text
    // - Some use .setText()
    const tc: any = this.textComponent as any
    if (!tc) return

    try {
      if (typeof tc.text === "string") tc.text = text
      else if (typeof tc.setText === "function") tc.setText(text)
      else print("[AIOutputPanel] ⚠️ Text component has no .text or .setText")
    } catch (e) {
      print("[AIOutputPanel] ❌ setText failed: " + e)
    }
  }

  private getTextSceneObject(): SceneObject | null {
    // Some components expose getSceneObject()
    const tc: any = this.textComponent as any
    try {
      if (tc && typeof tc.getSceneObject === "function") return tc.getSceneObject()
    } catch (e) {}
    return null
  }

  private decorateWarning(text: string): string {
    // Keep it simple + visible
    // Don’t spam — this shows on UI, TTS already speaks the warning.
    return "SAFETY\n" + text
  }

  private clamp(t: string, max: number): string {
    if (!t) return ""
    if (t.length <= max) return t
    return t.substring(0, max - 3).trim() + "..."
  }
}