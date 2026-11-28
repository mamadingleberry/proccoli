# Convenience wrapper; everything also works without make:
#   PYTHONPATH=src python3 -m proccoli
#   python3 -m unittest discover -s tests

PYTHON ?= python3
PREFIX ?= /usr/local
DESTDIR ?=

.PHONY: all run demo test test-verbose ui-test ui-test-verbose check screenshots install uninstall deb icons clean

all:
	@true

run:
	PYTHONPATH=src $(PYTHON) -m proccoli

demo:
	PYTHONPATH=src $(PYTHON) -m proccoli --demo

# The tests that need no display. Quiet: one line when all pass, else each
# failure in short (tests/run_quiet.py); test-verbose prints every test.
test:
	@$(PYTHON) tests/run_quiet.py

test-verbose:
	$(PYTHON) -m unittest discover -s tests -v

# All tests, the widget and window tests too, on a private headless display.
# Screenshots are their own target (make screenshots), for visual changes.
ui-test:
	@tests/run-headless.sh $(PYTHON) tests/run_quiet.py

ui-test-verbose:
	tests/run-headless.sh $(PYTHON) -m unittest discover -s tests -v

# Everything, quietly: what to run before saying a change is done.
check: ui-test

# The README's screenshots, from the made-up demo devices only (never this
# machine's own hardware or processes): shoot every scene, keep six.
README_SHOTS = wide-overview demo-gpu-details offline-dark demo-gpu-processes \
	wide-sidebar-icons palette-solarized-dark

screenshots:
	tests/run-headless.sh $(PYTHON) tests/ui/shoot.py tests/ui/out
	mkdir -p docs/screenshots
	for shot in $(README_SHOTS); do cp tests/ui/out/$$shot.png docs/screenshots/; done

install:
	PREFIX="$(PREFIX)" DESTDIR="$(DESTDIR)" packaging/install.sh

uninstall:
	PREFIX="$(PREFIX)" DESTDIR="$(DESTDIR)" packaging/install.sh --uninstall

deb:
	packaging/build-deb.sh

icons:
	$(PYTHON) packaging/make-logo.py
	$(PYTHON) packaging/render-icons.py

clean:
	rm -rf build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
