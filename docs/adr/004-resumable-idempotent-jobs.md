# ADR-004: Resumable and idempotent pipeline jobs

## Status

Accepted

## Context

Whisper and OCR runs are long. Crashes and re-runs must not duplicate expensive work or corrupt artifacts.

## Decision

Every stage creates or updates a `ProcessingJob` keyed by `(stage, input_fingerprint)`. Completed jobs with a matching fingerprint are skipped unless `--force` is set. Source artifacts are never overwritten; new versions go through `ArtifactVersion`.

## Consequences

Fingerprints must include model and normalizer versions. Operators use `--force` for intentional recomputation.
