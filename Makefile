install:
	uv sync

playground:
	agents-cli playground --port 8080

lint:
	agents-cli lint

generate-traces:
	python tests/eval/generate_traces.py

grade:
	agents-cli eval grade
