# FusionInteract ACE-Step Serverless Worker

RunPod Serverless worker for open-source text-to-music generation with ACE-Step 1.5.

Default production quality target for the 96 GB Pro endpoint:

- DiT model: `acestep-v15-xl-sft`
- LM model: `acestep-5Hz-lm-4B`
- LM backend: `vllm`
- `thinking=true`
- `use_format=true`
- output: `wav`
- duration: 60 seconds
- inference steps: 64
- batch size: 1

The worker starts the ACE-Step REST API locally, submits a task to `/release_task`, polls `/query_result`, downloads the generated audio from `/v1/audio`, and optionally uploads the audio to Bunny Storage.

## Input

```json
{
  "input": {
    "request_id": "project-or-job-id",
    "title": "system-overload-music-bed",
    "prompt": "cinematic synth rock instrumental, tense futuristic energy, no vocals",
    "lyrics": "",
    "duration_seconds": 60,
    "audio_format": "wav",
    "thinking": true,
    "use_format": true,
    "model": "acestep-v15-xl-sft",
    "lm_model_path": "acestep-5Hz-lm-4B",
    "inference_steps": 64,
    "guidance_scale": 7.0,
    "batch_size": 1,
    "upload_prefix": "media/fusioninteract/generated/music/job-id"
  }
}
```

Reference/repaint style tasks can stage audio into the worker before submitting to ACE-Step:

```json
{
  "input": {
    "prompt": "turn this into a cinematic trailer cue",
    "source_audio_url": "https://example.com/source.wav",
    "source_audio_extension": "wav",
    "task_type": "repaint",
    "audio_format": "wav"
  }
}
```

## Environment

Set these in the RunPod endpoint:

```text
ACESTEP_CONFIG_PATH=acestep-v15-xl-sft
ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-4B
ACESTEP_LM_BACKEND=vllm
ACESTEP_INIT_LLM=true
ACESTEP_DOWNLOAD_SOURCE=huggingface
ACESTEP_CHECKPOINTS_DIR=/runpod-volume/ace-step-models
ACESTEP_OUTPUT_FORMAT=wav
ACESTEP_DEFAULT_DURATION_SECONDS=60
ACESTEP_DEFAULT_INFERENCE_STEPS=64
ACESTEP_DEFAULT_GUIDANCE_SCALE=7.0
ACESTEP_DEFAULT_BATCH_SIZE=1
ACESTEP_DEFAULT_THINKING=true
BUNNY_STORAGE_ZONE=fusion-interact
BUNNY_STORAGE_ACCESS_KEY=...
BUNNY_PUBLIC_BASE_URL=https://fusioninteract.b-cdn.net
```

Attach a RunPod network volume so `/runpod-volume/ace-step-models` survives cold starts.

Do not commit API keys, Bunny keys, or endpoint secrets.

## Install / Build

ACE-Step's official install flow is:

```bash
git clone https://github.com/ace-step/ACE-Step-1.5.git
cd ACE-Step-1.5
uv sync
uv run acestep-api
```

This worker wraps that API for RunPod Serverless. The Dockerfile uses the official ACE-Step image, installs the RunPod worker dependency, then starts `handler.py`.

Build on a machine with Docker:

```powershell
.\scripts\build-image.ps1 -Image your-registry/fusioninteract-ace-step:latest -Push
```

Linux/macOS:

```bash
IMAGE=your-registry/fusioninteract-ace-step:latest PUSH=true ./scripts/build-image.sh
```

Run a local syntax smoke test:

```powershell
.\scripts\smoke-test.ps1 -Python "C:\path\to\python.exe"
```

This desktop does not need to contain the generated models. Attach a RunPod network volume and set `ACESTEP_CHECKPOINTS_DIR=/runpod-volume/ace-step-models` so model downloads survive cold starts.

For a local Windows ACE-Step API install, use:

```powershell
.\scripts\install-local-windows.ps1 -InstallDir C:\ace-step\ACE-Step-1.5
```

Then launch:

```powershell
cd C:\ace-step\ACE-Step-1.5
uv run acestep-api --host 127.0.0.1 --port 8001
```

## Output

```json
{
  "ok": true,
  "provider": "ace_step",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "acestep-v15-xl-sft",
  "lm_model_path": "acestep-5Hz-lm-4B",
  "thinking": true,
  "audio_format": "wav",
  "duration_seconds": 60,
  "output_count": 1,
  "outputs": [
    {
      "file_name": "ace-step-output-1.wav",
      "content_type": "audio/wav",
      "url": "https://.../system-overload-music-bed-1.wav",
      "metadata": {
        "metas": {
          "bpm": 120,
          "duration": 60
        }
      }
    }
  ],
  "timing": {
    "submit_seconds": 1.2,
    "total_seconds": 180.4
  }
}
```
