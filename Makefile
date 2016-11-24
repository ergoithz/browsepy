.PHONY: doc clean pep8 coverage travis

test: pep8
ifdef debug
	python setup.py test --debug=$(debug)
else
	python setup.py test
endif

clean:
	rm -rf build dist browsepy.egg-info htmlcov MANIFEST \
	       .eggs *.egg .coverage
	find browsepy -type f -name "*.py[co]" -delete
	find browsepy -type d -name "__pycache__" -delete
	$(MAKE) -C doc clean

build: clean
	mkdir -p build
	python3 -m venv build/env3
	build/env3/bin/pip install pip --upgrade
	build/env3/bin/pip install wheel
	env3/bin/python setup.py bdist_wheel --require-scandir
	env3/bin/python setup.py sdist

upload: build
	python setup.py upload

doc:
	$(MAKE) -C doc html

showdoc: doc
	xdg-open file://${CURDIR}/doc/.build/html/index.html >> /dev/null

pep8:
	find browsepy -type f -name "*.py" -exec pep8 --ignore=E123,E126,E121 {} +

coverage:
	coverage run --source=browsepy setup.py test

showcoverage: coverage
	coverage html
	xdg-open file://${CURDIR}/htmlcov/index.html >> /dev/null

travis-script: coverage
	travis-sphinx --nowarn --source=doc build

travis-success:
	coveralls
	travis-sphinx deploy
