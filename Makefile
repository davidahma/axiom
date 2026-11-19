PYTHON ?= python3

.PHONY: demo test bundle check

demo:
	$(PYTHON) -m axiom_demo demo --output artifacts/demo-report.json

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
	$(PYTHON) -m unittest discover -s trials/opendesk -p 'test_*.py' -v

bundle:
	$(PYTHON) scripts/build_zipapp.py --output artifacts/axiom.pyz

check: test demo bundle
	$(PYTHON) -m axiom_demo validate artifacts/demo-report.json
