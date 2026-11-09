# MT6895 / Mali-G610 MC6 — validation plan

Last updated: 2026-11-09

## Device baseline

- SoC: MediaTek MT6895
- GPU: Mali-G610 MC6, Valhall v10, CSF
- Kernel: 5.10.260 Android 12 common branch
- Kbase: `r32p1-01eac0`, UK uAPI 1.18
- Android: 16 / API 36
- System Vulkan: OEM driver is left untouched

## Confirmed with PanProbe 1.3.2 + imported PanVK

Driver identity:
- Imported Android ARM64 ICD, release package `panvk-kbase-v26.3.1`
- PanProbe reports Mesa `26.3.0-devel`, git `795ca7ff3e`, patch `p0175`
- GPU ID `0xa8670000`
- PanProbe reports successful driver load without vendor ICD fallback
- Run All: 41 PASS, 0 FAIL

Kernel / GPU execution:
- CSF queue-group creation and event path passed
- Submit stress passed: 53,721 submissions / render passes in 30 seconds
- Memory allocation fell back from `KBASE_IOCTL_MEM_ALLOC_EX` to `KBASE_IOCTL_MEM_ALLOC`; the fallback allocation succeeded

Android WSI:
- PanProbe uses `ANativeWindow_fromSurface`, `vkCreateAndroidSurfaceKHR`, a real Android Surface, and a Vulkan graphics pipeline
- 300 presents, resize/recreate, 120 resized presents, plus repeated create/present/destroy cycles passed
- Main 300-frame phase: approximately 122 FPS at 912×480
- The PanVK Android WSI patch allocates driver-owned AHardwareBuffers and copies rendered pixels to the Android window; this is not a zero-copy claim

Gralloc / AHB:
- Vendor Gralloc mapper could not be loaded from the app namespace; mapper metadata was unavailable
- The driver-owned-AHB fallback verified a linear RGBA8888 layout with `match=9/9` on 36 logged occurrences
- This proves the owned swapchain AHB fallback on this device; it does not prove arbitrary external AHB import, MediaCodec buffers, or video zero-copy

## Remaining unknowns

- Sustained rendering in a real application / game
- DXVK D3D11 application compatibility and visual correctness
- D3D9 / 32-bit compatibility
- External application AHardwareBuffer import
- MediaCodec / video buffer interoperability
- Long-session memory stability, thermal throttling and GPU fault behaviour
- Native vendor mapper discovery and zero-copy Gralloc path

## Next test: controlled DXVK D3D11 rendering

Preferred host application: PanPlay 1.3.1 or later.

1. Keep the OEM Android Vulkan driver untouched. PanVK is selected only inside PanPlay.
2. Use the Mesa PanVK 26.3.1 driver. PanPlay supports both its bundled driver and imported driver packages; it also allows a per-game driver override.
3. Start with a controlled D3D11 sample (rotating cube / draw-and-texture sample), not a large game. Set Render API to DXVK or Auto when D3D11 is correctly detected.
4. Capture a screenshot while the scene is moving, record the reported FPS, and retain the full PanPlay session log even if the app crashes.
5. Only after D3D11 is stable, test D3D9 and 32-bit execution. Defer D3D12 until the D3D11 path is understood.

PanPlay release: https://github.com/zenithblue-oss/panplay/releases/tag/panplay-v1.3.1
PanVK release: https://github.com/zenithblue-oss/panvk-kbase-android/releases/tag/panvk-kbase-v26.3.1

## Evidence handling

- Upload new ZIP bundles to `incoming/` in this repository.
- The `Inspect uploaded diagnostic archives` workflow runs on a ZIP push and uploads a text report as a GitHub Actions Artifact.
- Keep the original ZIP in GitHub; do not paste large logs into chat.
- Include device, app, test/API, driver version, and run number in the filename where practical.
- Before uploading to this public repository, remove tokens, credentials, and unrelated personal data.
