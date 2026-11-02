# ADR-005: Provider-agnostic LLM via LiteLLM

## Status

Accepted

## Context

Enrichment and topic labeling need LLMs, but providers change and tests must run offline.

## Decision

All generative calls go through an `LLMClient` protocol. LiteLLM is the production adapter. Tests use a fake client. Phase 1 ships only the protocol and a no-op adapter.

## Consequences

Domain code never imports a vendor SDK directly. Cost and model version are recorded on `ProcessingJob`.
