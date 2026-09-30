.PHONY: setup train evaluate api web test all bundle

setup:
	python3.11 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt
	cd web && npm ci

train:
	PYTHONPATH=ml/src .venv/bin/python -m cardiolens_ml.train
	PYTHONPATH=ml/src .venv/bin/python -m cardiolens_ml.evaluate

evaluate:
	PYTHONPATH=ml/src .venv/bin/python -m cardiolens_ml.evaluate

api:
	.venv/bin/uvicorn api.app.main:app --host 127.0.0.1 --port 8000

web:
	cd web && npm run dev

test:
	.venv/bin/python -m pytest ml/tests api/tests -q
	cd web && npx vitest run --environment jsdom && npx tsc --noEmit && npm run build

all:
	docker compose up --build

bundle:
	python3 scripts/package_bundle.py
