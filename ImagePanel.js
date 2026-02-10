// ImagePanel.js
//@input Component.Image imageView

function showBase64Image(mimeType, b64) {
    if (!script.imageView) return;

    // Create texture via the Image component’s mainPass if available
    try {
        var tex = script.imageView.mainMaterial.mainPass.baseTex;
        if (!tex) {
            // Create an empty texture asset instance if the build allows
            tex = new Texture();
        }
        tex.loadBase64(b64);
        script.imageView.mainMaterial.mainPass.baseTex = tex;
        script.imageView.enabled = true;
    } catch (e) {
        print("[ImagePanel] ❌ showBase64Image failed: " + e);
    }
}

function hide() {
    if (script.imageView) script.imageView.enabled = false;
}

script.api.showBase64Image = showBase64Image;
script.api.hide = hide;