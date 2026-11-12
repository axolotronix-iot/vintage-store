.PHONY: help back front migrate test lint fmt check build

help:
	@echo "make back     - Django en :8000"
	@echo "make front    - Vite en :5173"
	@echo "make migrate  - aplica migraciones"
	@echo "make test     - pytest"
	@echo "make lint     - ruff (sin modificar archivos)"
	@echo "make fmt      - ruff formatea y corrige"
	@echo "make build    - compila el frontend"
	@echo "make check    - lo que debe pasar antes de cada commit"

back:
	cd backend && python manage.py runserver 0.0.0.0:8000

front:
	cd frontend && npm run dev

migrate:
	cd backend && python manage.py migrate

test:
	cd backend && pytest

lint:
	cd backend && ruff check . && ruff format --check .

fmt:
	cd backend && ruff check --fix . && ruff format .

build:
	cd frontend && npm run build

check: lint
	cd backend && python manage.py check && python manage.py makemigrations --check --dry-run
	$(MAKE) test
	$(MAKE) build
