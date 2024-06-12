.PHONY: test
test:
	pytest . --doctest-modules

.PHONY: check-format
check-format:
	ruff format --check

.PHONY: format
format:
	ruff format

.PHONY: lint
lint: ruff mypy

.PHONY: ruff
ruff:
	ruff check .

.PHONY: ruff-fix
ruff-fix:
	ruff check . --fix

.PHONY: mypy
mypy:
	mypy .

.PHONY: package
package:
	python3 -m build