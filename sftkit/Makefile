.PHONY: test
test:
	pdm run -p .. pytest . --doctest-modules

.PHONY: format
format:
	pdm run -p .. ruff format

.PHONY: lint
lint: ruff mypy check-format

.PHONY: ruff
ruff:
	pdm run -p .. ruff check .

.PHONY: ruff-fix
ruff-fix:
	pdm run -p .. ruff check . --fix

.PHONY: mypy
mypy:
	pdm run -p .. mypy .

.PHONY: check-format
check-format:
	pdm run -p .. ruff format --check

.PHONY: build
package:
	pdm build