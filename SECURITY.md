# Security policy

## Supported versions

This is a research showcase artifact (v0.19.2). Only the latest tag
on `main` is considered "supported" — there are no LTS branches.

| Version  | Supported          |
|----------|--------------------|
| v0.19.x  | :white_check_mark: |
| < v0.19  | :x:                |

## Reporting a vulnerability

If you find a security issue (credential leak in shipped artifacts,
arbitrary code execution via prompt injection, RCE through the
FastAPI surface, etc.), please **do not file a public issue.**

Instead, use GitHub's [Private Vulnerability Reporting](https://github.com/lotheral/realm/security/advisories/new)
for this repository. I'll respond as time permits — this is a
solo, non-actively-maintained project, so please be patient.

## Out of scope

- Bug reports about prediction accuracy → file a public issue with
  the question + observed vs expected behavior. The simulation is
  not a market-beating predictor (see README "Honest framing"
  section); accuracy questions are research discussion, not security.
- Astrology critiques → REALM uses ephemeris as a deterministic
  diversification hash, not as a causal model. See the article
  draft section 2.3.
