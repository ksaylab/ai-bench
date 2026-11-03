# Battery changelog

Every change to a battery, with the reason, so the pruning (METHODOLOGY.md 8.3) is public. Each change makes a new
battery version (`battery` in `meta.json`): runs of different versions are never merged or compared.

## 2026-11-03

- All batteries: every case gets a `tier` (`easy`, `medium`, `hard`), tagged by hand before any anchor run (best
  effort; to be revisited with the first pruning report). No case removed.
- New reference battery `coding_public` (`cases/coding_public/`): 5 HumanEval and 5 MBPP (sanitized) problems, with
  `source` and `license` on every case and the attribution in `cases/coding_public/NOTICE.md`. Not part of the
  verdict.
