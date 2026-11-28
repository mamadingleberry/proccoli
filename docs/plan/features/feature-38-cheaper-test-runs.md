# Feature 38: Cheaper test runs for the agent

Design note: [design/features/feature-38-cheaper-test-runs.md](../../design/features/feature-38-cheaper-test-runs.md)

*Open.* Asked: refactor tests or run them on a local Jenkins (or
similar) so test results cost the agent fewer tokens.

**Measured (2026-11-28):**

| Run | Output | ≈ tokens if read whole | Wall time |
|---|---|---|---|
| `make test` (`-v`: one line per test) | 146 KB, 1 341 lines | ~36 000 | 10 s |
| `make ui-test` (tests + 43 screenshots) | 144 KB, 1 417 lines | ~36 000 | ~90 s tests, several minutes of screenshots |
| Either, filtered to the summary lines | ~40 bytes | ~15 | same |
| A failure's traceback | 1–6 KB | ~300–1 500 | – |

In practice the agent pipes runs through `grep`/`tail`, so a passing run
costs tens of tokens, and the session's test output is a small share of
its cost (reading source and writing changes dominate). The risk is the
unfiltered run (one mistake costs ~36 000 tokens) and long screenshot
waits, not the routine run.

**Options:**

| | How | For | Against |
|---|---|---|---|
| A | **Quiet by default:** `make test` without `-v`; a `make check` that prints one summary line and, for failures only, the test name and a short traceback (a small runner over `unittest`); `make test-verbose` keeps today's output | Removes the 36 000-token trap; no new service; humans still get detail on demand | A runner to keep |
| B | **Run only what changed:** `make check-changed` maps changed files to their test modules (import graph), then the full suites before "done" | Faster loops, smaller output | A mapping to keep right; full runs still needed |
| C | **Screenshots apart:** `make ui-test` runs the tests only; `make screenshots` the scenes, in the background, when a visual change asks for them | Minutes off every UI run | Screenshots checked less often |
| D | **A local CI (Jenkins, or a lighter runner such as a git hook or `act` for GitHub Actions):** runs on commit, the agent reads a one-line status | Tests run without the agent waiting | A service to install, secure and keep up; the agent still needs failures' details, so the token saving over A is small |
| E | **GitHub Actions on pull requests** | Checks every change in a clean machine; useful for people too | Needs a headless GTK display in CI; no token saving by itself |

**Recommendation:** A and C now (small, removes the expensive cases),
B later if loops feel slow; D isn't worth a service for one developer,
since its saving over A is small; E is worth having for its own sake.

| Step | Create / change | Test |
|---|---|---|
| F38.1 | `tests/run_quiet.py` (summary line; failures with short tracebacks); `make check`, `make test` quiet, `make test-verbose` | Unit: a passing and a failing fake suite give the expected lines |
| F38.2 | `make ui-test` without screenshots; `make screenshots` (already there) runs them | – |
| F38.3 | `software-testing` / `proccoli-engineer`: run `make check`; full output only to read a failure | Read through |

**Open questions for the user:** see the plan's options; which of A–E?
