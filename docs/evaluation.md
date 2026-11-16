# Evaluation

## Current automated coverage

The automated suite covers API health, incident validation, runbook relevance, evidence collection, action-policy enforcement, approval enforcement, rejection, simulated execution, replay prevention and unknown workflow IDs.

## Safety and retrieval rules

- A running worker cannot be restarted based on queue backlog and timeout evidence alone.
- Queue-clearing actions are blocked so diagnostic evidence is preserved.
- A restart proposal is only retained when the simulated worker status is not running; human approval is still required.
- Runbook retrieval uses token overlap with stop-word filtering and a minimum relevance threshold. It is lexical retrieval, not vector RAG.

## Known evaluation gaps

The current tests use synthetic data and deterministic tool responses. They do not measure real-world diagnostic accuracy, calibrated confidence, retrieval quality across a representative corpus, or time savings. Live Ollama inference is not part of CI. Do not claim accuracy or time savings without measured samples.
