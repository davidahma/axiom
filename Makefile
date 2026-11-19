PYTHON ?= python3

.PHONY: demo test check

demo:
	$(PYTHON) -m axiom_demo demo --output artifacts/demo-report.json

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
	$(PYTHON) -m unittest discover -s trials/opendesk -p 'test_*.py' -v

check: test demo
	$(PYTHON) -m axiom_demo validate artifacts/demo-report.json
