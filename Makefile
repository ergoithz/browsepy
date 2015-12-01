test:
	python setup.py test

coverage:
	coverage run --source=browsepy setup.py test
