# ADR-006: Human approval before publishing AI material

## Status

Accepted

## Context

AI-generated explanations and assessments must not be published unchecked.

## Decision

`ContentBlock` and `Assessment` cannot transition to `published` without a `ReviewDecision` of `approved`. Enforcement lives in the repository/service layer, not only the CLI.

## Consequences

Enrichment always writes drafts. Review commands are required for publish workflows.
