# Pipeline contracts

## StageResult

Every stage returns a list of `StageResult` envelopes:

- `stage`: stage name (`ingest`, `transcribe`, ...)
- `status`: `completed` | `failed` | `skipped`
- `job_id`: UUID of the `ProcessingJob` row
- `fingerprint`: input fingerprint string
- `artifacts`: filesystem paths written
- `metrics`: timing and counters
- `error`: optional error message

## Fingerprints

| Stage | Fingerprint inputs |
| --- | --- |
| ingest | file SHA-256 |
| transcribe | `video.sha256`, model name/version, language, normalize version |
| extract-visuals | video hash, scene detector version, OCR engine version |
| discover-topics | transcript + visual artifact hashes, taxonomy + prompt versions |
| map-curriculum | topic set hash, mapper version |
| analyze-gaps | curriculum map hash, reference curriculum hash |
| enrich | topic + gap fingerprint, model, prompt version |
| export | approved content hash, exporter version |

## Requests

- `IngestRequest(course_slug, video_paths, force=False)`
- `TranscribeRequest(video_ids=None, model_size="medium", language="tr", force=False)`
- Later phases follow the same request/service protocol pattern.

## Orchestration

`course run --from STAGE --to STAGE` executes the inclusive stage range. Phase 1 supports `ingest` through `transcribe` only.
