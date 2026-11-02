# ADR-010: Synthetic fixtures without real videos or API keys

## Status

Accepted

## Context

CI must stay offline and deterministic. Real SAP videos and Whisper model downloads are unsuitable for automated tests.

## Decision

Tests use synthetic media stubs, canned transcript JSON, and fake Whisper/OCR/LLM adapters. Optional extras install real engines for local development only.

## Consequences

Integration tests never require network access or credentials. Developers opt into `[whisper]` for real transcription.
