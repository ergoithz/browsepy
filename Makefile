test:
ifdef debug
	python setup.py test --debug=$(debug)
else
	python setup.py test
endif

clean:
	rm -rf build dist browsepy.egg-info htmlcov MANIFEST .eggs
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

coverage:
	coverage run --source=browsepy setup.py test --omit=browsepy/tests/runner.py
