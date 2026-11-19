PYTHON ?= python3

.PHONY: demo test bundle receipt-example check

demo:
	$(PYTHON) -m axiom_demo demo --output artifacts/demo-report.json

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
	$(PYTHON) -m unittest discover -s trials/opendesk -p 'test_*.py' -v

bundle:
	$(PYTHON) scripts/build_zipapp.py --output artifacts/axiom.pyz

receipt-example: bundle
	$(PYTHON) scripts/receipt_example.py

check: test demo receipt-example
	$(PYTHON) -m axiom_demo validate artifacts/demo-report.json
