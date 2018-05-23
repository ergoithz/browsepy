.PHONY: test clean upload doc showdoc eslint pep8 pycodestyle flake8 coverage showcoverage

test: flake8 eslint
	python -c 'import yaml, glob;[yaml.load(open(p)) for p in glob.glob(".*.yml")]'
ifdef debug
	python setup.py test --debug=$(debug)
else
	python setup.py test
endif

clean:
	rm -rf \
		build \
		dist \
		browsepy.egg-info
	find browsepy -type f -name "*.py[co]" -delete
	find browsepy -type d -name "__pycache__" -delete
	$(MAKE) -C doc clean

build/env:
	mkdir -p build
	python3 -m venv build/env
	build/env/bin/pip install pip --upgrade
	build/env/bin/pip install wheel

build: clean build/env
	build/env/bin/python setup.py bdist_wheel
	build/env/bin/python setup.py sdist

upload: clean build/env
	build/env/bin/python setup.py bdist_wheel upload
	build/env/bin/python setup.py sdist upload

doc:
	$(MAKE) -C doc html 2>&1 | grep -v \
		'WARNING: more than one target found for cross-reference'

showdoc: doc
	xdg-open file://${CURDIR}/doc/.build/html/index.html >> /dev/null

eslint:
	eslint ${CURDIR}/browsepy

pycodestyle:
	pycodestyle --show-source browsepy
	pycodestyle --show-source setup.py

pep8: pycodestyle

flake8:
	flake8 --show-source browsepy
	flake8 --show-source setup.py

coverage:
	coverage run --source=browsepy setup.py test

showcoverage: coverage
	coverage html
	xdg-open file://${CURDIR}/htmlcov/index.html >> /dev/null

