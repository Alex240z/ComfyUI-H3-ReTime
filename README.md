# ComfyUI-H3-ReTime

**H3 Re-Time** — per-frame (temporally uncompressed) autoregressive restoration, retiming, and timeline control for the **MiniMax H3 video model**.

Normal MiniMax H3 latents pack `1 + 4 + 4 + 4 + 4` pixel frames into 5 latent frames. **H3 Re-Time** encodes **each pixel frame individually** (1 latent = 1 pixel frame), runs overlapping autoregressive rolling windows in a single sampler pass with per-frame RoPE retiming and 1-to-1 frame-synced audio, and decodes all frames in one batched pass at the end.

## Install

1. Copy (or `git clone`) `ComfyUI-H3-ReTime` into `ComfyUI/custom_nodes/` and restart ComfyUI.
2. Download the companion per-frame LoRA (**`H3-Re-Time-v1.safetensors`**) from Hugging Face:
   - https://huggingface.co/Alex240z/H3-Re-Time-v1
   - Place it in `ComfyUI/models/loras/` (load at strength `1.0` alongside your MiniMax H3 model).
3. Drag [H3-Re-Time-WF.json](H3-Re-Time-WF.json) into ComfyUI for a ready-to-run example workflow.

## Nodes

| Node | Purpose |
|---|---|
| **H3 Re-Time Context Studio** | Interactive video player & per-chunk timeline editor for controlling chunk boundaries, context/buffer frames, per-chunk denoise, explicit conditioning indices (`Cond #`), and update-safe user presets (`ComfyUI/user/h3_context_studio_presets.json`). |
| **H3 Re-Time Encode** | Encodes each frame individually via the VAE's still-frame path into `[1, 24, N, h, w]`, with VRAM-aware auto batching (`batch_size = 0`) and progress logging. |
| **H3 Re-Time AV Latent** | Optional helper that pairs the per-frame video latent with synced audio (or silent placeholder audio if the clip has no audio track). Alternatively use `VAEEncodeAudio` + `LTXVConcatAVLatent`. |
| **H3 Re-Time Rolling Windows** | Model patch that applies per-frame RoPE retiming and runs autoregressive rolling windows (`[lead \| buffer_before \| commit \| buffer_after \| tail]`) inside a single `SamplerCustomAdvanced` pass — with live chunk previews (`TAEH3`, `Latent2RGB`, and `ModelPreviewOverrideKJ`), audio generation/lip-sync, and per-window conditioning splitting. |
| **H3 Re-Time Decode** | Decodes all per-frame latents back to images with VRAM-aware auto batching (`batch_size = 0`) and progress logging. |
| **H3 Re-Time Temporal Stabilizer** | Symmetric, boundary-free temporal stabilizer (`flow_bilateral`, `flow_hqdn3d`, `hqdn3d`) in float32 YCbCr with DIS optical flow & occlusion rejection — stabilizes shimmer without 4-frame / 17-frame Video VAE blur. |

## Recommended Wiring

```text
H3 Re-Time Context Studio (or LoadVideo / VHS_LoadVideo)
  ├─ images      -> H3 Re-Time Encode -> H3 Re-Time AV Latent (or LTXVConcatAVLatent + VAEEncodeAudio)
  ├─ audio       ──────────────────────┘
  └─ window_plan ───────────────────────────────────────┐
                                                        ↓
UNET -> LoRA(s) -> H3 Re-Time Rolling Windows -> BasicGuider
                                                        ↓
                                            SamplerCustomAdvanced
                                                        ↓
                        H3 Re-Time Decode -> (optional H3 Re-Time Temporal Stabilizer) -> CreateVideo / SaveVideo
```

## Notes

- **VAE:** `minimax_h3_image_vae_fp16.safetensors` is recommended for fast, low-VRAM per-frame encode/decode.
- **Batch size:** Leave `batch_size = 0` (Auto) to automatically pick a VRAM-safe batch size across 8–32 GB GPUs (auto-halves on OOM).
- **Defaults & Masks:** Default window layout is `commit=4, context_before=2, context_after=2, buffer=0`. Hard `0.0` lead/tail denoise (`lead_start_denoise=0, lead_end_denoise=0, tail_start_denoise=0, tail_end_denoise=0`) avoids mid-denoise ghosting on stepped motion.
- **Per-window conditioning:** Combine multiple prompts with ComfyUI's **ConditioningCombine** node, then either enable `split_conds_to_windows` on **H3 Re-Time Rolling Windows** (even timeline split) or set **Cond #** (`0, 1, 2...` or `Auto`) explicitly per chunk in **H3 Re-Time Context Studio** (supports multi-select batch editing).
- **Audio:** Set `freeze_audio = True` when lip-syncing to an input song/dialogue track, or `freeze_audio = False` to generate new audio across rolling windows.
- **Exporting crisp video:** ComfyUI's default `SaveVideo` H.264 uses `bframes=3`, which can introduce a 1-in-4 B-frame softness cadence on anime. Use `format = mov` + `codec = prores` (all-intra) or `SaveImage` (PNG) for lossless inspection.
