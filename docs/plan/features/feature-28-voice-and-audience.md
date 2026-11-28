# Feature 28: VOICE.md and AUDIENCE.md

Design note: [design/features/feature-28-voice-and-audience.md](../../design/features/feature-28-voice-and-audience.md)

*✅ Built as skeletons; in v0.6.0.* The user fills in the `<<…>>` notes. Two short files at the repo root,
imported by CLAUDE.md (`@VOICE.md`, `@AUDIENCE.md`), so every session
writes for the right reader.

**Settled:**
- **Audience:** everyday GNOME / Ubuntu desktop users read the README
  and the UI; contributors (people and Claude) read `docs/`.
- **Voice:** plain, short sentences; GNOME HIG wording and capitalisation
  in the UI; no hype; American spelling ("color"); say what a thing
  does, not how it was built.

| Step | Create / change | Test |
|---|---|---|
| F28.1 | `AUDIENCE.md`, `VOICE.md` (one screen each, examples of do and don't) | Read through |
| F28.2 | CLAUDE.md imports both | `test_docs`: CLAUDE.md names both files and they exist |
