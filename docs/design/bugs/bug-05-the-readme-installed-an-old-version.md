# Bug 5: The README installed an old version

Plan: [plan/bugs/bug-05-the-readme-installs-an-old-version.md](../../plan/bugs/bug-05-the-readme-installs-an-old-version.md)


*[PLAN.md, Bug 5](../../plan/bugs/bug-05-the-readme-installs-an-old-version.md). Fixed in Milestone 69.* After 0.4.0 the README's
install command still named `proccoli_0.3.0_all.deb`. **Fix:** the
command names 0.4.0, and `test_meta` checks every package name in the
README against `__version__`.
