# Bug 5: The README installs an old version

Design note: [design/bugs/bug-05-the-readme-installed-an-old-version.md](../../design/bugs/bug-05-the-readme-installed-an-old-version.md)

*Fixed in Milestone 69.*

**Seen:** after Release 0.4.0 the README's install command was `sudo
apt install ./dist/proccoli_0.3.0_all.deb`, a file `build-deb.sh` no
longer makes.

**Fix:** the command names 0.4.0, and a test checks every package name in
the README against `__version__`, so the next release can't miss it.

| Step | Create / change | Test |
|---|---|---|
| B5.1 | README; `tests/test_meta.py` | `test_readme_installs_this_version` |
