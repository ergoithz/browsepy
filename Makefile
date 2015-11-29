test:
	python -m unittest discover

coverage:
	coverage run --source=browsepy setup.py test
