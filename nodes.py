"""Per-frame (temporally uncompressed) MiniMax H3 video restoration nodes.

Normal MiniMax H3 latents pack 1 + 4 + 4 + 4 + 4 pixel frames into 5 latent frames. These nodes
instead encode every pixel frame on its own (single-frame still path, 1 latent = 1 pixel frame),
restore the video in overlapping autoregressive rolling windows with per-frame RoPE retiming and
1-to-1 frame-synced audio, and decode all frames in a single batched pass at the end.

Nodes:
- H3 Re-Time Encode: Batched single-frame VAE encoder -> [1, 24, N, h, w] latent.
- H3 Re-Time AV Latent: Wraps a per-frame video latent with optional synced audio (or silent
  dummy audio when the source clip has no audio track) into a joint MiniMax H3 AV latent.
- H3 Re-Time Rolling Windows: Model patch implementing single-node autoregressive rolling
  restoration with per-frame RoPE timeline, clean-lead chaining, symmetric buffers, and synced audio.
- H3 Re-Time Decode: Batched single-frame VAE decoder -> [N, H, W, 3] images.
"""

import json
import logging
import math
import os
import time

import cv2
import numpy as np
import torch
import torch.nn.functional as F

import comfy.audio
import comfy.ldm.common_dit
import comfy.model_management
import comfy.nested_tensor
import comfy.patcher_extension
import comfy.utils
import folder_paths
import latent_preview
from comfy.ldm.minimax.model import FRAME_RESCALE, PackedLayout

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")

DEFAULT_STUDIO_PRESETS = {
    "Default (2/0/0/2 Hard)": {
        "context_before": 2,
        "buffer_before": 0,
        "buffer_after": 0,
        "context_after": 2,
        "chunk_denoise": 1.0,
        "lead_start_denoise": 0.0,
        "lead_end_denoise": 0.0,
        "tail_start_denoise": 0.0,
        "tail_end_denoise": 0.0,
        "cond_index": -1,
    },
    "Soft Ramp (0->0.4)": {
        "context_before": 2,
        "buffer_before": 0,
        "buffer_after": 0,
        "context_after": 2,
        "chunk_denoise": 1.0,
        "lead_start_denoise": 0.0,
        "lead_end_denoise": 0.4,
        "tail_start_denoise": 0.4,
        "tail_end_denoise": 0.0,
        "cond_index": -1,
    },
    "Skip Chunk (Keep Source)": {
        "context_before": 2,
        "buffer_before": 0,
        "buffer_after": 0,
        "context_after": 2,
        "chunk_denoise": 0.0,
        "lead_start_denoise": 0.0,
        "lead_end_denoise": 0.0,
        "tail_start_denoise": 0.0,
        "tail_end_denoise": 0.0,
        "cond_index": -1,
    },
}


def _presets_file_path():
    """Store user presets in ComfyUI's user directory so node updates never overwrite them."""
    try:
        user_dir = folder_paths.get_user_directory()
        if user_dir:
            os.makedirs(user_dir, exist_ok=True)
            return os.path.join(user_dir, "h3_context_studio_presets.json")
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), ".comfyui_h3_context_studio_presets.json")


def _load_studio_presets():
    path = _presets_file_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logging.warning(f"H3PerFrameContextStudio: failed reading presets ({e})")
    return {k: dict(v) for k, v in DEFAULT_STUDIO_PRESETS.items()}


def _save_studio_presets(presets):
    path = _presets_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2)
    os.replace(tmp, path)
    return path


try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.get("/h3_context_studio/probe")
    async def _h3_context_studio_probe(request):
        filename = request.rel_url.query.get("filename", "")
        subfolder = request.rel_url.query.get("subfolder", "")
        ftype = request.rel_url.query.get("type", "input")
        if not filename or filename == "(upstream images)":
            return web.json_response({"ok": False, "error": "no file"})
        base = (
            folder_paths.get_temp_directory()
            if ftype == "temp"
            else folder_paths.get_output_directory()
            if ftype == "output"
            else folder_paths.get_input_directory()
        )
        full = os.path.abspath(os.path.join(base, subfolder, filename))
        if not full.startswith(os.path.abspath(base)) or not os.path.isfile(full):
            return web.json_response({"ok": False, "error": "not found"})
        cap = cv2.VideoCapture(full)
        if not cap.isOpened():
            return web.json_response({"ok": False, "error": "cannot open"})
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return web.json_response({
            "ok": True,
            "frame_count": max(1, n_frames),
            "fps": fps if fps > 0 else 24.0,
            "width": w,
            "height": h,
        })

    @PromptServer.instance.routes.get("/h3_context_studio/presets")
    async def _h3_context_studio_get_presets(request):
        return web.json_response({
            "ok": True,
            "presets": _load_studio_presets(),
            "path": _presets_file_path(),
        })

    @PromptServer.instance.routes.post("/h3_context_studio/presets")
    async def _h3_context_studio_post_presets(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)
        action = str(body.get("action", "")).lower()
        name = str(body.get("name", "")).strip()
        if not name:
            return web.json_response({"ok": False, "error": "missing preset name"}, status=400)
        presets = _load_studio_presets()
        if action == "save":
            vals = body.get("values")
            if not isinstance(vals, dict):
                return web.json_response({"ok": False, "error": "missing values"}, status=400)
            allowed = {
                "context_before", "buffer_before", "buffer_after", "context_after",
                "chunk_denoise", "lead_start_denoise", "lead_end_denoise",
                "tail_start_denoise", "tail_end_denoise", "cond_index",
            }
            presets[name] = {k: vals[k] for k in allowed if k in vals}
            path = _save_studio_presets(presets)
            return web.json_response({"ok": True, "presets": presets, "path": path})
        elif action == "delete":
            presets.pop(name, None)
            path = _save_studio_presets(presets)
            return web.json_response({"ok": True, "presets": presets, "path": path})
        return web.json_response({"ok": False, "error": f"unknown action '{action}'"}, status=400)
except Exception:
    pass

CANVAS_MULTIPLE = 32          # 16x VAE * 2x2 DiT patch
VIDEO_CHANNELS = 24
AUDIO_CHANNELS = 32
WRAPPER_KEY = "h3_perframe_timeline"
ROLLING_OUTER_KEY = "h3_perframe_rolling_outer"


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------

def _fit_frames(images, width, height):
    """[N,H,W,C] -> [N,height,width,3], lanczos stretch only when the size differs."""
    images = images[..., :3]
    if images.shape[1] == height and images.shape[2] == width:
        return images
    s = images.movedim(-1, 1)
    s = comfy.utils.common_upscale(s, width, height, "lanczos", "disabled")
    return s.movedim(1, -1)


def _extract_video_latent(latent, name="latent"):
    """Extract [1, 24, T, h, w] video tensor from a plain or nested AV LATENT dict."""
    z = latent["samples"]
    if getattr(z, "is_nested", False):
        z = z.unbind()[0]
    if z.ndim != 5 or z.shape[1] != VIDEO_CHANNELS:
        raise ValueError(f"{name}: expected 5D MiniMax H3 video latent [B, 24, T, h, w], got {tuple(z.shape)}")
    return z


def _pick_vae_batch_size(vae, per_frame_mem, n_frames, requested_bs=0, max_auto=8):
    """Choose a VRAM-safe batch size for independent T=1 still frames (0 = Auto based on free VRAM)."""
    if requested_bs > 0:
        return max(1, min(int(requested_bs), n_frames)), "manual"
    try:
        free_vram = comfy.model_management.get_free_memory(vae.device)
        # Keep >=25% (at least 2 GB) headroom so Windows WDDM never spills into Shared GPU Memory paging.
        usable = max(0.0, free_vram - max(2.0 * (1024 ** 3), free_vram * 0.25))
        pf = max(int(per_frame_mem), 256 * 1024 * 1024)
        bs = max(1, min(max_auto, n_frames, int(usable // pf)))
        return bs, "auto"
    except Exception:
        return max(1, min(2, n_frames)), "auto"


def _encode_per_frame(vae, frames, batch_size=0):
    """Encode every frame as a lone still latent -> [1, 24, N, h, w].

    Loads the VAE onto GPU once and batches independent T=1 still frames per GPU call
    (eliminating N-1 redundant DynamicVRAM staging calls), with VRAM-aware auto batch sizing,
    automatic halving on OOM, and clear progress logging.
    """
    n = int(frames.shape[0])
    h, w = int(frames.shape[1]), int(frames.shape[2])
    pbar = comfy.utils.ProgressBar(n)
    out_dev = comfy.model_management.intermediate_device()
    t_start = time.time()

    fsm = getattr(vae, "first_stage_model", None)
    is_h3_vae = fsm is not None and "MiniMaxH3" in type(fsm).__name__
    if is_h3_vae and hasattr(vae, "patcher"):
        try:
            pf_mem = vae.memory_used_encode((1, 3, 1, h, w), vae.vae_dtype)
        except Exception:
            pf_mem = int(1.5 * (1024 ** 3) * (h * w) / (768 * 1344))
        comfy.model_management.load_models_gpu([vae.patcher], memory_required=pf_mem)
        bs, mode = _pick_vae_batch_size(vae, pf_mem, n, requested_bs=batch_size)
        logging.info(f"H3 Re-Time Encode: {n} frames ({w}x{h}, batch={bs} [{mode}], vae={type(fsm).__name__})")
        dev, dt = vae.device, vae.vae_dtype
        latents = []
        i = 0
        last_log = t_start
        with torch.no_grad():
            while i < n:
                cur_bs = min(bs, n - i)
                try:
                    pix = frames[i:i + cur_bs].movedim(-1, 1).unsqueeze(2).to(device=dev, dtype=dt) * 2.0 - 1.0
                    z = fsm.encode(pix)  # [B, 24, 1, h_lat, w_lat]
                    if z.ndim == 4:
                        z = z.unsqueeze(2)
                    if z.ndim != 5 or z.shape[1] != VIDEO_CHANNELS or z.shape[2] != 1:
                        raise ValueError(
                            f"Expected 24ch single-frame MiniMax H3 VAE latent, got {tuple(z.shape)}")
                    # [B, 24, 1, h, w] -> [1, 24, B, h, w]
                    latents.append(z.permute(2, 1, 0, 3, 4).contiguous().to(out_dev))
                    i += cur_bs
                    pbar.update(cur_bs)
                    now = time.time()
                    if i < n and (now - last_log >= 2.0):
                        fps = i / max(now - t_start, 1e-3)
                        logging.info(f"  H3 Re-Time Encode: {i}/{n} ({100.0 * i / n:.0f}%) - {fps:.1f} fps")
                        last_log = now
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    if bs > 1:
                        bs = max(1, bs // 2)
                        logging.warning(f"  H3 Re-Time Encode OOM, reducing batch size to {bs}")
                    else:
                        raise
        elapsed = time.time() - t_start
        logging.info(f"H3 Re-Time Encode: done {n} frames in {elapsed:.2f}s ({n / max(elapsed, 1e-3):.1f} fps)")
        return torch.cat(latents, dim=2)

    logging.info(f"H3 Re-Time Encode: {n} frames ({w}x{h}, fallback 1-by-1)")
    latents = []
    for i in range(n):
        z = vae.encode(frames[i:i + 1])
        if z.ndim != 5 or z.shape[1] != VIDEO_CHANNELS or z.shape[2] != 1:
            raise ValueError(
                "Expected the MiniMax H3 video/image VAE (24ch, one latent per still frame), got latent shape "
                f"{tuple(z.shape)}")
        latents.append(z.to(out_dev))
        pbar.update(1)
    elapsed = time.time() - t_start
    logging.info(f"H3 Re-Time Encode: done {n} frames in {elapsed:.2f}s ({n / max(elapsed, 1e-3):.1f} fps)")
    return torch.cat(latents, dim=2)


def _encode_audio(audio_vae, audio, audio_t, total_frames=0, fps=24.0):
    waveform = audio["waveform"]
    sr = audio["sample_rate"]
    vae_sr = getattr(audio_vae, "audio_sample_rate", 32000)
    if total_frames > 0:
        win_samples = round((total_frames / fps) * sr)
        if waveform.shape[-1] > win_samples + sr // 10:
            waveform = waveform[..., :win_samples]
    if sr != vae_sr:
        waveform = comfy.audio.resample(waveform, sr, vae_sr)
    z = audio_vae.encode(waveform[:1].movedim(1, -1))  # [1, 32, 2, T]
    z = z.to(comfy.model_management.intermediate_device())
    if z.shape[-1] >= audio_t:
        return z[..., :audio_t]
    pad = torch.zeros(z.shape[:-1] + (audio_t - z.shape[-1],), dtype=z.dtype, device=z.device)
    return torch.cat([z, pad], dim=-1)


def _retime_layout(layout, frame_spacing):
    """Copy of a PackedLayout whose target video rows advance FRAME_RESCALE * frame_spacing per latent."""
    va, vb = next((a, b) for a, b, kind in layout.segments if kind == "video")
    latent_t = layout.signature[1]
    rows = vb - va
    if latent_t <= 0 or rows % latent_t != 0:
        return layout
    per_frame = rows // latent_t

    pos = layout.position_ids.clone()
    origin = float(pos[va, 0])
    k = torch.arange(latent_t, dtype=pos.dtype).repeat_interleave(per_frame)
    pos[va:vb, 0] = origin + FRAME_RESCALE * frame_spacing * k
    if frame_spacing != 1.0:
        for a, b, kind in layout.segments:
            if kind == "cond":
                pos[a:b, 0] = origin + (pos[a:b, 0] - origin) * frame_spacing

    new = object.__new__(PackedLayout)
    new.__dict__.update(layout.__dict__)
    new.position_ids = pos
    return new


def _make_timeline_wrapper(frame_spacing):
    def wrapper(executor, x, timestep, context, transformer_options={}, minimax_payload=None, **kwargs):
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            video_x, audio_x = x[0], x[1]
            payload = dict(minimax_payload or {})
            patch_size = getattr(getattr(executor, "class_obj", None), "patch_size", (1, 2, 2))
            padded = comfy.ldm.common_dit.pad_to_patch_size(video_x, patch_size)
            latent_t, lat_h, lat_w = padded.shape[2], padded.shape[3], padded.shape[4]
            audio_t = audio_x.shape[-1]
            text_len = context.shape[1]
            sig = (text_len, latent_t, lat_h, lat_w, audio_t)
            layout = payload.get("layout")
            if layout is None or layout.signature != sig:
                layout = PackedLayout(text_len, latent_t, lat_h, lat_w, audio_t,
                                      keyframes=payload.get("keyframes"), refs=payload.get("refs"))
            payload["layout"] = _retime_layout(layout, frame_spacing)
            minimax_payload = payload
        return executor(x, timestep, context, transformer_options, minimax_payload=minimax_payload, **kwargs)
    return wrapper


def _slice_synced_audio(src_a, n_video, idxs, out_a=None, n_left=0, per_frame_mask=None):
    """Slice audio [1, 32, 2, A] aligned 1-to-1 with 24fps video frame indices `idxs` (40Hz = 5/3 per frame).

    Returns (win_a, win_a_mask_or_None, a_left_len, a_commit_info):
    - Left frames (first `n_left` of `idxs`) read from `out_a` when provided (for autoregressive audio chaining).
    - Remaining frames read from `src_a`.
    - If `per_frame_mask` (length == len(idxs)) is provided, builds a matching per-audio-frame mask tensor.
    """
    a_total = int(src_a.shape[-1])
    if a_total <= 0 or not idxs:
        return src_a, None, 0, []
    # Always use the exact 40Hz / 24fps = 5/3 ratio rather than a_total / n_video, because loaders like
    # VHS_LoadVideo with frame_load_cap can pass a longer audio track than the loaded video frame count.
    edges = [min(a_total, round(k * FRAME_RESCALE)) for k in range(n_video + 1)]
    parts = []
    mask_parts = []
    frame_a_lens = []
    for pos, k in enumerate(idxs):
        a0 = min(a_total - 1, edges[k])
        a1 = min(a_total, max(a0 + 1, edges[k + 1]))
        src = out_a if (out_a is not None and pos < n_left) else src_a
        seg = src[:, :, :, a0:a1]
        parts.append(seg)
        seg_len = int(seg.shape[-1])
        frame_a_lens.append(seg_len)
        if per_frame_mask is not None:
            mask_parts.append(torch.full((1, 1, seg.shape[2], seg_len), float(per_frame_mask[pos]),
                                         dtype=torch.float32, device=src_a.device))
    a_win = torch.cat(parts, dim=-1)
    a_left_len = sum(frame_a_lens[:n_left])
    target_a = max(1, round(len(idxs) * FRAME_RESCALE))
    if a_win.shape[-1] > target_a:
        a_win = a_win[..., :target_a]
    elif a_win.shape[-1] < target_a:
        a_win = torch.cat([a_win, a_win[..., -1:].repeat(1, 1, 1, target_a - a_win.shape[-1])], dim=-1)

    a_mask = None
    if per_frame_mask is not None:
        a_mask = torch.cat(mask_parts, dim=-1)
        if a_mask.shape[-1] > target_a:
            a_mask = a_mask[..., :target_a]
        elif a_mask.shape[-1] < target_a:
            a_mask = torch.cat([a_mask, a_mask[..., -1:].repeat(1, 1, 1, target_a - a_mask.shape[-1])], dim=-1)
        a_mask = a_mask.expand_as(a_win).contiguous()
    return a_win, a_mask, a_left_len, frame_a_lens


def _slice_minimax_keyframes_for_window(cond_dict, win_start_frame, win_audio_len):
    """Slice any MiniMaxH3AddGuide audio_latent keyframes to the current rolling window's time range."""
    kfs = cond_dict.get("minimax_keyframes")
    if not kfs:
        return cond_dict
    has_audio_kf = any(kf.get("audio_latent") is not None for kf in kfs)
    if not has_audio_kf:
        return cond_dict
    a0 = round(win_start_frame * FRAME_RESCALE)
    a1 = a0 + win_audio_len
    new_kfs = []
    for kf in kfs:
        nk = kf.copy()
        al = kf.get("audio_latent")
        if al is not None:
            t = FRAME_RESCALE * float(kf.get("resolved_frame_index", 0))
            j0 = max(0, math.ceil(a0 - t))
            j1 = min(int(al.shape[-1]), math.ceil(a1 - t))
            if j1 > j0:
                nk["resolved_frame_index"] = (t + j0 - a0) / FRAME_RESCALE
                nk["audio_latent"] = al[..., j0:j1].clone()
                new_kfs.append(nk)
        else:
            new_kfs.append(nk)
    out = cond_dict.copy()
    out["minimax_keyframes"] = new_kfs
    return out


def _make_rolling_outer_wrapper(
    commit_frames,
    context_before,
    buffer_before,
    buffer_after,
    context_after,
    lead_start_denoise,
    lead_end_denoise,
    tail_start_denoise,
    tail_end_denoise,
    preserve_first_frame,
    pad_start,
    pad_end,
    freeze_audio,
    vary_seed,
    window_plan=None,
    split_conds_to_windows=False,
):
    def wrapper(executor, noise, latent_image, sampler, sigmas, denoise_mask=None,
                callback=None, disable_pbar=False, seed=None, latent_shapes=None):
        if latent_image is None:
            return executor(noise, latent_image, sampler, sigmas, denoise_mask,
                            callback, disable_pbar, seed, latent_shapes=latent_shapes)

        is_multimodal = latent_shapes is not None and len(latent_shapes) > 1
        if is_multimodal:
            src_parts = list(comfy.utils.unpack_latents(latent_image, latent_shapes))
            noise_parts = list(comfy.utils.unpack_latents(noise, latent_shapes))
            src_v, src_a = src_parts[0], src_parts[1]
            noise_v, noise_a = noise_parts[0], noise_parts[1]
        else:
            src_v, src_a = latent_image, None
            noise_v, noise_a = noise, None

        n = int(src_v.shape[2])
        if n <= 1:
            return executor(noise, latent_image, sampler, sigmas, denoise_mask,
                            callback, disable_pbar, seed, latent_shapes=latent_shapes)

        out_v = src_v.clone()
        out_a = src_a.clone() if src_a is not None else None
        has_real_audio = src_a is not None and bool(torch.count_nonzero(src_a).item() > 0)
        lock_audio = bool(freeze_audio and has_real_audio)

        base_seed = 0 if seed is None else int(seed)

        # Build chunk specs either from Context Studio `window_plan` or uniform defaults.
        chunk_specs = []
        if window_plan and isinstance(window_plan, dict) and window_plan.get("chunks"):
            for ch in window_plan["chunks"]:
                t0 = max(0, min(n - 1, int(ch.get("commit_start", 0))))
                t1 = max(t0 + 1, min(n, int(ch.get("commit_end", t0 + 1))))
                chunk_specs.append({
                    "t0": t0,
                    "t1": t1,
                    "c_step": max(1, int(ch.get("commit_end", t1)) - int(ch.get("commit_start", t0))),
                    "c_before": max(0, int(ch.get("context_before", context_before))),
                    "b_before": max(0, int(ch.get("buffer_before", buffer_before))),
                    "b_after": max(0, int(ch.get("buffer_after", buffer_after))),
                    "c_after": max(0, int(ch.get("context_after", context_after))),
                    "lead_start": float(ch.get("lead_start_denoise", ch.get("lead_start_strength", lead_start_denoise))),
                    "lead_end": float(ch.get("lead_end_denoise", ch.get("lead_end_strength", lead_end_denoise))),
                    "tail_start": float(ch.get("tail_start_denoise", ch.get("tail_start_strength", tail_start_denoise))),
                    "tail_end": float(ch.get("tail_end_denoise", ch.get("tail_end_strength", tail_end_denoise))),
                    "chunk_denoise": max(0.0, min(1.0, float(ch.get("chunk_denoise", 1.0)))),
                    "cond_index": int(ch.get("cond_index", -1)),
                })
        else:
            start_idx = 1 if preserve_first_frame else 0
            c_step = max(1, int(commit_frames))
            for t0 in range(start_idx, n, c_step):
                t1 = min(n, t0 + c_step)
                chunk_specs.append({
                    "t0": t0,
                    "t1": t1,
                    "c_step": c_step,
                    "c_before": max(0, int(context_before)),
                    "b_before": max(0, int(buffer_before)),
                    "b_after": max(0, int(buffer_after)),
                    "c_after": max(0, int(context_after)),
                    "lead_start": float(lead_start_denoise),
                    "lead_end": float(lead_end_denoise),
                    "tail_start": float(tail_start_denoise),
                    "tail_end": float(tail_end_denoise),
                    "chunk_denoise": 1.0,
                    "cond_index": -1,
                })

        total_chunks = len(chunk_specs)
        plan_tag = "Context Studio plan" if (window_plan and window_plan.get("chunks")) else "uniform"
        logging.info(
            f"\nH3 Re-Time Rolling Windows ({plan_tag}): {total_chunks} chunks for {n} frames "
            f"(audio={'locked' if lock_audio else 'free'})"
        )

        guider_obj = getattr(executor, "class_obj", None)
        mp = getattr(guider_obj, "model_patcher", None)
        mask_device = mp.load_device if mp is not None else src_v.device
        orig_conds = getattr(guider_obj, "conds", None)
        if orig_conds is not None:
            orig_conds = {k: [c.copy() for c in v] for k, v in orig_conds.items()}

        # Enable live sampler previews + ModelPreviewOverrideKJ compatibility across chunks.
        chunk_steps = max(1, int(sigmas.shape[-1]) - 1) if sigmas is not None and sigmas.ndim >= 1 else 1
        total_preview_steps = max(1, total_chunks * chunk_steps)
        cb_mod = getattr(callback, "__module__", "") or ""
        cb_qname = getattr(callback, "__qualname__", "") or ""
        is_outer_preview_override = (
            callback is not None
            and (
                "preview_override" in cb_mod.lower()
                or "previewoverride" in cb_qname.lower()
                or "kj_preview" in cb_mod.lower()
            )
        )
        chunk_preview_cb = None
        if not is_outer_preview_override and mp is not None:
            try:
                chunk_preview_cb = latent_preview.prepare_callback(mp, total_preview_steps)
            except Exception as e:
                logging.debug(f"H3PerFrameRollingWindows: preview callback init skipped ({e})")

        pbar = comfy.utils.ProgressBar(total_chunks) if (chunk_preview_cb is None and not is_outer_preview_override) else None
        try:
            for chunk_idx, spec in enumerate(chunk_specs):
                t0 = spec["t0"]
                t1 = spec["t1"]
                n_real = t1 - t0
                c_step = spec["c_step"]
                c_before = spec["c_before"]
                b_before = spec["b_before"]
                b_after = spec["b_after"]
                c_after = spec["c_after"]
                ls_start = spec["lead_start"]
                ls_end = spec["lead_end"]
                ts_start = spec["tail_start"]
                ts_end = spec["tail_end"]
                ch_denoise = spec["chunk_denoise"]

                if ch_denoise <= 1e-4:
                    logging.info(
                        f"Rolling chunk {chunk_idx + 1}/{total_chunks}: commit {t0}-{t1 - 1} of {n} "
                        f"(SKIPPED: chunk_denoise=0.0, keeping source frames)"
                    )
                    out_v[:, :, t0:t1] = src_v[:, :, t0:t1].to(device=out_v.device, dtype=out_v.dtype)
                    if pbar is not None:
                        pbar.update(1)
                    continue

                # Left (lead + buffer_before) read from already-restored out_v
                req_left = c_before + b_before
                if pad_start:
                    left_idxs = [max(0, t0 - req_left + j) for j in range(req_left)]
                    n_lead = c_before
                    n_buf_before = b_before
                else:
                    avail_left = min(req_left, t0)
                    left_idxs = list(range(t0 - avail_left, t0))
                    n_buf_before = min(b_before, avail_left)
                    n_lead = avail_left - n_buf_before

                # Commit + right (buffer_after + tail) read from source src_v
                if pad_end:
                    commit_idxs = [min(n - 1, t0 + j) for j in range(c_step)]
                    n_commit_win = c_step
                    right_start = t0 + c_step
                    req_right = b_after + c_after
                    right_idxs = [min(n - 1, right_start + j) for j in range(req_right)]
                    n_buf_after = b_after
                    n_tail = c_after
                else:
                    commit_idxs = list(range(t0, t1))
                    n_commit_win = n_real
                    avail_right = max(0, n - t1)
                    n_buf_after = min(b_after, avail_right)
                    n_tail = min(c_after, max(0, avail_right - n_buf_after))
                    right_idxs = list(range(t1, t1 + n_buf_after + n_tail))

                all_idxs = left_idxs + commit_idxs + right_idxs
                w_len = len(all_idxs)
                commit_offset = n_lead + n_buf_before

                v_parts = []
                if left_idxs:
                    v_parts.append(out_v[:, :, left_idxs])
                v_parts.append(src_v[:, :, commit_idxs])
                if right_idxs:
                    v_parts.append(src_v[:, :, right_idxs])
                win_v = torch.cat(v_parts, dim=2).contiguous()

                # Per-frame denoise mask:
                # [lead ramp | buffer_before (1.0) | commit (1.0) | buffer_after (1.0) | tail ramp]
                strengths = []
                for k in range(n_lead):
                    if n_lead == 1:
                        strengths.append(ls_start)
                    else:
                        a = k / (n_lead - 1)
                        strengths.append(ls_start + (ls_end - ls_start) * a)
                strengths.extend([1.0] * (n_buf_before + n_commit_win + n_buf_after))
                for k in range(n_tail):
                    if n_tail == 1:
                        strengths.append(ts_start)
                    else:
                        a = k / (n_tail - 1)
                        strengths.append(ts_start + (ts_end - ts_start) * a)

                if ch_denoise < 1.0:
                    strengths = [s * ch_denoise for s in strengths]

                vm = torch.tensor(strengths, dtype=torch.float32, device=win_v.device).view(1, 1, w_len, 1, 1)
                win_v_mask = vm.expand_as(win_v).contiguous()

                chunk_seed = base_seed + chunk_idx if vary_seed else base_seed
                if vary_seed:
                    gen = torch.Generator("cpu").manual_seed(chunk_seed)
                    win_noise_v = torch.randn(win_v.shape, generator=gen, dtype=noise_v.dtype).to(noise_v.device)
                else:
                    win_noise_v = noise_v[:, :, all_idxs].contiguous()

                a_left_len = 0
                frame_a_lens = []
                if is_multimodal:
                    n_left_frames = len(left_idxs)
                    if lock_audio:
                        win_a, _, a_left_len, frame_a_lens = _slice_synced_audio(src_a, n, all_idxs)
                        win_a_mask = torch.zeros_like(win_a, dtype=torch.float32)
                    else:
                        # Free audio generation: chain already-generated left audio on chunks > 0
                        # using the same lead mask, while denoising commit + right audio freely.
                        a_frame_masks = (
                            [s if idx < n_left_frames else 1.0 for idx, s in enumerate(strengths)]
                            if (chunk_idx > 0 and n_left_frames > 0)
                            else [1.0] * w_len
                        )
                        win_a, win_a_mask, a_left_len, frame_a_lens = _slice_synced_audio(
                            src_a, n, all_idxs,
                            out_a=out_a if chunk_idx > 0 else None,
                            n_left=n_left_frames,
                            per_frame_mask=a_frame_masks,
                        )
                    win_a = win_a.contiguous()
                    if vary_seed:
                        gen_a = torch.Generator("cpu").manual_seed(chunk_seed + 1000003)
                        win_noise_a = torch.randn(win_a.shape, generator=gen_a, dtype=noise_a.dtype).to(noise_a.device)
                    else:
                        win_noise_a, _, _, _ = _slice_synced_audio(noise_a, n, all_idxs)
                        win_noise_a = win_noise_a.contiguous()
                    win_latent, win_shapes = comfy.utils.pack_latents([win_v, win_a])
                    win_noise, _ = comfy.utils.pack_latents([win_noise_v, win_noise_a])
                    win_mask, _ = comfy.utils.pack_latents([win_v_mask, win_a_mask])
                else:
                    win_latent, win_shapes = win_v, None
                    win_noise = win_noise_v
                    win_mask = win_v_mask

                win_mask = win_mask.to(device=mask_device, dtype=torch.float32)

                cond_tag = ""
                if guider_obj is not None and orig_conds is not None:
                    center_ratio = (t0 + (t1 - 1)) / (2.0 * max(n, 1))
                    explicit_cond = int(spec.get("cond_index", -1))
                    win_audio_len = int(win_a.shape[-1]) if is_multimodal else round(w_len * FRAME_RESCALE)
                    win_origin_frame = t0 - commit_offset
                    new_conds = {}
                    picked_regions = []
                    for k, v in orig_conds.items():
                        if len(v) > 1 and explicit_cond >= 0:
                            region = min(explicit_cond, len(v) - 1)
                            selected = [v[region].copy()]
                            picked_regions.append(f"{k}={region}/{len(v)} (explicit)")
                        elif len(v) > 1 and split_conds_to_windows:
                            region = min(max(int(center_ratio * len(v)), 0), len(v) - 1)
                            selected = [v[region].copy()]
                            picked_regions.append(f"{k}={region}/{len(v)} (auto)")
                        else:
                            selected = [c.copy() for c in v]
                        new_conds[k] = [
                            _slice_minimax_keyframes_for_window(c, win_origin_frame, win_audio_len)
                            for c in selected
                        ]
                    guider_obj.conds = new_conds
                    if picked_regions:
                        cond_tag = f", conds=[{', '.join(picked_regions)}]"

                logging.info(
                    f"Rolling chunk {chunk_idx + 1}/{total_chunks}: commit {t0}-{t1 - 1} of {n} "
                    f"(window {all_idxs[0]}-{all_idxs[-1]}, len={w_len}, mask={[round(s, 2) for s in strengths]}{cond_tag})"
                )

                # Per-chunk live preview callback (supports both built-in sampler previews and ModelPreviewOverrideKJ)
                win_callback = None
                if is_outer_preview_override:
                    def _outer_preview_cb(step, x0, x, total_steps,
                                          _ci=chunk_idx, _t0=t0, _t1=t1, _co=commit_offset, _nr=n_real,
                                          _ws=win_shapes, _al=a_left_len):
                        try:
                            if is_multimodal and _ws is not None:
                                ux0 = comfy.utils.unpack_latents(x0, _ws)
                                x0_v, x0_a = ux0[0], ux0[1]
                            else:
                                x0_v, x0_a = x0, None
                            live_v = out_v.to(device=x0_v.device, dtype=x0_v.dtype).clone()
                            live_v[:, :, _t0:_t1] = x0_v[:, :, _co:_co + _nr]
                            if is_multimodal and out_a is not None:
                                live_a = out_a.to(device=x0_v.device, dtype=x0_v.dtype).clone()
                                if not lock_audio and x0_a is not None:
                                    a_tot = int(live_a.shape[-1])
                                    ad0 = min(a_tot, round(_t0 * FRAME_RESCALE))
                                    ad1 = min(a_tot, round(_t1 * FRAME_RESCALE))
                                    as0 = min(int(x0_a.shape[-1]), _al)
                                    ac = min(ad1 - ad0, int(x0_a.shape[-1]) - as0)
                                    if ac > 0:
                                        live_a[:, :, :, ad0:ad0 + ac] = x0_a[:, :, :, as0:as0 + ac]
                                live_packed, _ = comfy.utils.pack_latents([live_v, live_a])
                            else:
                                live_packed = live_v
                            return callback(_ci * chunk_steps + step, live_packed, live_packed, total_preview_steps)
                        except Exception as e:
                            logging.debug(f"H3PerFrameRollingWindows: outer preview callback skipped ({e})")
                    win_callback = _outer_preview_cb
                elif chunk_preview_cb is not None:
                    def _chunk_preview_cb(step, x0, x, total_steps,
                                          _ci=chunk_idx, _co=commit_offset, _nr=n_real, _ws=win_shapes):
                        try:
                            if is_multimodal and _ws is not None:
                                x0_v = comfy.utils.unpack_latents(x0, _ws)[0]
                            else:
                                x0_v = x0
                            x0_commit = x0_v[:, :, _co:_co + _nr]
                            return chunk_preview_cb(_ci * chunk_steps + step, x0_commit, x0_commit, total_preview_steps)
                        except Exception as e:
                            logging.debug(f"H3PerFrameRollingWindows: chunk preview callback skipped ({e})")
                    win_callback = _chunk_preview_cb

                win_out = executor(
                    win_noise, win_latent, sampler, sigmas, win_mask,
                    win_callback, disable_pbar, chunk_seed, latent_shapes=win_shapes,
                )
                if is_multimodal:
                    unpacked_out = comfy.utils.unpack_latents(win_out, win_shapes)
                    out_win_v, out_win_a = unpacked_out[0], unpacked_out[1]
                else:
                    out_win_v, out_win_a = win_out, None

                out_v[:, :, t0:t1] = out_win_v[:, :, commit_offset:commit_offset + n_real].to(
                    device=out_v.device, dtype=out_v.dtype
                )
                if is_multimodal and not lock_audio and out_win_a is not None:
                    a_total = int(out_a.shape[-1])
                    a_dst0 = min(a_total, round(t0 * FRAME_RESCALE))
                    a_dst1 = min(a_total, round(t1 * FRAME_RESCALE))
                    n_a_dst = a_dst1 - a_dst0
                    if n_a_dst > 0:
                        a_src0 = min(int(out_win_a.shape[-1]), a_left_len)
                        a_copy = min(n_a_dst, int(out_win_a.shape[-1]) - a_src0)
                        if a_copy > 0:
                            out_a[:, :, :, a_dst0:a_dst0 + a_copy] = out_win_a[:, :, :, a_src0:a_src0 + a_copy].to(
                                device=out_a.device, dtype=out_a.dtype
                            )
                if pbar is not None:
                    pbar.update(1)
        finally:
            if guider_obj is not None and orig_conds is not None:
                guider_obj.conds = orig_conds

        if is_multimodal:
            return comfy.utils.pack_latents([out_v, out_a])[0]
        return out_v

    return wrapper


# ----------------------------------------------------------------------------------------------
# nodes
# ----------------------------------------------------------------------------------------------

class H3PerFrameEncode:
    DESCRIPTION = (
        "VAE-encodes every frame of an image batch on its own (single-frame still path) into a temporally "
        "uncompressed [1, 24, N, h, w] MiniMax H3 video latent. Uses single-load VRAM-aware batching.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "vae": ("VAE", {"tooltip": "MiniMax H3 image/video VAE (e.g. minimax_h3_image_vae_fp16)."}),
                "images": ("IMAGE", {"tooltip": "Video frames, [N,H,W,C]."}),
                "width": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 32,
                                  "tooltip": "0 = use the image width rounded to a multiple of 32."}),
                "height": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 32,
                                   "tooltip": "0 = use the image height rounded to a multiple of 32."}),
            },
            "optional": {
                "batch_size": ("INT", {"default": 0, "min": 0, "max": 32,
                                       "tooltip": "0 = auto-size from free VRAM (safe across 8-32GB GPUs); >0 = fixed batch size (auto-halves on OOM)."}),
            },
        }

    RETURN_TYPES = ("LATENT", "INT")
    RETURN_NAMES = ("latent", "frame_count")
    FUNCTION = "execute"
    CATEGORY = "model/latent/minimax"

    def execute(self, vae, images, width, height, batch_size=0):
        n = images.shape[0]
        if n == 0:
            raise ValueError("images is empty")
        if width <= 0:
            width = max(CANVAS_MULTIPLE, round(images.shape[2] / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)
        if height <= 0:
            height = max(CANVAS_MULTIPLE, round(images.shape[1] / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)
        frames = _fit_frames(images, width, height)
        z = _encode_per_frame(vae, frames, batch_size=batch_size)
        return ({"samples": z}, n)


class H3PerFramePrepareAV:
    DESCRIPTION = (
        "Wraps a per-frame video latent from 'H3 Re-Time Encode' with optional synced audio (or silent "
        "placeholder audio when the clip has no audio track) into a joint MiniMax H3 AV latent for "
        "'H3 Re-Time Rolling Windows'.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_latent": ("LATENT", {"tooltip": "Full [1, 24, N, h, w] per-frame latent from 'H3 Re-Time Encode'."}),
            },
            "optional": {
                "audio_vae": ("VAE", {"tooltip": "Optional MiniMax H3 audio VAE, used when 'audio' is connected."}),
                "audio": ("AUDIO", {"tooltip": "Optional full-clip soundtrack (frozen per chunk by Rolling Windows)."}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "execute"
    CATEGORY = "model/latent/minimax"

    def execute(self, video_latent, audio_vae=None, audio=None):
        vz = _extract_video_latent(video_latent, "video_latent").clone()
        total = vz.shape[2]
        audio_t = max(1, round(total * FRAME_RESCALE))
        if audio is not None:
            if audio_vae is None:
                raise ValueError("audio needs audio_vae")
            az = _encode_audio(audio_vae, audio, audio_t, total_frames=total)
            logging.info(
                f"H3 Re-Time AV Latent: synced audio to {total} video frames @ 24fps "
                f"({total / 24.0:.2f}s -> {az.shape[-1]} audio latents @ 40Hz)"
            )
        else:
            az = torch.zeros([1, AUDIO_CHANNELS, 2, audio_t], device=vz.device)
        return ({"samples": comfy.nested_tensor.NestedTensor((vz, az))},)


class H3PerFrameRollingWindows:
    DESCRIPTION = (
        "Single-node autoregressive rolling restoration for MiniMax H3 per-frame latents. "
        "Combines simple single-pass wiring (no Start/End Loop) with clean-lead autoregressive chaining, "
        "symmetric throwaway buffers (buffer_before & buffer_after) around commit_frames, per-frame RoPE "
        "retiming, and 1-to-1 frame-synced frozen audio for exact lipsync.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "commit_frames": ("INT", {"default": 4, "min": 1, "max": 32,
                                          "tooltip": "Number of restored center frames kept per chunk (also the stride)."}),
                "context_before": ("INT", {"default": 2, "min": 0, "max": 16,
                                           "tooltip": "Masked leading context frames (already-restored clean frames)."}),
                "buffer_before": ("INT", {"default": 0, "min": 0, "max": 8,
                                          "tooltip": "Unmasked (1.0) throwaway frames between lead and commit (read from already-restored frames)."}),
                "buffer_after": ("INT", {"default": 0, "min": 0, "max": 8,
                                         "tooltip": "Unmasked (1.0) throwaway frames between commit and tail. Absorbs trailing 1.0->0.0 cliff artifacts."}),
                "context_after": ("INT", {"default": 2, "min": 0, "max": 16,
                                          "tooltip": "Masked trailing context frames from the source video."}),
                "lead_start_denoise": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                                 "tooltip": "Denoise level for the outer leading context frame (0.0 = frozen clean anchor, 1.0 = full denoise)."}),
                "lead_end_denoise": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                               "tooltip": "Denoise level for the inner leading context frame (linearly interpolates across context_before; equal = flat)."}),
                "tail_start_denoise": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                                 "tooltip": "Denoise level for the inner trailing context frame (0.0 = frozen motion anchor, 1.0 = full denoise)."}),
                "tail_end_denoise": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                               "tooltip": "Denoise level for the outer trailing context frame (linearly interpolates across context_after; equal = flat)."}),
                "preserve_first_frame": ("BOOLEAN", {"default": True,
                                                     "tooltip": "Keep frame 0 untouched as the initial clean anchor and begin restoring at frame 1."}),
                "pad_start": ("BOOLEAN", {"default": True,
                                          "tooltip": "Repeat frame 0 on early chunks so the first chunk has the full lead + buffer_before window."}),
                "pad_end": ("BOOLEAN", {"default": True,
                                        "tooltip": "Repeat the last frame on final chunks so the last chunk keeps its full buffer_after + tail anchor."}),
                "freeze_audio": ("BOOLEAN", {"default": True,
                                             "tooltip": "When the input AV latent has real audio, freeze each chunk's synced audio slice (mask=0) to preserve lipsync."}),
                "vary_seed": ("BOOLEAN", {"default": True,
                                          "tooltip": "Increment noise seed per chunk (seed + chunk_idx) to prevent fixed-pattern noise burn-in."}),
                "frame_spacing": ("FLOAT", {"default": 1.0, "min": 0.25, "max": 8.0, "step": 0.25,
                                            "tooltip": "Pixel frames between consecutive latent frames on the RoPE time axis (1.0 = true per-frame)."}),
            },
            "optional": {
                "window_plan": ("H3_WINDOW_PLAN", {"tooltip": "Optional per-chunk schedule from 'H3 Re-Time Context Studio'. Overrides uniform chunk layout & per-chunk mask strengths."}),
                "split_conds_to_windows": ("BOOLEAN", {"default": False,
                                                       "tooltip": "Split multiple conditionings (created by ConditioningCombine) across rolling windows based on each window's timeline position, matching ComfyUI's native Context Windows behavior."}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "execute"
    CATEGORY = "advanced/model"

    def execute(self, model, commit_frames, context_before, buffer_before, buffer_after, context_after,
                lead_start_denoise, lead_end_denoise, tail_start_denoise, tail_end_denoise,
                preserve_first_frame, pad_start, pad_end, freeze_audio, vary_seed, frame_spacing,
                window_plan=None, split_conds_to_windows=False):
        m = model.clone()
        m.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL,
            WRAPPER_KEY,
            _make_timeline_wrapper(float(frame_spacing)),
        )
        m.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.OUTER_SAMPLE,
            ROLLING_OUTER_KEY,
            _make_rolling_outer_wrapper(
                commit_frames=commit_frames,
                context_before=context_before,
                buffer_before=buffer_before,
                buffer_after=buffer_after,
                context_after=context_after,
                lead_start_denoise=lead_start_denoise,
                lead_end_denoise=lead_end_denoise,
                tail_start_denoise=tail_start_denoise,
                tail_end_denoise=tail_end_denoise,
                preserve_first_frame=preserve_first_frame,
                pad_start=pad_start,
                pad_end=pad_end,
                freeze_audio=freeze_audio,
                vary_seed=vary_seed,
                window_plan=window_plan,
                split_conds_to_windows=bool(split_conds_to_windows),
            ),
        )
        return (m,)


class H3PerFrameDecode:
    DESCRIPTION = (
        "Decodes a per-frame MiniMax H3 latent one still frame at a time with single-load VRAM-aware "
        "batching and progress logging.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "vae": ("VAE", {"tooltip": "MiniMax H3 image/video VAE (e.g. minimax_h3_image_vae_fp16)."}),
                "samples": ("LATENT", {"tooltip": "Per-frame video or AV latent from SamplerCustomAdvanced."}),
            },
            "optional": {
                "batch_size": ("INT", {"default": 0, "min": 0, "max": 32,
                                       "tooltip": "0 = auto-size from free VRAM (safe across 8-32GB GPUs); >0 = fixed batch size (auto-halves on OOM)."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "model/latent/minimax"

    def execute(self, vae, samples, batch_size=0):
        z = _extract_video_latent(samples, "samples")
        n_dec = int(z.shape[2])
        pbar = comfy.utils.ProgressBar(n_dec)
        out_dev = comfy.model_management.intermediate_device()
        t_start = time.time()

        fsm = getattr(vae, "first_stage_model", None)
        is_h3_vae = fsm is not None and "MiniMaxH3" in type(fsm).__name__
        if is_h3_vae and hasattr(vae, "patcher"):
            lh, lw = int(z.shape[3]), int(z.shape[4])
            try:
                pf_mem = vae.memory_used_decode((1, VIDEO_CHANNELS, 1, lh, lw), vae.vae_dtype)
            except Exception:
                pf_mem = int(1.5 * (1024 ** 3) * (lh * lw) / (48 * 84))
            comfy.model_management.load_models_gpu([vae.patcher], memory_required=pf_mem)
            bs, mode = _pick_vae_batch_size(vae, pf_mem, n_dec, requested_bs=batch_size)
            logging.info(f"H3 Re-Time Decode: {n_dec} frames ({lw * 16}x{lh * 16}, batch={bs} [{mode}], vae={type(fsm).__name__})")
            dev, dt = vae.device, vae.vae_dtype
            out = []
            k = 0
            last_log = t_start
            with torch.no_grad():
                while k < n_dec:
                    cur_bs = min(bs, n_dec - k)
                    try:
                        # [1, 24, B, h, w] -> [B, 24, 1, h, w]
                        zb = z[:, :, k:k + cur_bs].permute(2, 1, 0, 3, 4).contiguous().to(device=dev, dtype=dt)
                        dec = fsm.decode(zb)  # [B, 3, 1, H, W] in [0, 1]
                        if dec.ndim == 5:
                            dec = dec.squeeze(2)
                        img = dec.movedim(1, -1).clamp(0.0, 1.0).to(device=out_dev, dtype=torch.float32)
                        out.append(img)
                        k += cur_bs
                        pbar.update(cur_bs)
                        now = time.time()
                        if k < n_dec and (now - last_log >= 2.0):
                            fps = k / max(now - t_start, 1e-3)
                            logging.info(f"  H3 Re-Time Decode: {k}/{n_dec} ({100.0 * k / n_dec:.0f}%) - {fps:.1f} fps")
                            last_log = now
                    except torch.cuda.OutOfMemoryError:
                        torch.cuda.empty_cache()
                        if bs > 1:
                            bs = max(1, bs // 2)
                            logging.warning(f"  H3 Re-Time Decode OOM, reducing batch size to {bs}")
                        else:
                            raise
            elapsed = time.time() - t_start
            logging.info(f"H3 Re-Time Decode: done {n_dec} frames in {elapsed:.2f}s ({n_dec / max(elapsed, 1e-3):.1f} fps)")
            return (torch.cat(out, dim=0),)

        logging.info(f"H3 Re-Time Decode: {n_dec} frames (fallback 1-by-1)")
        out = []
        for k in range(n_dec):
            img = vae.decode(z[:, :, k:k + 1])
            img = img.reshape((-1,) + tuple(img.shape[-3:]))[:1]
            out.append(img.to(out_dev))
            pbar.update(1)
        elapsed = time.time() - t_start
        logging.info(f"H3 Re-Time Decode: done {n_dec} frames in {elapsed:.2f}s ({n_dec / max(elapsed, 1e-3):.1f} fps)")
        return (torch.cat(out, dim=0),)


def _list_input_videos():
    """List video files inside ComfyUI's input directory (relative paths)."""
    items = ["(upstream input)", "(upstream images)"]
    try:
        inp = folder_paths.get_input_directory()
        if os.path.isdir(inp):
            found = []
            for dp, _, fns in os.walk(inp):
                for fn in fns:
                    if fn.lower().endswith(VIDEO_EXTENSIONS):
                        rel = os.path.relpath(os.path.join(dp, fn), inp).replace("\\", "/")
                        found.append(rel)
            items.extend(sorted(found))
    except Exception:
        pass
    return items


def _load_video_and_audio(path, skip_first_frames=0, frame_load_cap=0):
    """Load RGB frames [N,H,W,3] float32 in [0,1], fps, and optional AUDIO dict from a video file."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"H3PerFrameContextStudio: could not open video '{path}'")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    if fps <= 0:
        fps = 24.0
    if skip_first_frames > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(skip_first_frames))
    frames = []
    limit = int(frame_load_cap) if frame_load_cap > 0 else 10**9
    while len(frames) < limit:
        ok, bgr = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    cap.release()
    if not frames:
        raise ValueError(f"H3PerFrameContextStudio: no frames decoded from '{path}'")
    images = torch.from_numpy(np.stack(frames, axis=0).astype(np.float32) / 255.0)

    # Try extracting audio via PyAV (fast, no external subprocess)
    audio_out = None
    try:
        import av
        with av.open(path) as container:
            if container.streams.audio:
                stream = container.streams.audio[0]
                sr = int(stream.rate or 32000)
                chunks = []
                for frame in container.decode(stream):
                    arr = frame.to_ndarray()
                    if arr.ndim == 1:
                        arr = arr[None, :]
                    if arr.dtype == np.int16:
                        arr = arr.astype(np.float32) / 32768.0
                    elif arr.dtype == np.int32:
                        arr = arr.astype(np.float32) / 2147483648.0
                    else:
                        arr = arr.astype(np.float32)
                    chunks.append(arr)
                if chunks:
                    wf = np.concatenate(chunks, axis=-1)
                    if wf.shape[0] == 1:
                        wf = np.repeat(wf, 2, axis=0)
                    elif wf.shape[0] > 2:
                        wf = wf[:2]
                    start_s = int(round((skip_first_frames / fps) * sr))
                    dur_s = int(round((images.shape[0] / fps) * sr))
                    wf = wf[:, start_s:start_s + dur_s]
                    if wf.shape[-1] > 0:
                        audio_out = {"waveform": torch.from_numpy(wf).unsqueeze(0), "sample_rate": sr}
    except Exception as e:
        logging.debug(f"H3PerFrameContextStudio: audio decode skipped ({e})")

    return images, fps, audio_out


def _write_temp_preview_mp4(images, fps=24.0):
    """Write a lightweight H.264 preview MP4 into ComfyUI's temp dir for upstream IMAGE scrubbing."""
    temp_dir = folder_paths.get_temp_directory()
    os.makedirs(temp_dir, exist_ok=True)
    fname = f"h3_studio_preview_{int(time.time() * 1000) % 1000000}.mp4"
    out_path = os.path.join(temp_dir, fname)
    n, h, w, _ = images.shape
    # Downscale preview to max 640px wide (even dimensions) for instant writing & smooth UI scrubbing
    scale = min(1.0, 640.0 / max(w, 1))
    pw = max(2, int(round(w * scale)) // 2 * 2)
    ph = max(2, int(round(h * scale)) // 2 * 2)

    try:
        import av
        with av.open(out_path, mode="w") as container:
            stream = container.add_stream("libx264", rate=int(round(fps)))
            stream.width = pw
            stream.height = ph
            stream.pix_fmt = "yuv420p"
            stream.options = {"preset": "ultrafast", "crf": "26", "g": "1"}
            for i in range(n):
                rgb = (images[i, ..., :3].clamp(0.0, 1.0).cpu().numpy() * 255.0).astype(np.uint8)
                if rgb.shape[1] != pw or rgb.shape[0] != ph:
                    rgb = cv2.resize(rgb, (pw, ph), interpolation=cv2.INTER_AREA)
                vf = av.VideoFrame.from_ndarray(rgb, format="rgb24")
                for pkt in stream.encode(vf):
                    container.mux(pkt)
            for pkt in stream.encode():
                container.mux(pkt)
        return {"filename": fname, "subfolder": "", "type": "temp"}
    except Exception as e:
        logging.debug(f"H3PerFrameContextStudio: preview encode skipped ({e})")
        return None


def _build_default_plan(n_frames, preserve_first_frame, default_commit):
    start_idx = 1 if preserve_first_frame and n_frames > 1 else 0
    step = max(1, int(default_commit))
    chunks = []
    for t0 in range(start_idx, n_frames, step):
        t1 = min(n_frames, t0 + step)
        chunks.append({
            "commit_start": t0,
            "commit_end": t1,
            "context_before": 2,
            "buffer_before": 0,
            "buffer_after": 0,
            "context_after": 2,
            "lead_start_denoise": 0.0,
            "lead_end_denoise": 0.0,
            "tail_start_denoise": 0.0,
            "tail_end_denoise": 0.0,
            "chunk_denoise": 1.0,
            "cond_index": -1,
        })
    return {"frame_count": n_frames, "preserve_first_frame": bool(preserve_first_frame), "chunks": chunks}


class H3PerFrameContextStudio:
    DESCRIPTION = (
        "Interactive Context Studio for MiniMax H3 Re-Time Rolling Windows. "
        "Load a video file (or connect upstream images), scrub frame-by-frame, drag committed chunk "
        "boundaries, isolate any chunk to adjust its context/buffer frames & denoise strengths, or "
        "multi-select chunks for batch editing. Wire 'window_plan' into 'H3 Re-Time Rolling Windows'.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_file": (_list_input_videos(), {"tooltip": "Optional video file from ComfyUI/input (managed by Browse/Clear). Ignored when upstream 'video' or 'images' is connected."}),
                "frame_load_cap": ("INT", {"default": 0, "min": 0, "max": 10000,
                                           "tooltip": "0 = load all frames; >0 = cap loaded frames."}),
                "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "preserve_first_frame": ("BOOLEAN", {"default": True,
                                                     "tooltip": "Pin frame 0 as the initial clean anchor and start chunk 1 at frame 1."}),
                "default_commit": ("INT", {"default": 4, "min": 1, "max": 32,
                                           "tooltip": "Default committed frames per chunk when auto-generating or resetting the timeline."}),
                "schedule_json": ("STRING", {"default": "", "multiline": False,
                                             "tooltip": "Serialized per-chunk window plan (managed automatically by the Context Studio UI)."}),
            },
            "optional": {
                "video": ("VIDEO", {"tooltip": "Native ComfyUI VIDEO input (e.g. from LoadVideo / CreateVideo). Extracts frames, audio, and fps automatically."}),
                "images": ("IMAGE", {"tooltip": "Optional upstream video frames (used when 'video' is not connected)."}),
                "audio": ("AUDIO", {"tooltip": "Optional upstream audio passthrough (overrides video's audio track when connected)."}),
            },
        }

    RETURN_TYPES = ("H3_WINDOW_PLAN", "IMAGE", "AUDIO", "INT")
    RETURN_NAMES = ("window_plan", "images", "audio", "frame_count")
    FUNCTION = "execute"
    CATEGORY = "model/latent/minimax"
    OUTPUT_NODE = True

    def execute(self, video_file, frame_load_cap, skip_first_frames, preserve_first_frame,
                default_commit, schedule_json, video=None, images=None, audio=None):
        preview_info = None
        fps = 24.0
        audio_out = audio

        if video is not None:
            components = video.get_components()
            imgs = components.images
            fps = float(components.frame_rate or 24.0)
            if fps <= 0:
                fps = 24.0
            if skip_first_frames > 0:
                imgs = imgs[skip_first_frames:]
            if frame_load_cap > 0:
                imgs = imgs[:frame_load_cap]
            if imgs.shape[0] == 0:
                raise ValueError("H3PerFrameContextStudio: upstream 'video' has no frames after slicing")
            if audio_out is None and components.audio is not None:
                va = components.audio
                wf = va["waveform"]
                sr = int(va["sample_rate"])
                if skip_first_frames > 0 or frame_load_cap > 0:
                    start_s = int(round((skip_first_frames / fps) * sr))
                    dur_s = int(round((imgs.shape[0] / fps) * sr))
                    wf = wf[..., start_s:start_s + dur_s]
                if wf.shape[-1] > 0:
                    audio_out = {"waveform": wf, "sample_rate": sr}
            preview_info = _write_temp_preview_mp4(imgs, fps=fps)
        elif images is not None:
            imgs = images
            if skip_first_frames > 0:
                imgs = imgs[skip_first_frames:]
            if frame_load_cap > 0:
                imgs = imgs[:frame_load_cap]
            if imgs.shape[0] == 0:
                raise ValueError("H3PerFrameContextStudio: upstream images tensor is empty after slicing")
            preview_info = _write_temp_preview_mp4(imgs, fps=fps)
        else:
            if not video_file or video_file in ("(upstream input)", "(upstream images)"):
                raise ValueError("H3PerFrameContextStudio: connect upstream 'video'/'images' or select a video file")
            inp = folder_paths.get_input_directory()
            full = os.path.join(inp, video_file)
            if not os.path.isfile(full):
                raise FileNotFoundError(f"H3PerFrameContextStudio: video not found '{full}'")
            imgs, fps, loaded_audio = _load_video_and_audio(full, skip_first_frames, frame_load_cap)
            if audio_out is None:
                audio_out = loaded_audio
            sub = os.path.dirname(video_file).replace("\\", "/")
            preview_info = {"filename": os.path.basename(video_file), "subfolder": sub, "type": "input"}

        n_frames = int(imgs.shape[0])

        # Parse schedule_json if provided and valid; otherwise build default plan
        plan = None
        if schedule_json and schedule_json.strip():
            try:
                parsed = json.loads(schedule_json)
                if isinstance(parsed, dict) and isinstance(parsed.get("chunks"), list) and len(parsed["chunks"]) > 0:
                    plan = parsed
                    plan["frame_count"] = n_frames
            except Exception as e:
                logging.warning(f"H3PerFrameContextStudio: invalid schedule_json ({e}), falling back to default plan")
        if plan is None:
            plan = _build_default_plan(n_frames, preserve_first_frame, default_commit)

        # Provide a silent dummy audio dict only if None? Keep None so downstream handles optional audio cleanly.
        ui = {"frame_count": [n_frames], "fps": [fps]}
        if preview_info is not None:
            ui["preview_video"] = [preview_info]
        return {"ui": ui, "result": (plan, imgs, audio_out, n_frames)}


# ----------------------------------------------------------------------------------------------
# H3 Re-Time Temporal Stabilizer (Motion-Compensated Bilateral & Float32 Symmetric HQDN3D)
# ----------------------------------------------------------------------------------------------

def _rgb_to_ycbcr(rgb):
    """[B, 3, H, W] float32 in [0, 1] -> BT.709 YCbCr (Y in [0,1], Cb/Cr in [-0.5, 0.5])."""
    r, g, b = rgb[:, 0:1], rgb[:, 1:2], rgb[:, 2:3]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    cb = -0.1145721060573399 * r - 0.3854278939426601 * g + 0.5 * b
    cr = 0.5 * r - 0.4541529083058166 * g - 0.0458470916941834 * b
    return torch.cat([y, cb, cr], dim=1)


def _ycbcr_to_rgb(ycbcr):
    """BT.709 YCbCr -> [B, 3, H, W] float32 RGB in [0, 1]."""
    y, cb, cr = ycbcr[:, 0:1], ycbcr[:, 1:2], ycbcr[:, 2:3]
    r = y + 1.5748 * cr
    g = y - 0.1873242729306488 * cb - 0.4681242729306488 * cr
    b = y + 1.8556 * cb
    return torch.cat([r, g, b], dim=1).clamp_(0.0, 1.0)


def _spatial_bilateral_ycbcr(ycbcr, spatial_strength, motion_threshold):
    """Fast edge-preserving 5x5 spatial bilateral filter in YCbCr (GPU/CPU float32)."""
    if spatial_strength <= 1e-5:
        return ycbcr
    sigma_y = max(1e-4, motion_threshold * (0.6 + 1.4 * spatial_strength))
    sigma_c = max(1e-4, sigma_y * 1.5)
    pad = F.pad(ycbcr, (2, 2, 2, 2), mode="reflect")
    h, w = ycbcr.shape[2], ycbcr.shape[3]
    y0, c0 = ycbcr[:, 0:1], ycbcr[:, 1:3]
    acc_y = torch.zeros_like(y0)
    acc_c = torch.zeros_like(c0)
    w_y = torch.zeros_like(y0)
    w_c = torch.zeros_like(y0)
    inv_2sy2 = 0.5 / (sigma_y * sigma_y)
    inv_2sc2 = 0.5 / (sigma_c * sigma_c)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            sp_w = float(np.exp(-0.5 * (dx * dx + dy * dy) / 2.0))
            patch = pad[:, :, 2 + dy:2 + dy + h, 2 + dx:2 + dx + w]
            py, pc = patch[:, 0:1], patch[:, 1:3]
            dy_diff = py - y0
            dc_diff = pc - c0
            wy = sp_w * torch.exp(-(dy_diff * dy_diff) * inv_2sy2)
            wc = sp_w * torch.exp(-(dc_diff * dc_diff).sum(dim=1, keepdim=True) * inv_2sc2)
            acc_y += wy * py
            w_y += wy
            acc_c += wc * pc
            w_c += wc
    out_y = acc_y / w_y.clamp_min(1e-6)
    out_c = acc_c / w_c.clamp_min(1e-6)
    out = torch.cat([out_y, out_c], dim=1)
    return torch.lerp(ycbcr, out, min(1.0, spatial_strength))


def _make_base_grid(h, w, device):
    """[1, H, W, 2] pixel coordinates (x, y)."""
    ys = torch.arange(h, device=device, dtype=torch.float32)
    xs = torch.arange(w, device=device, dtype=torch.float32)
    gy, gx = torch.meshgrid(ys, xs, indexing="ij")
    return torch.stack([gx, gy], dim=-1).unsqueeze(0)


def _warp_with_flow(img_bchw, flow_hw2, base_grid):
    """Warp [1, C, H, W] using flow [1, H, W, 2] in pixel units (dx, dy)."""
    h, w = img_bchw.shape[2], img_bchw.shape[3]
    coords = base_grid + flow_hw2
    gx = 2.0 * coords[..., 0] / max(w - 1, 1) - 1.0
    gy = 2.0 * coords[..., 1] / max(h - 1, 1) - 1.0
    grid = torch.stack([gx, gy], dim=-1)
    return F.grid_sample(img_bchw, grid, mode="bilinear", padding_mode="border", align_corners=True)


def _compute_dis_flow(dis, gray_a, gray_b, target_h, target_w, scale):
    """Compute dense optical flow from gray_a -> gray_b, returned as [H, W, 2] float32 in full-res pixels."""
    flow = dis.calc(gray_a, gray_b, None)  # [sh, sw, 2] in scaled pixels
    if flow.shape[0] != target_h or flow.shape[1] != target_w:
        inv_s = 1.0 / scale
        flow = cv2.resize(flow, (target_w, target_h), interpolation=cv2.INTER_LINEAR) * inv_s
    return flow


def _flow_occlusion_weight(flow_ab, flow_ba, base_grid, occ_tol=1.5):
    """Forward-backward flow consistency weight in [0, 1] (0 on disocclusions / bad flow)."""
    # flow_ab, flow_ba: [1, H, W, 2]
    bwd_ch = flow_ba.permute(0, 3, 1, 2)  # [1, 2, H, W]
    warped_ba = _warp_with_flow(bwd_ch, flow_ab, base_grid).permute(0, 2, 3, 1)  # [1, H, W, 2]
    fb_err2 = ((flow_ab + warped_ba) ** 2).sum(dim=-1, keepdim=True)  # [1, H, W, 1]
    # Scale tolerance slightly with motion magnitude so fast rigid pans aren't over-rejected
    mag2 = (flow_ab ** 2).sum(dim=-1, keepdim=True)
    tol2 = (occ_tol * occ_tol) + 0.015 * mag2
    w = torch.exp(-0.5 * fb_err2 / tol2)
    return w.permute(0, 3, 1, 2)  # [1, 1, H, W]


class H3TemporalStabilizer:
    DESCRIPTION = (
        "Symmetric, boundary-free temporal stabilizer designed to pair with MiniMax H3 Re-Time Restore. "
        "Removes micro-shimmer and color breathing without the 4-frame / 17-frame blur of a Video VAE round-trip. "
        "Supports 'flow_bilateral' (motion-compensated symmetric bilateral with occlusion rejection), "
        "'flow_hqdn3d' (motion-compensated symmetric float32 HQDN3D), and 'hqdn3d' (classic symmetric float32 HQDN3D)."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Decoded video frames [N, H, W, 3] from H3 Re-Time Decode."}),
                "mode": (["flow_bilateral", "flow_hqdn3d", "hqdn3d"], {
                    "default": "flow_bilateral",
                    "tooltip": "flow_bilateral: symmetric motion-compensated bilateral (best all-around, zero ghosting); "
                               "flow_hqdn3d: motion-compensated symmetric float32 HQDN3D; "
                               "hqdn3d: classic symmetric float32 HQDN3D (fastest, best for locked-off cameras)."
                }),
                "luma_strength": ("FLOAT", {
                    "default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Temporal stabilization strength on brightness/detail (0.0 = untouched, 0.25-0.45 realistic, 0.15-0.30 anime)."
                }),
                "chroma_strength": ("FLOAT", {
                    "default": 0.50, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Temporal stabilization strength on color channels (suppresses color flicker without softening edges)."
                }),
                "spatial_strength": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Optional edge-preserving spatial denoising (0.0 = preserve 100% spatial sharpness)."
                }),
                "temporal_radius": ("INT", {
                    "default": 2, "min": 1, "max": 4,
                    "tooltip": "Symmetric frame radius for flow_bilateral (1 = 3-frame, 2 = 5-frame, 3 = 7-frame window)."
                }),
                "motion_threshold": ("FLOAT", {
                    "default": 0.08, "min": 0.005, "max": 0.5, "step": 0.005,
                    "tooltip": "Pixel difference cutoff above which motion/detail is preserved instead of blended (lower = crisper/safer, higher = stronger stabilization)."
                }),
                "flow_scale": ("FLOAT", {
                    "default": 0.5, "min": 0.25, "max": 1.0, "step": 0.25,
                    "tooltip": "Optical flow resolution scale (0.5 = fast & smooth, 1.0 = full resolution)."
                }),
                "mix": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Dry/wet blend with the original input frames (1.0 = full stabilized output)."
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "execute"
    CATEGORY = "image/postprocessing"

    def execute(self, images, mode, luma_strength, chroma_strength, spatial_strength,
                temporal_radius, motion_threshold, flow_scale, mix):
        n, h, w, c = images.shape
        if n <= 1 or mix <= 1e-5 or (luma_strength <= 1e-5 and chroma_strength <= 1e-5 and spatial_strength <= 1e-5):
            return (images,)

        t_start = time.time()
        device = comfy.model_management.get_torch_device()
        out_dev = images.device
        pbar = comfy.utils.ProgressBar(n)

        # Precompute uint8 grayscale frames at flow_scale if optical flow is used
        use_flow = mode in ("flow_bilateral", "flow_hqdn3d")
        grays = None
        dis = None
        if use_flow:
            sh = max(16, int(round(h * flow_scale)))
            sw = max(16, int(round(w * flow_scale)))
            dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
            grays = []
            for i in range(n):
                rgb_u8 = (images[i, ..., :3].clamp(0.0, 1.0).cpu().numpy() * 255.0).astype(np.uint8)
                g = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2GRAY)
                if sh != h or sw != w:
                    g = cv2.resize(g, (sw, sh), interpolation=cv2.INTER_AREA)
                grays.append(g)

        base_grid = _make_base_grid(h, w, device) if use_flow else None

        # Helper to load frame i to GPU YCbCr [1, 3, H, W] (with optional spatial pre-filter)
        ycbcr_cache = {}
        def get_ycbcr(idx):
            t = ycbcr_cache.get(idx)
            if t is None:
                rgb = images[idx:idx + 1, ..., :3].permute(0, 3, 1, 2).to(device=device, dtype=torch.float32)
                t = _rgb_to_ycbcr(rgb)
                if spatial_strength > 1e-5:
                    t = _spatial_bilateral_ycbcr(t, spatial_strength, motion_threshold)
                ycbcr_cache[idx] = t
            return t

        out_cpu = torch.empty((n, h, w, 3), dtype=torch.float32, device="cpu")
        thr_y = max(1e-4, float(motion_threshold))
        thr_c = max(1e-4, float(motion_threshold) * 1.4)
        scene_cut_thr = 0.35

        with torch.no_grad():
            if mode == "flow_bilateral":
                rad = max(1, min(int(temporal_radius), n - 1))
                # Cache pair flows (a, b) on CPU numpy while inside the sliding window
                flow_cache = {}
                def get_flow_gpu(a, b):
                    arr = flow_cache.get((a, b))
                    if arr is None:
                        arr = _compute_dis_flow(dis, grays[a], grays[b], h, w, flow_scale)
                        flow_cache[(a, b)] = arr
                    return torch.from_numpy(arr).unsqueeze(0).to(device=device, dtype=torch.float32)

                sigma_t = max(0.75, rad * 0.65)
                inv_2ty2 = 0.5 / (thr_y * thr_y)
                inv_2tc2 = 0.5 / (thr_c * thr_c)

                for i in range(n):
                    cur = get_ycbcr(i)
                    y0, c0 = cur[:, 0:1], cur[:, 1:3]
                    acc_y = y0.clone()
                    acc_c = c0.clone()
                    sum_wy = torch.ones_like(y0)
                    sum_wc = torch.ones_like(y0)

                    lo = max(0, i - rad)
                    hi = min(n - 1, i + rad)
                    for j in range(lo, hi + 1):
                        if j == i:
                            continue
                        nb = get_ycbcr(j)
                        # Quick scene-cut check
                        if float((nb[:, 0:1] - y0).abs().mean().item()) > scene_cut_thr:
                            continue
                        f_ij = get_flow_gpu(i, j)
                        f_ji = get_flow_gpu(j, i)
                        occ = _flow_occlusion_weight(f_ij, f_ji, base_grid)
                        warped = _warp_with_flow(nb, f_ij, base_grid)
                        wy_diff = warped[:, 0:1] - y0
                        wc_diff = warped[:, 1:3] - c0

                        dt = abs(j - i)
                        t_w = float(np.exp(-0.5 * (dt * dt) / (sigma_t * sigma_t)))
                        # Smooth range kernel scaled by strength (strength=0 -> neighbor weight 0)
                        if luma_strength > 1e-5:
                            wy = (t_w * luma_strength) * occ * torch.exp(-(wy_diff * wy_diff) * inv_2ty2)
                            acc_y += wy * warped[:, 0:1]
                            sum_wy += wy
                        if chroma_strength > 1e-5:
                            wc = (t_w * chroma_strength) * occ * torch.exp(-(wc_diff * wc_diff).sum(dim=1, keepdim=True) * inv_2tc2)
                            acc_c += wc * warped[:, 1:3]
                            sum_wc += wc

                    stab = torch.cat([acc_y / sum_wy, acc_c / sum_wc], dim=1)
                    rgb_out = _ycbcr_to_rgb(stab)[0].permute(1, 2, 0).cpu()
                    if mix < 0.9999:
                        rgb_out = torch.lerp(images[i, ..., :3].cpu().float(), rgb_out, float(mix))
                    out_cpu[i] = rgb_out
                    # Evict old entries outside sliding window
                    evict = i - rad - 1
                    if evict >= 0:
                        ycbcr_cache.pop(evict, None)
                        for k in list(flow_cache.keys()):
                            if k[0] <= evict or k[1] <= evict:
                                del flow_cache[k]
                    pbar.update(1)

            else:
                # Symmetric float32 HQDN3D (classic or motion-compensated)
                # Forward pass (0 -> N-1) and Backward pass (N-1 -> 0) averaged symmetrically
                def run_iir_pass(indices):
                    pass_out = [None] * n
                    state = None
                    prev_idx = None
                    for idx in indices:
                        cur = get_ycbcr(idx)
                        if state is None:
                            state = cur.clone()
                        else:
                            if float((cur[:, 0:1] - state[:, 0:1]).abs().mean().item()) > scene_cut_thr:
                                state = cur.clone()
                            else:
                                if use_flow:
                                    f_cp = torch.from_numpy(
                                        _compute_dis_flow(dis, grays[idx], grays[prev_idx], h, w, flow_scale)
                                    ).unsqueeze(0).to(device=device, dtype=torch.float32)
                                    f_pc = torch.from_numpy(
                                        _compute_dis_flow(dis, grays[prev_idx], grays[idx], h, w, flow_scale)
                                    ).unsqueeze(0).to(device=device, dtype=torch.float32)
                                    occ = _flow_occlusion_weight(f_cp, f_pc, base_grid)
                                    ref = _warp_with_flow(state, f_cp, base_grid)
                                else:
                                    occ = 1.0
                                    ref = state
                                dy = ref[:, 0:1] - cur[:, 0:1]
                                dc = ref[:, 1:3] - cur[:, 1:3]
                                ay = (luma_strength * occ) / (1.0 + (dy / thr_y) ** 2)
                                ac = (chroma_strength * occ) / (1.0 + (dc * dc).sum(dim=1, keepdim=True) / (thr_c * thr_c))
                                state = torch.cat([
                                    cur[:, 0:1] + ay * dy,
                                    cur[:, 1:3] + ac * dc,
                                ], dim=1)
                        pass_out[idx] = state.cpu()
                        prev_idx = idx
                    return pass_out

                fwd = run_iir_pass(range(n))
                bwd = run_iir_pass(range(n - 1, -1, -1))
                for i in range(n):
                    sym = 0.5 * (fwd[i].to(device) + bwd[i].to(device))
                    rgb_out = _ycbcr_to_rgb(sym)[0].permute(1, 2, 0).cpu()
                    if mix < 0.9999:
                        rgb_out = torch.lerp(images[i, ..., :3].cpu().float(), rgb_out, float(mix))
                    out_cpu[i] = rgb_out
                    pbar.update(1)

        elapsed = time.time() - t_start
        logging.info(
            f"H3 Re-Time Temporal Stabilizer ({mode}): {n} frames ({w}x{h}) in {elapsed:.2f}s "
            f"({n / max(elapsed, 1e-3):.1f} fps, luma={luma_strength:.2f}, chroma={chroma_strength:.2f})"
        )
        return (out_cpu.to(device=out_dev),)


NODE_CLASS_MAPPINGS = {
    "H3PerFrameContextStudio": H3PerFrameContextStudio,
    "H3PerFrameEncode": H3PerFrameEncode,
    "H3PerFramePrepareAV": H3PerFramePrepareAV,
    "H3PerFrameRollingWindows": H3PerFrameRollingWindows,
    "H3PerFrameDecode": H3PerFrameDecode,
    "H3TemporalStabilizer": H3TemporalStabilizer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3PerFrameContextStudio": "H3 Re-Time Context Studio",
    "H3PerFrameEncode": "H3 Re-Time Encode",
    "H3PerFramePrepareAV": "H3 Re-Time AV Latent",
    "H3PerFrameRollingWindows": "H3 Re-Time Rolling Windows",
    "H3PerFrameDecode": "H3 Re-Time Decode",
    "H3TemporalStabilizer": "H3 Re-Time Temporal Stabilizer",
}
