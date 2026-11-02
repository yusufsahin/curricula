# ADR-008: TOML + environment + CLI configuration

## Status

Accepted

## Context

Local defaults must be reproducible while allowing per-run overrides.

## Decision

Load configuration in precedence order: `config/default.toml` < `CURRICULA_*` environment variables < CLI flags.

## Consequences

Tests inject config objects directly. Operators can override `--db` and `--data-dir` without editing files.
