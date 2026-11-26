import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const STYLE_ID = "h3-context-studio-styles";

function injectStyles() {
    const existing = document.getElementById(STYLE_ID);
    if (existing) existing.remove();
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
.h3cs-root {
    display: flex; flex-direction: column; gap: 6px;
    background: #14161b; color: #e2e6ef; border: 1px solid #2b303b;
    border-radius: 6px; padding: 8px; font-family: ui-sans-serif, system-ui, sans-serif;
    font-size: 11px; user-select: none; box-sizing: border-box; width: 100%; height: 100%;
    min-width: 0; min-height: 0; overflow: hidden;
}
.h3cs-video-wrap {
    position: relative; background: #0a0b0e; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    flex: 1 1 auto; min-height: 160px; min-width: 0; width: 100%;
    overflow: hidden; border: 1px solid #232730;
}
.h3cs-video-wrap video {
    position: absolute; inset: 0;
    width: 100%; height: 100%; object-fit: contain; display: block;
}
.h3cs-video-empty {
    color: #6f7787; font-size: 11px; text-align: center; padding: 8px;
}
.h3cs-transport {
    display: flex; align-items: center; gap: 5px; flex-wrap: wrap;
    flex: 0 0 auto;
}
.h3cs-btn {
    background: #232833; color: #dce2ee; border: 1px solid #353c4a;
    border-radius: 4px; padding: 3px 7px; font-size: 11px; cursor: pointer;
    line-height: 1.2;
}
.h3cs-btn:hover { background: #2f3645; border-color: #4a5468; }
.h3cs-btn.primary { background: #2a528a; border-color: #3f72ba; }
.h3cs-btn.primary:hover { background: #3566ab; }
.h3cs-btn.danger { background: #5a262c; border-color: #823840; }
.h3cs-select {
    background: #1a1f29; color: #dce2ee; border: 1px solid #353c4a;
    border-radius: 4px; padding: 2px 6px; font-size: 11px; max-width: 170px;
    cursor: pointer; outline: none;
}
.h3cs-select:hover { border-color: #4a5468; }
.h3cs-readout {
    margin-left: auto; font-family: ui-monospace, Consolas, monospace;
    color: #9fb0cc; font-size: 11px;
}
.h3cs-track-box {
    background: #0f1116; border: 1px solid #252a34; border-radius: 4px;
    padding: 4px 6px; display: flex; flex-direction: column; gap: 4px;
    flex: 0 0 auto;
}
.h3cs-track-label {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; color: #8c96ab; text-transform: uppercase; letter-spacing: 0.04em;
}
.h3cs-timeline-scroll {
    overflow-x: auto; overflow-y: hidden; position: relative; padding-bottom: 2px;
}
.h3cs-ruler {
    position: relative; height: 18px; border-bottom: 1px solid #262b36;
    cursor: ew-resize;
}
.h3cs-tick {
    position: absolute; top: 0; bottom: 0; border-left: 1px solid #2c3340;
    font-size: 9px; color: #788296; padding-left: 2px; pointer-events: none;
}
.h3cs-playhead {
    position: absolute; top: 0; bottom: 0; width: 2px; background: #ff5c5c;
    pointer-events: none; z-index: 20;
}
.h3cs-chunks-row {
    position: relative; height: 30px; margin-top: 2px;
}
.h3cs-f0 {
    position: absolute; top: 2px; bottom: 2px; background: #2d3444;
    border: 1px solid #485268; border-radius: 3px; color: #b7c2d6;
    display: flex; align-items: center; justify-content: center;
    font-size: 9px; font-weight: 600; box-sizing: border-box; cursor: pointer;
}
.h3cs-chunk {
    position: absolute; top: 2px; bottom: 2px; border-radius: 3px;
    border: 1px solid rgba(255,255,255,0.18); box-sizing: border-box;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 600; color: #fff; cursor: pointer;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.h3cs-chunk.selected {
    outline: 2px solid #ffd166; outline-offset: -1px; z-index: 6;
}
.h3cs-chunk.focused {
    outline: 2px solid #ffffff; outline-offset: -1px; z-index: 7;
}
.h3cs-handle {
    position: absolute; top: 0; bottom: 0; width: 10px; margin-left: -5px;
    cursor: col-resize; z-index: 15; display: flex; align-items: center; justify-content: center;
}
.h3cs-handle::after {
    content: ""; width: 2px; height: 74%; background: rgba(255,255,255,0.6); border-radius: 1px;
}
.h3cs-handle:hover::after { background: #ffd166; width: 3px; }
.h3cs-iso-row {
    position: relative; height: 30px; margin-top: 2px;
}
.h3cs-iso-seg {
    position: absolute; top: 2px; bottom: 2px; border-radius: 3px;
    box-sizing: border-box; display: flex; align-items: center; justify-content: center;
    font-size: 9px; font-weight: 600; color: #eef3fb; overflow: hidden;
    border: 1px solid rgba(255,255,255,0.16); cursor: pointer;
}
.h3cs-iso-lead { background: #26547c; }
.h3cs-iso-bb   { background: #1b8a8f; }
.h3cs-iso-tgt  { background: #2d8a4e; }
.h3cs-iso-ba   { background: #1b8a8f; }
.h3cs-iso-tail { background: #b5651d; }
.h3cs-inspector {
    background: #101319; border: 1px solid #252a34; border-radius: 4px;
    padding: 6px 8px; display: flex; flex-direction: column; gap: 6px;
    flex: 0 0 auto;
}
.h3cs-insp-header {
    display: flex; justify-content: space-between; align-items: center; gap: 6px;
    flex-wrap: wrap; font-weight: 600; color: #dbe4f3; font-size: 11px;
}
.h3cs-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px;
}
.h3cs-field {
    display: flex; flex-direction: column; gap: 2px; background: #181c24;
    padding: 4px 5px; border-radius: 4px; border: 1px solid #262c38;
}
.h3cs-field label { font-size: 9px; color: #8f9bb3; text-transform: uppercase; }
.h3cs-field input[type="number"], .h3cs-field input[type="range"] {
    width: 100%; box-sizing: border-box;
}
.h3cs-field input[type="number"] {
    background: #0e1015; color: #eef2fa; border: 1px solid #303746;
    border-radius: 3px; padding: 2px 4px; font-size: 11px;
    -moz-appearance: textfield;
}
.h3cs-field input[type="number"]::-webkit-outer-spin-button,
.h3cs-field input[type="number"]::-webkit-inner-spin-button {
    -webkit-appearance: none; margin: 0;
}
.h3cs-stepper {
    display: flex; align-items: stretch; gap: 3px;
}
.h3cs-step-btn {
    background: #262c38; color: #e8eef9; border: 1px solid #3a4354;
    border-radius: 3px; min-width: 24px; height: 24px; font-size: 14px;
    font-weight: 700; line-height: 1; cursor: pointer; display: flex;
    align-items: center; justify-content: center; flex: 0 0 auto;
}
.h3cs-step-btn:hover { background: #343d4f; border-color: #53607a; }
.h3cs-stepper input[type="number"] {
    text-align: center; min-width: 0; flex: 1 1 auto; height: 24px;
}
.h3cs-val-row {
    display: flex; justify-content: space-between; align-items: center; gap: 4px;
}
.h3cs-val-input {
    width: 48px !important; text-align: right;
    font-family: ui-monospace, Consolas, monospace; font-size: 10px !important;
    padding: 1px 3px !important; color: #cfe0ff !important;
}
.h3cs-legend {
    display: flex; gap: 8px; font-size: 9px; color: #96a1b5; align-items: center;
}
.h3cs-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; margin-right: 3px; }
.h3cs-json-drawer {
    display: none; flex-direction: column; gap: 4px; margin-top: 2px;
}
.h3cs-json-drawer.open { display: flex; }
.h3cs-json-drawer textarea {
    width: 100%; height: 84px; box-sizing: border-box;
    background: #0b0d12; color: #b8c7e0; border: 1px solid #2b3240;
    border-radius: 4px; padding: 5px; font-family: ui-monospace, Consolas, monospace;
    font-size: 10px; resize: vertical; user-select: text;
}
`;
    document.head.appendChild(style);
}

const CHUNK_COLORS = [
    "#326899", "#3b7a62", "#6e5599", "#8c6239", "#3c788a", "#7a4b6e", "#4b7a3f", "#8a5a44",
];

function buildDefaultChunks(nFrames, preserveFirst, defaultCommit) {
    const start = preserveFirst && nFrames > 1 ? 1 : 0;
    const step = Math.max(1, defaultCommit || 4);
    const chunks = [];
    for (let t0 = start; t0 < nFrames; t0 += step) {
        const t1 = Math.min(nFrames, t0 + step);
        chunks.push({
            commit_start: t0,
            commit_end: t1,
            context_before: 2,
            buffer_before: 0,
            buffer_after: 0,
            context_after: 2,
            lead_start_denoise: 0.0,
            lead_end_denoise: 0.0,
            tail_start_denoise: 0.0,
            tail_end_denoise: 0.0,
            chunk_denoise: 1.0,
            cond_index: -1,
        });
    }
    return chunks;
}

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

/**
 * Convert mouse clientX to unscaled CSS pixels inside `el`, compensating for LiteGraph canvas zoom!
 */
function clientXToLocalPx(el, clientX) {
    const rect = el.getBoundingClientRect();
    const scaleX = rect.width / Math.max(1, el.offsetWidth);
    return (clientX - rect.left) / (scaleX > 0 ? scaleX : 1);
}

function hideScheduleWidget(widget) {
    if (!widget) return;
    widget.type = "hidden";
    widget.serialize = true;
    widget.computeSize = () => [0, -4];
    widget.draw = () => {};
    if (widget.inputEl) {
        widget.inputEl.style.display = "none";
    }
}

function createStudioUI(node) {
    injectStyles();

    const state = {
        frameCount: 36,
        fps: 24.0,
        currentFrame: 0,
        preserveFirst: true,
        defaultCommit: 4,
        chunks: [],
        selected: new Set([0]),
        focused: 0,
        lastClicked: 0,
        pxPerFrame: 18,
    };

    const getWidget = (name) => node.widgets?.find((w) => w.name === name);
    const getVideoFileWidget = () => getWidget("video_file") || getWidget("video");
    const isUpstreamSentinel = (v) => !v || v === "(upstream input)" || v === "(upstream images)";
    hideScheduleWidget(getWidget("schedule_json"));

    // --- Build DOM ---
    const root = document.createElement("div");
    root.className = "h3cs-root";

    // Hidden native file input for OS file explorer video picker
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v";
    fileInput.style.display = "none";
    root.appendChild(fileInput);

    // 1. Video preview (flex: 1 1 auto -> absorbs all extra height on node resize!)
    const videoWrap = document.createElement("div");
    videoWrap.className = "h3cs-video-wrap";
    const videoEl = document.createElement("video");
    videoEl.muted = true;
    videoEl.playsInline = true;
    videoEl.preload = "auto";
    videoEl.style.display = "none";
    const emptyMsg = document.createElement("div");
    emptyMsg.className = "h3cs-video-empty";
    emptyMsg.textContent = "Click 'Browse Video' or pick from the dropdown (or run once with upstream images) to preview & scrub.";
    videoWrap.appendChild(videoEl);
    videoWrap.appendChild(emptyMsg);
    root.appendChild(videoWrap);

    // 2. Transport & chunk actions
    const transport = document.createElement("div");
    transport.className = "h3cs-transport";
    const btnBrowse = document.createElement("button");
    btnBrowse.className = "h3cs-btn primary";
    btnBrowse.textContent = "📂 Browse Video";
    btnBrowse.title = "Open file explorer to pick & upload a video into ComfyUI/input";
    const btnClearVideo = document.createElement("button");
    btnClearVideo.className = "h3cs-btn";
    btnClearVideo.textContent = "✕ Clear";
    btnClearVideo.title = "Clear selected video file so upstream 'images' input is used";
    const btnPlay = document.createElement("button");
    btnPlay.className = "h3cs-btn";
    btnPlay.textContent = "▶ Play";
    const btnPrev = document.createElement("button");
    btnPrev.className = "h3cs-btn";
    btnPrev.textContent = "◀ -1f";
    const btnNext = document.createElement("button");
    btnNext.className = "h3cs-btn";
    btnNext.textContent = "+1f ▶";
    const btnSplit = document.createElement("button");
    btnSplit.className = "h3cs-btn";
    btnSplit.textContent = "Split @ Frame";
    const btnMerge = document.createElement("button");
    btnMerge.className = "h3cs-btn";
    btnMerge.textContent = "Merge Sel";
    const btnSelAll = document.createElement("button");
    btnSelAll.className = "h3cs-btn";
    btnSelAll.textContent = "Select All";
    const btnReset = document.createElement("button");
    btnReset.className = "h3cs-btn danger";
    btnReset.textContent = "Auto-Split";
    const readout = document.createElement("span");
    readout.className = "h3cs-readout";
    transport.append(btnBrowse, btnClearVideo, btnPlay, btnPrev, btnNext, btnSplit, btnMerge, btnSelAll, btnReset, readout);
    root.appendChild(transport);

    // 3. Committed chunks timeline
    const mainTrackBox = document.createElement("div");
    mainTrackBox.className = "h3cs-track-box";
    const mainLabel = document.createElement("div");
    mainLabel.className = "h3cs-track-label";
    mainLabel.innerHTML = `<span>Committed Chunks (drag edges • Click=isolate • Ctrl/Shift=multi-select)</span>`;
    const mainScroll = document.createElement("div");
    mainScroll.className = "h3cs-timeline-scroll";
    const mainInner = document.createElement("div");
    mainInner.style.position = "relative";
    const ruler = document.createElement("div");
    ruler.className = "h3cs-ruler";
    const chunksRow = document.createElement("div");
    chunksRow.className = "h3cs-chunks-row";
    const playheadMain = document.createElement("div");
    playheadMain.className = "h3cs-playhead";
    mainInner.append(ruler, chunksRow, playheadMain);
    mainScroll.appendChild(mainInner);
    mainTrackBox.append(mainLabel, mainScroll);
    root.appendChild(mainTrackBox);

    // 4. Isolated chunk window track
    const isoTrackBox = document.createElement("div");
    isoTrackBox.className = "h3cs-track-box";
    const isoLabel = document.createElement("div");
    isoLabel.className = "h3cs-track-label";
    const isoTitle = document.createElement("span");
    const isoLegend = document.createElement("span");
    isoLegend.className = "h3cs-legend";
    isoLegend.innerHTML =
        `<span><i class="h3cs-dot" style="background:#26547c"></i>Ctx Before</span>` +
        `<span><i class="h3cs-dot" style="background:#1b8a8f"></i>Buffer</span>` +
        `<span><i class="h3cs-dot" style="background:#2d8a4e"></i>Commit</span>` +
        `<span><i class="h3cs-dot" style="background:#b5651d"></i>Ctx After</span>`;
    isoLabel.append(isoTitle, isoLegend);
    const isoScroll = document.createElement("div");
    isoScroll.className = "h3cs-timeline-scroll";
    const isoInner = document.createElement("div");
    isoInner.style.position = "relative";
    const isoRow = document.createElement("div");
    isoRow.className = "h3cs-iso-row";
    const playheadIso = document.createElement("div");
    playheadIso.className = "h3cs-playhead";
    isoInner.append(isoRow, playheadIso);
    isoScroll.appendChild(isoInner);
    isoTrackBox.append(isoLabel, isoScroll);
    root.appendChild(isoTrackBox);

    mainScroll.addEventListener("scroll", () => { isoScroll.scrollLeft = mainScroll.scrollLeft; });
    isoScroll.addEventListener("scroll", () => { mainScroll.scrollLeft = isoScroll.scrollLeft; });

    // 5. Inspector / batch editor + collapsible Advanced JSON drawer
    const inspector = document.createElement("div");
    inspector.className = "h3cs-inspector";
    const inspHeader = document.createElement("div");
    inspHeader.className = "h3cs-insp-header";
    const inspTitle = document.createElement("span");
    const presetBar = document.createElement("div");
    presetBar.style.display = "flex";
    presetBar.style.gap = "4px";
    presetBar.style.flexWrap = "wrap";
    presetBar.style.alignItems = "center";

    let userPresets = {};
    const presetSelect = document.createElement("select");
    presetSelect.className = "h3cs-select";
    presetSelect.title = "User presets (saved in ComfyUI/user/h3_context_studio_presets.json, safe across node updates)";

    const btnPresetApply = document.createElement("button");
    btnPresetApply.className = "h3cs-btn primary";
    btnPresetApply.textContent = "Apply";
    btnPresetApply.title = "Apply selected preset to all selected chunk(s)";

    const btnPresetSave = document.createElement("button");
    btnPresetSave.className = "h3cs-btn";
    btnPresetSave.textContent = "💾 Save";
    btnPresetSave.title = "Save current chunk settings as a reusable user preset";

    const btnPresetDel = document.createElement("button");
    btnPresetDel.className = "h3cs-btn danger";
    btnPresetDel.textContent = "🗑";
    btnPresetDel.title = "Delete selected user preset (click twice to confirm)";

    const presetStatus = document.createElement("span");
    presetStatus.style.fontSize = "10px";
    presetStatus.style.color = "#8fd19e";
    let statusTimer = null;
    function flashStatus(msg, isErr = false) {
        presetStatus.textContent = msg;
        presetStatus.style.color = isErr ? "#ff8c8c" : "#8fd19e";
        if (statusTimer) clearTimeout(statusTimer);
        statusTimer = setTimeout(() => { presetStatus.textContent = ""; }, 2600);
    }

    // Inline save bar (no window.prompt — works in ComfyUI Desktop Electron & all browsers!)
    const saveBar = document.createElement("div");
    saveBar.style.display = "none";
    saveBar.style.alignItems = "center";
    saveBar.style.gap = "4px";
    saveBar.style.background = "#181c24";
    saveBar.style.border = "1px solid #353c4a";
    saveBar.style.borderRadius = "4px";
    saveBar.style.padding = "4px 6px";
    const saveLabel = document.createElement("span");
    saveLabel.textContent = "Preset name:";
    saveLabel.style.color = "#9fb0cc";
    saveLabel.style.fontSize = "10px";
    const saveNameInp = document.createElement("input");
    saveNameInp.type = "text";
    saveNameInp.placeholder = "Enter preset name...";
    saveNameInp.style.flex = "1 1 auto";
    saveNameInp.style.background = "#0e1015";
    saveNameInp.style.color = "#eef2fa";
    saveNameInp.style.border = "1px solid #3f72ba";
    saveNameInp.style.borderRadius = "3px";
    saveNameInp.style.padding = "3px 6px";
    saveNameInp.style.fontSize = "11px";
    saveNameInp.style.userSelect = "text";
    const btnSaveConfirm = document.createElement("button");
    btnSaveConfirm.className = "h3cs-btn primary";
    btnSaveConfirm.textContent = "✓ Save";
    const btnSaveCancel = document.createElement("button");
    btnSaveCancel.className = "h3cs-btn";
    btnSaveCancel.textContent = "✕";
    saveBar.append(saveLabel, saveNameInp, btnSaveConfirm, btnSaveCancel);

    const btnJsonToggle = document.createElement("button");
    btnJsonToggle.className = "h3cs-btn";
    btnJsonToggle.textContent = "{ } JSON";
    btnJsonToggle.title = "Show/hide raw schedule JSON";

    function renderPresetOptions(selectName = null) {
        const prev = selectName ?? presetSelect.value;
        presetSelect.innerHTML = "";
        const names = Object.keys(userPresets);
        if (names.length === 0) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "(no presets)";
            presetSelect.appendChild(opt);
            return;
        }
        for (const name of names) {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            presetSelect.appendChild(opt);
        }
        if (prev && names.includes(prev)) {
            presetSelect.value = prev;
        }
    }

    async function fetchPresets(selectName = null) {
        try {
            const resp = await api.fetchApi("/h3_context_studio/presets");
            const data = await resp.json();
            if (data && data.ok && data.presets) {
                userPresets = data.presets;
                renderPresetOptions(selectName);
            }
        } catch (err) {
            console.warn("H3 Re-Time Context Studio: could not load presets", err);
        }
    }

    btnPresetApply.onclick = () => {
        const name = presetSelect.value;
        if (!name || !userPresets[name]) return;
        applyToSelected(normalizeChunk(userPresets[name]));
        flashStatus(`Applied "${name}"`);
    };

    async function commitSavePreset() {
        const ch = state.chunks[state.focused];
        if (!ch) return;
        const cleanName = saveNameInp.value.trim();
        if (!cleanName) {
            flashStatus("Enter a name", true);
            saveNameInp.focus();
            return;
        }
        const values = {
            context_before: ch.context_before,
            buffer_before: ch.buffer_before,
            buffer_after: ch.buffer_after,
            context_after: ch.context_after,
            chunk_denoise: ch.chunk_denoise == null ? 1.0 : Number(ch.chunk_denoise),
            lead_start_denoise: ch.lead_start_denoise == null ? 0.0 : Number(ch.lead_start_denoise),
            lead_end_denoise: ch.lead_end_denoise == null ? 0.0 : Number(ch.lead_end_denoise),
            tail_start_denoise: ch.tail_start_denoise == null ? 0.0 : Number(ch.tail_start_denoise),
            tail_end_denoise: ch.tail_end_denoise == null ? 0.0 : Number(ch.tail_end_denoise),
            cond_index: ch.cond_index == null ? -1 : parseInt(ch.cond_index, 10),
        };
        try {
            const resp = await api.fetchApi("/h3_context_studio/presets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "save", name: cleanName, values }),
            });
            const data = await resp.json();
            if (data && data.ok && data.presets) {
                userPresets = data.presets;
                renderPresetOptions(cleanName);
                saveBar.style.display = "none";
                flashStatus(`Saved "${cleanName}"`);
            } else {
                flashStatus(data?.error || "Save failed", true);
            }
        } catch (err) {
            flashStatus(`Save error: ${err.message}`, true);
        }
    }

    btnPresetSave.onclick = () => {
        const isOpen = saveBar.style.display === "flex";
        if (isOpen) {
            saveBar.style.display = "none";
            return;
        }
        saveNameInp.value = presetSelect.value || "My Preset";
        saveBar.style.display = "flex";
        saveNameInp.focus();
        saveNameInp.select();
    };
    btnSaveConfirm.onclick = () => commitSavePreset();
    btnSaveCancel.onclick = () => { saveBar.style.display = "none"; };
    saveNameInp.addEventListener("keydown", (ev) => {
        ev.stopPropagation();
        if (ev.key === "Enter") { ev.preventDefault(); commitSavePreset(); }
        else if (ev.key === "Escape") { ev.preventDefault(); saveBar.style.display = "none"; }
    });

    let delConfirmName = null;
    let delConfirmTimer = null;
    btnPresetDel.onclick = async () => {
        const name = presetSelect.value;
        if (!name || !userPresets[name]) return;
        if (delConfirmName !== name) {
            delConfirmName = name;
            btnPresetDel.textContent = "Confirm?";
            if (delConfirmTimer) clearTimeout(delConfirmTimer);
            delConfirmTimer = setTimeout(() => {
                delConfirmName = null;
                btnPresetDel.textContent = "🗑";
            }, 3000);
            return;
        }
        delConfirmName = null;
        if (delConfirmTimer) clearTimeout(delConfirmTimer);
        btnPresetDel.textContent = "🗑";
        try {
            const resp = await api.fetchApi("/h3_context_studio/presets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "delete", name }),
            });
            const data = await resp.json();
            if (data && data.ok && data.presets) {
                userPresets = data.presets;
                renderPresetOptions();
                flashStatus(`Deleted "${name}"`);
            }
        } catch (err) {
            flashStatus(`Delete error: ${err.message}`, true);
        }
    };

    presetBar.append(presetSelect, btnPresetApply, btnPresetSave, btnPresetDel, presetStatus, btnJsonToggle);
    inspHeader.append(inspTitle, presetBar);
    fetchPresets();

    const gridCounts = document.createElement("div");
    gridCounts.className = "h3cs-grid";
    gridCounts.style.gridTemplateColumns = "repeat(5, 1fr)";
    const gridStrengths = document.createElement("div");
    gridStrengths.className = "h3cs-grid";
    gridStrengths.style.gridTemplateColumns = "repeat(5, 1fr)";

    const inputs = {};
    const addIntField = (parent, key, label, min, max) => {
        const box = document.createElement("div");
        box.className = "h3cs-field";
        const lb = document.createElement("label");
        lb.textContent = label;
        const row = document.createElement("div");
        row.className = "h3cs-stepper";
        const btnMinus = document.createElement("button");
        btnMinus.className = "h3cs-step-btn";
        btnMinus.textContent = "−";
        btnMinus.title = `Decrease ${label}`;
        const inp = document.createElement("input");
        inp.type = "number";
        inp.min = String(min);
        inp.max = String(max);
        inp.step = "1";
        const btnPlus = document.createElement("button");
        btnPlus.className = "h3cs-step-btn";
        btnPlus.textContent = "+";
        btnPlus.title = `Increase ${label}`;
        const setVal = (v) => {
            const c = clamp(Math.round(v), min, max);
            inp.value = String(c);
            applyToSelected({ [key]: c });
        };
        btnMinus.onclick = () => setVal((parseInt(inp.value, 10) || 0) - 1);
        btnPlus.onclick = () => setVal((parseInt(inp.value, 10) || 0) + 1);
        inp.addEventListener("change", () => setVal(parseInt(inp.value, 10) || 0));
        row.append(btnMinus, inp, btnPlus);
        box.append(lb, row);
        parent.appendChild(box);
        inputs[key] = { inp };
    };
    const addFloatField = (parent, key, label) => {
        const box = document.createElement("div");
        box.className = "h3cs-field";
        const top = document.createElement("div");
        top.className = "h3cs-val-row";
        const lb = document.createElement("label");
        lb.textContent = label;
        const numInp = document.createElement("input");
        numInp.type = "number";
        numInp.className = "h3cs-val-input";
        numInp.min = "0";
        numInp.max = "1";
        numInp.step = "0.01";
        numInp.value = "0.00";
        top.append(lb, numInp);
        const inp = document.createElement("input");
        inp.type = "range";
        inp.min = "0";
        inp.max = "1";
        inp.step = "0.01";
        inp.addEventListener("input", () => {
            const v = clamp(parseFloat(inp.value) || 0, 0, 1);
            numInp.value = v.toFixed(2);
            applyToSelected({ [key]: v });
        });
        numInp.addEventListener("change", () => {
            const v = clamp(parseFloat(numInp.value) || 0, 0, 1);
            numInp.value = v.toFixed(2);
            inp.value = String(v);
            applyToSelected({ [key]: v });
        });
        box.append(top, inp);
        parent.appendChild(box);
        inputs[key] = { inp, numInp };
    };

    addIntField(gridCounts, "context_before", "Ctx Before", 0, 16);
    addIntField(gridCounts, "buffer_before", "Buf Before", 0, 8);
    addIntField(gridCounts, "buffer_after", "Buf After", 0, 8);
    addIntField(gridCounts, "context_after", "Ctx After", 0, 16);

    // Explicit per-chunk conditioning index (-1 = Auto, 0+ = index into ConditioningCombine)
    {
        const box = document.createElement("div");
        box.className = "h3cs-field";
        const lb = document.createElement("label");
        lb.textContent = "Cond #";
        lb.title = "Conditioning index from ConditioningCombine (-1 / Auto = use Rolling Windows default; 0, 1, 2... = explicit index)";
        const row = document.createElement("div");
        row.className = "h3cs-stepper";
        const btnMinus = document.createElement("button");
        btnMinus.className = "h3cs-step-btn";
        btnMinus.textContent = "−";
        btnMinus.title = "Decrease Cond # (down to Auto)";
        const inp = document.createElement("input");
        inp.type = "text";
        inp.style.background = "#0e1015";
        inp.style.color = "#eef2fa";
        inp.style.border = "1px solid #303746";
        inp.style.borderRadius = "3px";
        inp.style.padding = "2px 4px";
        inp.style.fontSize = "11px";
        inp.style.textAlign = "center";
        inp.style.minWidth = "0";
        inp.style.flex = "1 1 auto";
        inp.style.height = "24px";
        inp.style.boxSizing = "border-box";
        const btnPlus = document.createElement("button");
        btnPlus.className = "h3cs-step-btn";
        btnPlus.textContent = "+";
        btnPlus.title = "Increase Cond # (0, 1, 2...)";
        const parseCond = (raw) => {
            const s = String(raw ?? "").trim().toLowerCase();
            if (!s || s === "auto") return -1;
            const n = parseInt(s, 10);
            return Number.isNaN(n) ? -1 : clamp(n, -1, 64);
        };
        const setVal = (v) => {
            const c = clamp(Math.round(v), -1, 64);
            inp.value = c < 0 ? "Auto" : String(c);
            applyToSelected({ cond_index: c });
        };
        btnMinus.onclick = () => setVal(parseCond(inp.value) - 1);
        btnPlus.onclick = () => setVal(parseCond(inp.value) + 1);
        inp.addEventListener("change", () => setVal(parseCond(inp.value)));
        row.append(btnMinus, inp, btnPlus);
        box.append(lb, row);
        gridCounts.appendChild(box);
        inputs.cond_index = { inp };
    }

    addFloatField(gridStrengths, "chunk_denoise", "Chunk Denoise");
    addFloatField(gridStrengths, "lead_start_denoise", "Lead Start Denoise");
    addFloatField(gridStrengths, "lead_end_denoise", "Lead End Denoise");
    addFloatField(gridStrengths, "tail_start_denoise", "Tail Start Denoise");
    addFloatField(gridStrengths, "tail_end_denoise", "Tail End Denoise");

    // Collapsible Advanced JSON drawer (hidden by default)
    const jsonDrawer = document.createElement("div");
    jsonDrawer.className = "h3cs-json-drawer";
    const jsonTextarea = document.createElement("textarea");
    jsonTextarea.spellcheck = false;
    const jsonApplyBtn = document.createElement("button");
    jsonApplyBtn.className = "h3cs-btn";
    jsonApplyBtn.style.alignSelf = "flex-end";
    jsonApplyBtn.textContent = "Apply JSON";
    jsonApplyBtn.onclick = () => {
        try {
            const parsed = JSON.parse(jsonTextarea.value);
            if (parsed && Array.isArray(parsed.chunks) && parsed.chunks.length > 0) {
                state.chunks = parsed.chunks;
                state.focused = clamp(state.focused, 0, state.chunks.length - 1);
                state.selected = new Set([state.focused]);
                syncToWidget();
                renderAll();
            }
        } catch (err) {
            alert(`Invalid JSON: ${err.message}`);
        }
    };
    jsonDrawer.append(jsonTextarea, jsonApplyBtn);
    btnJsonToggle.onclick = () => {
        const isOpen = jsonDrawer.classList.toggle("open");
        if (isOpen) {
            jsonTextarea.value = JSON.stringify(
                { frame_count: state.frameCount, preserve_first_frame: state.preserveFirst, chunks: state.chunks },
                null,
                2
            );
        }
    };

    inspector.append(inspHeader, saveBar, gridCounts, gridStrengths, jsonDrawer);
    root.appendChild(inspector);

    // --- Widget sync ---
    function syncToWidget() {
        const sw = getWidget("schedule_json");
        const payload = {
            frame_count: state.frameCount,
            preserve_first_frame: state.preserveFirst,
            chunks: state.chunks,
        };
        const text = JSON.stringify(payload);
        if (sw) sw.value = text;
        if (jsonDrawer.classList.contains("open")) {
            jsonTextarea.value = JSON.stringify(payload, null, 2);
        }
    }

    function normalizeChunk(ch) {
        // Migrate legacy *_strength keys -> *_denoise transparently
        const out = { ...ch };
        for (const base of ["lead_start", "lead_end", "tail_start", "tail_end"]) {
            const dk = `${base}_denoise`;
            const sk = `${base}_strength`;
            if (out[dk] == null) {
                out[dk] = out[sk] == null ? 0.0 : Number(out[sk]);
            }
            delete out[sk];
        }
        if (out.chunk_denoise == null) out.chunk_denoise = 1.0;
        if (out.cond_index == null) out.cond_index = -1;
        return out;
    }

    function loadFromWidget() {
        const pf = getWidget("preserve_first_frame");
        const dc = getWidget("default_commit");
        if (pf) state.preserveFirst = !!pf.value;
        if (dc) state.defaultCommit = Math.max(1, parseInt(dc.value, 10) || 4);

        const sw = getWidget("schedule_json");
        if (sw && sw.value && sw.value.trim()) {
            try {
                const parsed = JSON.parse(sw.value);
                if (parsed && Array.isArray(parsed.chunks) && parsed.chunks.length > 0) {
                    if (parsed.frame_count > 0) state.frameCount = parsed.frame_count;
                    state.chunks = parsed.chunks.map(normalizeChunk);
                    state.focused = clamp(state.focused, 0, state.chunks.length - 1);
                    state.selected = new Set([state.focused]);
                    return;
                }
            } catch (_) {}
        }
        state.chunks = buildDefaultChunks(state.frameCount, state.preserveFirst, state.defaultCommit);
        state.focused = 0;
        state.selected = new Set([0]);
        syncToWidget();
    }

    // --- Clear selected video (switch to upstream video/images input) ---
    function clearSelectedVideo() {
        videoEl.pause();
        videoEl.removeAttribute("src");
        videoEl.load();
        videoEl.style.display = "none";
        emptyMsg.textContent = "Using upstream 'video' / 'images' input (run once to preview & scrub, or pick/browse a video).";
        emptyMsg.style.display = "block";
        const vw = getVideoFileWidget();
        if (vw) {
            vw.value = "(upstream input)";
        }
    }
    btnClearVideo.onclick = () => clearSelectedVideo();

    // --- Browse / Upload video via OS file explorer ---
    btnBrowse.onclick = () => fileInput.click();
    fileInput.onchange = async () => {
        const file = fileInput.files?.[0];
        if (!file) return;
        btnBrowse.textContent = "Uploading...";
        btnBrowse.disabled = true;
        try {
            const body = new FormData();
            body.append("image", file);
            body.append("type", "input");
            body.append("overwrite", "true");
            const resp = await api.fetchApi("/upload/image", { method: "POST", body });
            if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
            const data = await resp.json();
            const relPath = data.subfolder ? `${data.subfolder}/${data.name}` : data.name;
            const vw = getVideoFileWidget();
            if (vw) {
                if (vw.options?.values && !vw.options.values.includes(relPath)) {
                    vw.options.values.push(relPath);
                }
                vw.value = relPath;
            }
            await loadPreviewVideo(data.name, data.subfolder || "", "input");
        } catch (err) {
            console.error("H3 Re-Time Context Studio upload error:", err);
            emptyMsg.textContent = `Upload error: ${err.message}`;
        } finally {
            btnBrowse.textContent = "📂 Browse Video";
            btnBrowse.disabled = false;
            fileInput.value = "";
        }
    };

    // --- Video seek & playback ---
    function seekFrame(f) {
        state.currentFrame = clamp(Math.round(f), 0, Math.max(0, state.frameCount - 1));
        if (videoEl.readyState >= 1 && state.fps > 0) {
            const targetTime = (state.currentFrame + 0.05) / state.fps;
            if (Math.abs(videoEl.currentTime - targetTime) > 0.004) {
                videoEl.currentTime = targetTime;
            }
        }
        updatePlayhead();
    }

    function updatePlayhead() {
        const x = (state.currentFrame + 0.5) * state.pxPerFrame;
        playheadMain.style.left = `${x}px`;
        playheadIso.style.left = `${x}px`;
        readout.textContent = `F ${state.currentFrame} / ${Math.max(0, state.frameCount - 1)} (${state.frameCount}f @ ${state.fps.toFixed(1)}fps)`;
    }

    let rafId = null;
    function syncPlayback() {
        if (videoEl.paused) {
            btnPlay.textContent = "▶ Play";
            rafId = null;
            return;
        }
        state.currentFrame = clamp(Math.floor(videoEl.currentTime * state.fps), 0, Math.max(0, state.frameCount - 1));
        updatePlayhead();
        rafId = requestAnimationFrame(syncPlayback);
    }

    btnPlay.onclick = () => {
        if (!videoEl.src) return;
        if (videoEl.paused) {
            videoEl.play();
            btnPlay.textContent = "⏸ Pause";
            if (!rafId) rafId = requestAnimationFrame(syncPlayback);
        } else {
            videoEl.pause();
            btnPlay.textContent = "▶ Play";
        }
    };
    btnPrev.onclick = () => { videoEl.pause(); seekFrame(state.currentFrame - 1); };
    btnNext.onclick = () => { videoEl.pause(); seekFrame(state.currentFrame + 1); };

    // --- Chunk editing operations ---
    function applyToSelected(patch) {
        if (state.selected.size === 0 && state.chunks.length > 0) {
            state.selected.add(state.focused);
        }
        for (const idx of state.selected) {
            if (state.chunks[idx]) {
                Object.assign(state.chunks[idx], patch);
            }
        }
        syncToWidget();
        renderAll();
    }

    btnSplit.onclick = () => {
        const f = state.currentFrame;
        const idx = state.chunks.findIndex((c) => f > c.commit_start && f < c.commit_end);
        if (idx < 0) return;
        const orig = state.chunks[idx];
        const left = { ...orig, commit_end: f };
        const right = { ...orig, commit_start: f };
        state.chunks.splice(idx, 1, left, right);
        state.focused = idx + 1;
        state.selected = new Set([idx + 1]);
        syncToWidget();
        renderAll();
    };

    btnMerge.onclick = () => {
        const sorted = Array.from(state.selected).sort((a, b) => a - b);
        if (sorted.length < 2) return;
        const lo = sorted[0];
        const hi = sorted[sorted.length - 1];
        const merged = { ...state.chunks[lo], commit_end: state.chunks[hi].commit_end };
        state.chunks.splice(lo, hi - lo + 1, merged);
        state.focused = lo;
        state.selected = new Set([lo]);
        syncToWidget();
        renderAll();
    };

    btnSelAll.onclick = () => {
        state.selected = new Set(state.chunks.map((_, i) => i));
        renderAll();
    };

    btnReset.onclick = () => {
        const pf = getWidget("preserve_first_frame");
        const dc = getWidget("default_commit");
        state.preserveFirst = pf ? !!pf.value : true;
        state.defaultCommit = dc ? Math.max(1, parseInt(dc.value, 10) || 4) : 4;
        state.chunks = buildDefaultChunks(state.frameCount, state.preserveFirst, state.defaultCommit);
        state.focused = 0;
        state.selected = new Set([0]);
        syncToWidget();
        renderAll();
    };

    // Ruler scrub (zoom-compensated!)
    function startScrub(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        videoEl.pause();
        const move = (e) => {
            const localX = clientXToLocalPx(ruler, e.clientX);
            seekFrame(Math.floor(localX / state.pxPerFrame));
        };
        const up = () => {
            window.removeEventListener("mousemove", move);
            window.removeEventListener("mouseup", up);
        };
        move(ev);
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
    }
    ruler.addEventListener("mousedown", startScrub);

    // --- Rendering ---
    function renderAll() {
        const availW = Math.max(360, (mainScroll.clientWidth || 560) - 4);
        state.pxPerFrame = clamp(Math.floor(availW / Math.max(1, state.frameCount)), 12, 36);
        const totalW = state.frameCount * state.pxPerFrame;
        mainInner.style.width = `${totalW}px`;
        isoInner.style.width = `${totalW}px`;

        // 1. Ruler
        ruler.innerHTML = "";
        const tickStep = state.pxPerFrame >= 20 ? 1 : state.pxPerFrame >= 14 ? 2 : 5;
        for (let f = 0; f < state.frameCount; f += tickStep) {
            const t = document.createElement("div");
            t.className = "h3cs-tick";
            t.style.left = `${f * state.pxPerFrame}px`;
            t.textContent = String(f);
            ruler.appendChild(t);
        }

        // 2. Committed chunks row
        chunksRow.innerHTML = "";
        if (state.preserveFirst && state.frameCount > 1) {
            const f0 = document.createElement("div");
            f0.className = "h3cs-f0";
            f0.style.left = "0px";
            f0.style.width = `${state.pxPerFrame}px`;
            f0.textContent = "F0";
            f0.title = "Frame 0 (preserved clean anchor)";
            f0.onclick = () => seekFrame(0);
            chunksRow.appendChild(f0);
        }

        state.chunks.forEach((ch, idx) => {
            const el = document.createElement("div");
            el.className = "h3cs-chunk";
            if (state.selected.has(idx)) el.classList.add("selected");
            if (idx === state.focused) el.classList.add("focused");
            el.style.left = `${ch.commit_start * state.pxPerFrame}px`;
            el.style.width = `${Math.max(1, ch.commit_end - ch.commit_start) * state.pxPerFrame}px`;
            el.style.background = CHUNK_COLORS[idx % CHUNK_COLORS.length];
            const len = ch.commit_end - ch.commit_start;
            const cd = ch.chunk_denoise == null ? 1.0 : Number(ch.chunk_denoise);
            const ci = ch.cond_index == null ? -1 : parseInt(ch.cond_index, 10);
            const cdTag = cd <= 0.001 ? " [SKIP]" : cd < 0.999 ? ` ×${cd.toFixed(2)}` : "";
            const ciTag = ci >= 0 ? ` [P${ci}]` : "";
            el.textContent = len >= 2 ? `C${idx + 1} (${ch.commit_start}-${ch.commit_end - 1})${ciTag}${cdTag}` : `${ch.commit_start}${ciTag}${cdTag}`;
            if (cd <= 0.001) el.style.opacity = "0.45";
            el.style.cursor = "grab";
            el.title = `Chunk ${idx + 1}: commit ${ch.commit_start}..${ch.commit_end - 1} (len ${len}, cond=${ci >= 0 ? "P" + ci : "Auto"}, denoise ×${cd.toFixed(2)}) • Click=isolate • Drag body=slide`;

            // Drag body to slide chunk (preserving its length), or click to select/isolate
            el.addEventListener("mousedown", (ev) => {
                if (ev.button !== 0) return;
                ev.stopPropagation();
                const startClientX = ev.clientX;
                const origStart = ch.commit_start;
                const origEnd = ch.commit_end;
                const chunkLen = origEnd - origStart;
                const prevCh = idx > 0 ? state.chunks[idx - 1] : null;
                const nextCh = idx < state.chunks.length - 1 ? state.chunks[idx + 1] : null;
                const minStart = prevCh ? prevCh.commit_start + 1 : origStart;
                const maxEnd = nextCh ? nextCh.commit_end - 1 : origEnd;
                let dragged = false;

                const move = (e) => {
                    if (!dragged && Math.abs(e.clientX - startClientX) < 4) return;
                    if (!dragged) {
                        dragged = true;
                        videoEl.pause();
                        el.style.cursor = "grabbing";
                    }
                    const rect = chunksRow.getBoundingClientRect();
                    const scaleX = rect.width / Math.max(1, chunksRow.offsetWidth);
                    const dxPx = (e.clientX - startClientX) / (scaleX > 0 ? scaleX : 1);
                    const df = Math.round(dxPx / state.pxPerFrame);
                    const newStart = clamp(origStart + df, minStart, maxEnd - chunkLen);
                    const newEnd = newStart + chunkLen;
                    if (newStart !== ch.commit_start) {
                        ch.commit_start = newStart;
                        ch.commit_end = newEnd;
                        if (prevCh) prevCh.commit_end = newStart;
                        if (nextCh) nextCh.commit_start = newEnd;
                        seekFrame(newStart);
                        syncToWidget();
                        renderAll();
                    }
                };
                const up = (e) => {
                    window.removeEventListener("mousemove", move);
                    window.removeEventListener("mouseup", up);
                    el.style.cursor = "grab";
                    if (!dragged) {
                        if (e.ctrlKey || e.metaKey) {
                            if (state.selected.has(idx)) state.selected.delete(idx);
                            else state.selected.add(idx);
                            state.focused = idx;
                        } else if (e.shiftKey && state.lastClicked != null) {
                            const lo = Math.min(state.lastClicked, idx);
                            const hi = Math.max(state.lastClicked, idx);
                            state.selected = new Set();
                            for (let k = lo; k <= hi; k++) state.selected.add(k);
                            state.focused = idx;
                        } else {
                            state.selected = new Set([idx]);
                            state.focused = idx;
                        }
                        state.lastClicked = idx;
                        seekFrame(ch.commit_start);
                        renderAll();
                    }
                };
                window.addEventListener("mousemove", move);
                window.addEventListener("mouseup", up);
            });
            chunksRow.appendChild(el);

            // Draggable boundary handle between chunk idx and chunk idx + 1 (zoom-compensated!)
            if (idx < state.chunks.length - 1) {
                const handle = document.createElement("div");
                handle.className = "h3cs-handle";
                handle.style.left = `${ch.commit_end * state.pxPerFrame}px`;
                handle.title = `Drag boundary between Chunk ${idx + 1} and Chunk ${idx + 2}`;
                handle.addEventListener("mousedown", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    videoEl.pause();
                    const leftCh = state.chunks[idx];
                    const rightCh = state.chunks[idx + 1];
                    const minF = leftCh.commit_start + 1;
                    const maxF = rightCh.commit_end - 1;
                    const move = (e) => {
                        const localX = clientXToLocalPx(chunksRow, e.clientX);
                        const f = clamp(Math.round(localX / state.pxPerFrame), minF, maxF);
                        if (f !== leftCh.commit_end) {
                            leftCh.commit_end = f;
                            rightCh.commit_start = f;
                            seekFrame(f);
                            syncToWidget();
                            renderAll();
                        }
                    };
                    const up = () => {
                        window.removeEventListener("mousemove", move);
                        window.removeEventListener("mouseup", up);
                    };
                    window.addEventListener("mousemove", move);
                    window.addEventListener("mouseup", up);
                });
                chunksRow.appendChild(handle);
            }
        });

        // 3. Isolated chunk window track
        isoRow.innerHTML = "";
        const ch = state.chunks[state.focused];
        if (ch) {
            const t0 = ch.commit_start;
            const t1 = ch.commit_end;
            const bbStart = Math.max(0, t0 - ch.buffer_before);
            const leadStart = Math.max(0, t0 - ch.buffer_before - ch.context_before);
            const baEnd = Math.min(state.frameCount, t1 + ch.buffer_after);
            const tailEnd = Math.min(state.frameCount, t1 + ch.buffer_after + ch.context_after);
            const winLen = ch.context_before + ch.buffer_before + (t1 - t0) + ch.buffer_after + ch.context_after;

            isoTitle.textContent =
                `Isolated Chunk #${state.focused + 1} (window len=${winLen}: ` +
                `C${ch.context_before} B${ch.buffer_before} T${t1 - t0} B${ch.buffer_after} C${ch.context_after})`;

            const addSeg = (cls, f0, f1, text, allowSlide = false) => {
                if (f1 <= f0) return;
                const d = document.createElement("div");
                d.className = `h3cs-iso-seg ${cls}`;
                d.style.left = `${f0 * state.pxPerFrame}px`;
                d.style.width = `${(f1 - f0) * state.pxPerFrame}px`;
                d.textContent = text;
                if (allowSlide) {
                    d.style.cursor = "grab";
                    d.title = "Drag body to slide this chunk (preserving its length & buffers)";
                    d.addEventListener("mousedown", (ev) => {
                        if (ev.button !== 0) return;
                        ev.preventDefault();
                        ev.stopPropagation();
                        const idx = state.focused;
                        const startClientX = ev.clientX;
                        const origStart = ch.commit_start;
                        const origEnd = ch.commit_end;
                        const chunkLen = origEnd - origStart;
                        const prevCh = idx > 0 ? state.chunks[idx - 1] : null;
                        const nextCh = idx < state.chunks.length - 1 ? state.chunks[idx + 1] : null;
                        const minStart = prevCh ? prevCh.commit_start + 1 : origStart;
                        const maxEnd = nextCh ? nextCh.commit_end - 1 : origEnd;
                        let dragged = false;
                        const move = (e) => {
                            if (!dragged && Math.abs(e.clientX - startClientX) < 4) return;
                            if (!dragged) {
                                dragged = true;
                                videoEl.pause();
                            }
                            const rect = isoRow.getBoundingClientRect();
                            const scaleX = rect.width / Math.max(1, isoRow.offsetWidth);
                            const dxPx = (e.clientX - startClientX) / (scaleX > 0 ? scaleX : 1);
                            const df = Math.round(dxPx / state.pxPerFrame);
                            const newStart = clamp(origStart + df, minStart, maxEnd - chunkLen);
                            const newEnd = newStart + chunkLen;
                            if (newStart !== ch.commit_start) {
                                ch.commit_start = newStart;
                                ch.commit_end = newEnd;
                                if (prevCh) prevCh.commit_end = newStart;
                                if (nextCh) nextCh.commit_start = newEnd;
                                seekFrame(newStart);
                                syncToWidget();
                                renderAll();
                            }
                        };
                        const up = () => {
                            window.removeEventListener("mousemove", move);
                            window.removeEventListener("mouseup", up);
                            if (!dragged) seekFrame(f0);
                        };
                        window.addEventListener("mousemove", move);
                        window.addEventListener("mouseup", up);
                    });
                } else {
                    d.onclick = () => seekFrame(f0);
                }
                isoRow.appendChild(d);
            };

            const cd = ch.chunk_denoise == null ? 1.0 : Number(ch.chunk_denoise);
            const lsd = ch.lead_start_denoise == null ? 0.0 : Number(ch.lead_start_denoise);
            const led = ch.lead_end_denoise == null ? 0.0 : Number(ch.lead_end_denoise);
            const tsd = ch.tail_start_denoise == null ? 0.0 : Number(ch.tail_start_denoise);
            const ted = ch.tail_end_denoise == null ? 0.0 : Number(ch.tail_end_denoise);
            addSeg("h3cs-iso-lead", leadStart, bbStart, `L:${(lsd * cd).toFixed(2)}-${(led * cd).toFixed(2)}`);
            addSeg("h3cs-iso-bb", bbStart, t0, `B:${ch.buffer_before}`);
            addSeg("h3cs-iso-tgt", t0, t1, cd < 0.999 ? `T:${t0}-${t1 - 1} @${cd.toFixed(2)}` : `T:${t0}-${t1 - 1}`, true);
            addSeg("h3cs-iso-ba", t1, baEnd, `B:${ch.buffer_after}`);
            addSeg("h3cs-iso-tail", baEnd, tailEnd, `C:${(tsd * cd).toFixed(2)}-${(ted * cd).toFixed(2)}`);

            const addIsoHandle = (posFrame, title, onDragFrame) => {
                const h = document.createElement("div");
                h.className = "h3cs-handle";
                h.style.left = `${posFrame * state.pxPerFrame}px`;
                h.title = title;
                h.addEventListener("mousedown", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    videoEl.pause();
                    const move = (e) => {
                        const localX = clientXToLocalPx(isoRow, e.clientX);
                        const f = clamp(Math.round(localX / state.pxPerFrame), 0, state.frameCount);
                        onDragFrame(f);
                        seekFrame(f);
                        syncToWidget();
                        renderAll();
                    };
                    const up = () => {
                        window.removeEventListener("mousemove", move);
                        window.removeEventListener("mouseup", up);
                    };
                    window.addEventListener("mousemove", move);
                    window.addEventListener("mouseup", up);
                });
                isoRow.appendChild(h);
            };

            addIsoHandle(leadStart, "Drag left edge to resize Context Before", (f) => {
                const curBbStart = Math.max(0, ch.commit_start - ch.buffer_before);
                ch.context_before = clamp(curBbStart - f, 0, 16);
            });
            if (ch.buffer_before > 0 || ch.context_before > 0) {
                addIsoHandle(bbStart, "Drag to resize Buffer Before", (f) => {
                    ch.buffer_before = clamp(ch.commit_start - f, 0, 8);
                });
            }
            if (ch.buffer_after > 0 || ch.context_after > 0) {
                addIsoHandle(baEnd, "Drag to resize Buffer After", (f) => {
                    ch.buffer_after = clamp(f - ch.commit_end, 0, 8);
                });
            }
            addIsoHandle(tailEnd, "Drag right edge to resize Context After", (f) => {
                const curBaEnd = Math.min(state.frameCount, ch.commit_end + ch.buffer_after);
                ch.context_after = clamp(f - curBaEnd, 0, 16);
            });

            // 4. Update inspector values
            const selCount = state.selected.size;
            inspTitle.textContent =
                selCount > 1
                    ? `Batch Editing ${selCount} Selected Chunks`
                    : `Chunk #${state.focused + 1} (frames ${t0}–${t1 - 1})`;

            for (const k of ["context_before", "buffer_before", "buffer_after", "context_after"]) {
                inputs[k].inp.value = String(ch[k]);
            }
            const ciVal = ch.cond_index == null ? -1 : parseInt(ch.cond_index, 10);
            inputs.cond_index.inp.value = ciVal < 0 || Number.isNaN(ciVal) ? "Auto" : String(ciVal);
            for (const k of ["chunk_denoise", "lead_start_denoise", "lead_end_denoise", "tail_start_denoise", "tail_end_denoise"]) {
                const v = ch[k] == null ? (k === "chunk_denoise" ? 1.0 : 0.0) : Number(ch[k]);
                inputs[k].inp.value = String(v);
                inputs[k].numInp.value = v.toFixed(2);
            }
        }

        updatePlayhead();
    }

    // --- Video loading ---
    async function loadPreviewVideo(filename, subfolder = "", type = "input", preserveExisting = false) {
        if (isUpstreamSentinel(filename)) {
            videoEl.pause();
            videoEl.removeAttribute("src");
            videoEl.load();
            videoEl.style.display = "none";
            emptyMsg.textContent = "Using upstream 'video' / 'images' input (run once to preview & scrub, or pick/browse a video).";
            emptyMsg.style.display = "block";
            return;
        }
        const params = new URLSearchParams({ filename, subfolder, type });
        videoEl.src = api.apiURL(`/view?${params.toString()}`);
        videoEl.style.display = "block";
        emptyMsg.style.display = "none";

        try {
            const resp = await api.fetchApi(`/h3_context_studio/probe?${params.toString()}`);
            const info = await resp.json();
            if (info && info.ok) {
                const capW = getWidget("frame_load_cap");
                const skipW = getWidget("skip_first_frames");
                const skip = skipW ? Math.max(0, parseInt(skipW.value, 10) || 0) : 0;
                const cap = capW ? Math.max(0, parseInt(capW.value, 10) || 0) : 0;
                let n = Math.max(1, info.frame_count - skip);
                if (cap > 0) n = Math.min(n, cap);
                const changed = n !== state.frameCount;
                state.frameCount = n;
                state.fps = info.fps || 24.0;
                const hasValidChunks =
                    state.chunks.length > 0 &&
                    state.chunks.every((c) => c.commit_start >= 0 && c.commit_end <= n && c.commit_end > c.commit_start);
                if (!preserveExisting || !hasValidChunks || (changed && !hasValidChunks)) {
                    if (changed || !hasValidChunks) {
                        state.chunks = buildDefaultChunks(state.frameCount, state.preserveFirst, state.defaultCommit);
                        state.focused = 0;
                        state.selected = new Set([0]);
                        syncToWidget();
                    }
                }
                renderAll();
            }
        } catch (_) {}
    }

    const videoWidget = getVideoFileWidget();
    if (videoWidget) {
        const origCb = videoWidget.callback;
        videoWidget.callback = function (val) {
            if (origCb) origCb.apply(this, arguments);
            if (!isUpstreamSentinel(val)) {
                const parts = String(val).split("/");
                const fn = parts.pop();
                loadPreviewVideo(fn, parts.join("/"), "input");
            } else {
                loadPreviewVideo("(upstream input)");
            }
        };
    }

    for (const wname of ["frame_load_cap", "skip_first_frames", "preserve_first_frame", "default_commit"]) {
        const w = getWidget(wname);
        if (w) {
            const origCb = w.callback;
            w.callback = function () {
                if (origCb) origCb.apply(this, arguments);
                const vw = getVideoFileWidget();
                if (vw && !isUpstreamSentinel(vw.value)) {
                    const parts = String(vw.value).split("/");
                    const fn = parts.pop();
                    loadPreviewVideo(fn, parts.join("/"), "input");
                }
            };
        }
    }

    // Re-render timeline smoothly whenever the node is resized (independent of video aspect ratio)
    if (typeof ResizeObserver !== "undefined") {
        let lastW = 0;
        const ro = new ResizeObserver(() => {
            const w = mainScroll.clientWidth || 0;
            if (Math.abs(w - lastW) >= 4) {
                lastW = w;
                renderAll();
            }
        });
        ro.observe(mainScroll);
    }

    loadFromWidget();
    renderAll();

    if (videoWidget && !isUpstreamSentinel(videoWidget.value)) {
        const parts = String(videoWidget.value).split("/");
        const fn = parts.pop();
        loadPreviewVideo(fn, parts.join("/"), "input");
    }

    return {
        root,
        onConfigure() {
            hideScheduleWidget(getWidget("schedule_json"));
            loadFromWidget();
            renderAll();
            const vw = getVideoFileWidget();
            if (vw && !isUpstreamSentinel(vw.value)) {
                const parts = String(vw.value).split("/");
                const fn = parts.pop();
                loadPreviewVideo(fn, parts.join("/"), "input", true);
            }
        },
        onExecuted(message) {
            if (message?.frame_count?.[0]) {
                const n = Number(message.frame_count[0]);
                const fps = Number(message.fps?.[0] || 24.0);
                state.fps = fps;
                if (n > 0 && n !== state.frameCount) {
                    state.frameCount = n;
                    state.chunks = buildDefaultChunks(state.frameCount, state.preserveFirst, state.defaultCommit);
                    state.focused = 0;
                    state.selected = new Set([0]);
                    syncToWidget();
                }
            }
            const pv = message?.preview_video?.[0];
            if (pv && pv.filename) {
                const params = new URLSearchParams({
                    filename: pv.filename,
                    subfolder: pv.subfolder || "",
                    type: pv.type || "temp",
                });
                videoEl.src = api.apiURL(`/view?${params.toString()}`);
                videoEl.style.display = "block";
                emptyMsg.style.display = "none";
            }
            renderAll();
        },
        onResize() {
            hideScheduleWidget(getWidget("schedule_json"));
            renderAll();
        },
        clearSelectedVideo,
    };
}

app.registerExtension({
    name: "H3PerFrame.ContextStudio",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        // Auto-migrate legacy H3PerFrameDecode widgets_values (old "all"/"targets" string -> batch_size=0)
        if (nodeData.name === "H3PerFrameDecode") {
            const origCfg = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                const r = origCfg ? origCfg.apply(this, arguments) : undefined;
                const bw = this.widgets?.find((w) => w.name === "batch_size");
                if (bw && (typeof bw.value !== "number" || Number.isNaN(bw.value))) {
                    const parsed = parseInt(bw.value, 10);
                    bw.value = Number.isNaN(parsed) ? 0 : parsed;
                }
                return r;
            };
            return;
        }
        if (nodeData.name !== "H3PerFrameContextStudio") return;

        const origCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origCreated ? origCreated.apply(this, arguments) : undefined;
            const studio = createStudioUI(this);
            this._h3Studio = studio;
            this.addDOMWidget("context_studio_ui", "custom", studio.root, {
                serialize: false,
                hideOnZoom: false,
                getMinHeight: () => 440,
            });
            this.setSize([Math.max(this.size[0] || 0, 680), Math.max(this.size[1] || 0, 680)]);
            return r;
        };

        const origConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = origConfigure ? origConfigure.apply(this, arguments) : undefined;
            hideScheduleWidget(this.widgets?.find((w) => w.name === "schedule_json"));
            if (this._h3Studio) this._h3Studio.onConfigure();
            return r;
        };

        const origExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            if (origExecuted) origExecuted.apply(this, arguments);
            if (this._h3Studio) this._h3Studio.onExecuted(message);
        };

        const origResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            const r = origResize ? origResize.apply(this, arguments) : undefined;
            if (this._h3Studio) this._h3Studio.onResize();
            return r;
        };

        const origConn = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
            const r = origConn ? origConn.apply(this, arguments) : undefined;
            const inName = this.inputs?.[index]?.name;
            if (type === 1 && connected && (inName === "images" || inName === "video")) {
                if (this._h3Studio) this._h3Studio.clearSelectedVideo();
            }
            return r;
        };
    },
});
