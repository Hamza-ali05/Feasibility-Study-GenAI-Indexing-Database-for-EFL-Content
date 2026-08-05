ROOT := $(abspath ..)
# Repo root for backend.*; backend/ for api.* (matches start.bat / run_backend.bat)
export PYTHONPATH := $(ROOT)$(if $(filter $(OS),Windows_NT),;,:)$(ROOT)/backend
PYTHON ?= python
PYTEST ?= pytest
PIP ?= pip
UVICORN ?= uvicorn

.PHONY: install discover load integrate eda clean split preprocess balance \
	train evaluate explain-global explain-local explain-quality predict \
	pipeline-all pipeline-repro-note api test hash-password

install:
	$(PIP) install -r requirements.txt

discover:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_01_discover

load:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_02_load

integrate:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_03_integrate

eda:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_04_eda

clean:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_05_clean

split:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_06_split

preprocess:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_07_preprocess

balance:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_08_balance

train:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_09_train

evaluate:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_10_evaluate

explain-global:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_11_explain_global

explain-local:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_12_explain_local

explain-quality:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_13_explain_quality

predict:
	cd $(ROOT) && $(PYTHON) -m backend.pipeline.stage_14_predict

pipeline-repro-note:
	@echo ============================================================
	@echo   A reproducibility snapshot will be captured automatically
	@echo   at the start of Discover (seed, packages, dataset hash).
	@echo ============================================================

pipeline-all: pipeline-repro-note discover load integrate eda clean split preprocess balance \
	train evaluate explain-global explain-local explain-quality predict

api:
	cd $(ROOT) && $(UVICORN) backend.api.main:app --reload --host 127.0.0.1 --port 8000 --reload-dir $(ROOT)/backend --reload-dir $(ROOT)/research

test:
	cd $(ROOT) && $(PYTEST) tests/ -v

# Usage: make hash-password PW='your-chosen-password'
hash-password:
	cd $(ROOT) && $(PYTHON) -m backend.auth.generate_password_hash "$(PW)"
