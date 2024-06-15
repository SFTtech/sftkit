.PHONY: test
test:
	pdm run pytest . --doctest-modules

.PHONY: format
format:
	pdm run ruff format

.PHONY: lint
lint: ruff mypy check-format

.PHONY: ruff
ruff:
	pdm run ruff check .

.PHONY: ruff-fix
ruff-fix:
	pdm run ruff check . --fix

.PHONY: mypy
mypy:
	pdm run mypy .

.PHONY: check-format
check-format:
	pdm run ruff format --check

.PHONY: build
package:
	pdm build