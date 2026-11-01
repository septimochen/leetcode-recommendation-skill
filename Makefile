SKILLS_DIR ?= $(HOME)/.agents/skills
SKILL_DIR := $(SKILLS_DIR)/leetcode-recommendation

.PHONY: check format test lint install

install:
	mkdir -p "$(SKILL_DIR)"
	cp -R leetcode-recommendation/. "$(SKILL_DIR)/"

check: lint test
	uv run ty check leetcode-recommendation/scripts

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .

test:
	uv run pytest
