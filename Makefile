test:
ifdef debug
	python setup.py test --debug=$(debug)
else
	python setup.py test
endif

clean:
	rm -rf build dist browsepy.egg-info htmlcov MANIFEST .eggs *.egg
	find browsepy -type f -name "*.py[co]" -delete
	find browsepy -type d -name "__pycache__" -delete
	$(MAKE) -C doc clean

doc: *
	$(MAKE) -C doc html

pep8:
	find browsepy -type f -name "*.py" -exec pep8 --ignore=E123,E126,E121 {} +

coverage:
	coverage run --source=browsepy setup.py test
