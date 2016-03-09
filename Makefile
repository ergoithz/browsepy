test:
	python setup.py test
	
clean:
	rm -rf build
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

coverage:
	coverage run --source=browsepy setup.py test
