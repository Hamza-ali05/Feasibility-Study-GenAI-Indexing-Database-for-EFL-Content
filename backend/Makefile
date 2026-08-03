ROOT := $(abspath ..)
export PYTHONPATH := $(ROOT)
PYTHON ?= python
PYTEST ?= pytest
PIP ?= pip
UVICORN ?= uvicorn

.PHONY: install discover load integrate eda clean split preprocess balance \
	train evaluate explain-global explain-local explain-quality predict \
	pipeline-all api test hash-password

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

pipeline-all: discover load integrate eda clean split preprocess balance \
	train evaluate explain-global explain-local explain-quality predict

api:
	cd $(ROOT) && $(UVICORN) backend.api.main:app --reload --port 8000

test:
	cd $(ROOT) && $(PYTEST) tests/ -v

# Usage: make hash-password PW='your-chosen-password'
hash-password:
	cd $(ROOT) && $(PYTHON) -m backend.auth.generate_password_hash "$(PW)"
