test:
	python -m unittest browsepy.tests

coverage:
	coverage run --source=browsepy setup.py test
