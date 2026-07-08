param(
  [Parameter(Mandatory=$true)]
  [string]$RunpodApiKey,

  [string]$ImageName = "ghcr.io/adamsontech/fusioninteract-ace-step-serverless-worker:latest",
  [string]$TemplateName = "fusioninteract-ace-step-serverless",
  [string]$EndpointName = "fusioninteract-ace-step-music",
  [string]$NetworkVolumeId = "wsta77wxv4",
  [string]$GpuType = "NVIDIA RTX PRO 6000 Blackwell Server Edition",
  [int]$WorkersMax = 1,
  [int]$WorkersMin = 0,
  [int]$WorkersStandby = 0
)

$ErrorActionPreference = "Stop"
$headers = @{
  Authorization = "Bearer $RunpodApiKey"
  "Content-Type" = "application/json"
}
$baseUrl = "https://rest.runpod.io/v1"

$envVars = @{
  ACESTEP_CONFIG_PATH = "acestep-v15-xl-sft"
  ACESTEP_LM_MODEL_PATH = "acestep-5Hz-lm-4B"
  ACESTEP_LM_BACKEND = "vllm"
  ACESTEP_INIT_LLM = "true"
  ACESTEP_DOWNLOAD_SOURCE = "huggingface"
  ACESTEP_CHECKPOINTS_DIR = "/runpod-volume/ace-step-models"
  ACESTEP_OUTPUT_FORMAT = "wav"
  ACESTEP_DEFAULT_DURATION_SECONDS = "60"
  ACESTEP_DEFAULT_INFERENCE_STEPS = "64"
  ACESTEP_DEFAULT_GUIDANCE_SCALE = "7.0"
  ACESTEP_DEFAULT_BATCH_SIZE = "1"
  ACESTEP_DEFAULT_THINKING = "true"
  ACESTEP_API_START_TIMEOUT_SECONDS = "1800"
  ACESTEP_POLL_ATTEMPTS = "720"
  ACESTEP_POLL_SLEEP_SECONDS = "5"
}

$templateBody = @{
  category = "NVIDIA"
  containerDiskInGb = 120
  dockerEntrypoint = @()
  dockerStartCmd = @()
  env = $envVars
  imageName = $ImageName
  isPublic = $false
  isServerless = $true
  name = $TemplateName
  ports = @()
  readme = "FusionInteract ACE-Step 1.5 RunPod Serverless worker."
  volumeInGb = 0
  volumeMountPath = "/runpod-volume"
}

$template = Invoke-RestMethod -Method Post -Uri "$baseUrl/templates" -Headers $headers -Body ($templateBody | ConvertTo-Json -Depth 8)

$endpointBody = @{
  allowedCudaVersions = @("12.8", "12.9", "13.0")
  computeType = "GPU"
  executionTimeoutMs = 3600000
  flashboot = $true
  gpuCount = 1
  gpuTypeIds = @($GpuType)
  idleTimeout = 30
  name = $EndpointName
  networkVolumeId = $NetworkVolumeId
  networkVolumeIds = @($NetworkVolumeId)
  scalerType = "QUEUE_DELAY"
  scalerValue = 4
  templateId = $template.id
  workersMax = $WorkersMax
  workersMin = $WorkersMin
  workersStandby = $WorkersStandby
}

$endpoint = Invoke-RestMethod -Method Post -Uri "$baseUrl/endpoints" -Headers $headers -Body ($endpointBody | ConvertTo-Json -Depth 8)

[pscustomobject]@{
  TemplateId = $template.id
  TemplateName = $template.name
  EndpointId = $endpoint.id
  EndpointName = $endpoint.name
  ImageName = $ImageName
  NetworkVolumeId = $NetworkVolumeId
} | ConvertTo-Json -Depth 5
