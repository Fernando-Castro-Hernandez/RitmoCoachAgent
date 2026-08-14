# Reenvía a poethepoet, que funciona igual en Windows, macOS y Linux.
# En Windows sin `make`, usa directamente:  uv run poe <tarea>
# Lista de tareas:                          uv run poe --help

.PHONY: dev down test test-dom evals lint fmt purity check deploy setup

setup:   ; uv sync --all-groups
dev:     ; uv run poe dev
down:    ; uv run poe down
test:    ; uv run poe test
test-dom:; uv run poe test-dom
evals:   ; uv run poe evals
lint:    ; uv run poe lint
fmt:     ; uv run poe fmt
purity:  ; uv run poe purity
check:   ; uv run poe check
deploy:  ; uv run poe deploy
