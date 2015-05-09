test:
	python -m browsepy.tests

coverage:
	@(nosetests $(TEST_OPTIONS) --with-coverage --cover-package=browsepy --cover-html --cover-html-dir=coverage_out $(TESTS))
