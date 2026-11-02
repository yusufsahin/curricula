# ADR-009: Artifacts on disk, metadata in the database

## Status

Accepted

## Context

Transcripts, frames, and exports are large and benefit from filesystem inspection.

## Decision

Store blobs under `data/` (audio, transcripts, frames, exports). The database stores paths, hashes, and provenance metadata only.

## Consequences

Backups must include both `data/` and the SQLite file. Paths are relative to the configured data directory when possible.
