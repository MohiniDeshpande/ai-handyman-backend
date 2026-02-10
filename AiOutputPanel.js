// AIOutputPanel.js
//@input SceneObject normalPlateObj
//@input SceneObject warningPlateObj
//@input Component textComponent
//@input int maxChars = 900
//@input bool startHidden = false
//@input float autoHideSeconds = 0

var hideAt = 0;

function log(m){ print("[AIOutputPanel] " + m); }

function clampText(t, max){
    t = (t || "");
    if (t.length <= max) return t;
    return t.substring(0, max - 3).trim() + "...";
}

function setVisible(visible, isWarning){
    if (script.normalPlateObj) script.normalPlateObj.enabled = visible && !isWarning;
    if (script.warningPlateObj) script.warningPlateObj.enabled = visible && isWarning;

    // keep text visible when panel visible
    if (script.textComponent && script.textComponent.getSceneObject) {
        script.textComponent.getSceneObject().enabled = visible;
    }
}

function setText(text){
    var tc = script.textComponent;
    if (!tc) { log("Missing textComponent"); return; }

    try {
        // Most LS text components have .text
        if (tc.text !== undefined) {
            tc.text = text;
            return;
        }
        // Some have setText()
        if (tc.setText) {
            tc.setText(text);
            return;
        }
        log("Text component has no .text or .setText");
    } catch (e) {
        log("setText failed: " + e);
    }
}

function decorateWarning(t){
    return "SAFETY\n" + t;
}

function showMessage(text, isWarning){
    var t = clampText(text, script.maxChars);
    setVisible(true, !!isWarning);
    setText(isWarning ? decorateWarning(t) : t);

    if (script.autoHideSeconds > 0){
        hideAt = getTime() + script.autoHideSeconds;
    } else {
        hideAt = 0;
    }
}

function hide(){
    setVisible(false, false);
    hideAt = 0;
}

var updateEvt = script.createEvent("UpdateEvent");
updateEvt.bind(function(){
    if (hideAt > 0 && getTime() >= hideAt){
        hide();
    }
});

// Init
if (script.startHidden) hide();
else setVisible(true, false);

// API
script.api.showMessage = showMessage;
script.api.hide = hide;