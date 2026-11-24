# Convenience wrapper; everything also works without make:
#   PYTHONPATH=src python3 -m proccoli
#   python3 -m unittest discover -s tests

PYTHON ?= python3
PREFIX ?= /usr/local
DESTDIR ?=

.PHONY: all run demo test ui-test install uninstall deb icons clean

all:
	@true

run:
	PYTHONPATH=src $(PYTHON) -m proccoli

demo:
	PYTHONPATH=src $(PYTHON) -m proccoli --demo

test:
	$(PYTHON) -m unittest discover -s tests -v

# All tests, including the widget and window tests, on a private headless
# display; then screenshots of the main layouts into tests/ui/out/.
ui-test:
	tests/run-headless.sh $(PYTHON) -m unittest discover -s tests -v
	tests/run-headless.sh $(PYTHON) tests/ui/shoot.py tests/ui/out

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
