# ADR-001: Local-first modular monolith

## Status

Accepted

## Context

We need a production-oriented system that transforms Turkish SAP ABAP training videos into a structured curriculum. Early cloud microservices would add operational cost without clear benefit for a local-first workflow.

## Decision

Ship a single installable Python package (`course`) with clear domain modules, a Typer CLI, SQLite as the system of record, and a FastAPI surface deferred until needed.

## Consequences

Modules communicate through typed protocols and the repository layer. Scaling later may require extracting services, but the domain boundaries already anticipate that split.
