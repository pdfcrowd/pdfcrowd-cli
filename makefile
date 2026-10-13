PYTHON ?= python3
TWINE ?= twine

.PHONY: build dist clean check publish publish-to-testpypi

build:
	@$(MAKE) clean
	@$(PYTHON) -m build

dist: build
	$(PYTHON) package_download.py

check: build
	@$(TWINE) check --strict dist/*

publish: check
	@$(TWINE) upload --skip-existing --verbose dist/*

publish-to-testpypi: check
	@$(TWINE) upload --repository testpypi --skip-existing --verbose dist/*

clean:
	rm -rf build dist *.egg-info src/*.egg-info
