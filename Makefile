RED=\033[0;31m
YELLOW=\033[0;33m
GREEN=\033[0;32m
CYAN=\033[0;36m
NC=\033[0m # No Color

TMP_DIR=$(CURDIR)/tmp

OPENCV_SRC=${TMP_DIR}/opencv
OPENCV_BUILD=${OPENCV_SRC}/build

VENV_DIR=$(CURDIR)/env3
ENV_BIN_PATH=${VENV_DIR}/bin
ENV_LIB_PATH=${VENV_DIR}/lib

.PHONY: doc clean pep8 coverage travis

test: pep8 flake8 eslint
	python -c 'import yaml;yaml.load(open(".travis.yml").read())'
ifdef debug
	python setup.py test --debug=$(debug)
else
	python setup.py test
endif

clean:
	rm -rf build dist browsepy.egg-info htmlcov MANIFEST \
	       .eggs *.egg .coverage ${VENV_DIR} ${TMP_DIR}
	find browsepy -type f -name "*.py[co]" -delete
	find browsepy -type d -name "__pycache__" -delete
	$(MAKE) -C doc clean

local-dev:
	-python3 -m venv ${VENV_DIR}
	${ENV_BIN_PATH}/pip install pip --upgrade
	${ENV_BIN_PATH}/pip install --upgrade setuptools #https://github.com/pallets/itsdangerous/issues/90
	${ENV_BIN_PATH}/pip install -r requirements.txt
	${ENV_BIN_PATH}/pip install numpy

opencv-fedora-deps:
	sudo dnf install -y cmake python-devel numpy gcc gcc-c++ gtk2-devel libdc1394-devel libv4l-devel ffmpeg-devel gstreamer-plugins-base-devel libpng-devel libjpeg-turbo-devel jasper-devel openexr-devel libtiff-devel libwebp-devel tbb-devel eigen3-devel python-sphinx texlive

build-env:
	mkdir -p build
	python3 -m venv build/env3
	build/env3/bin/pip install pip --upgrade
	build/env3/bin/pip install wheel

build: clean build-env
	build/env3/bin/python setup.py bdist_wheel
	build/env3/bin/python setup.py sdist

upload: clean build-env
	build/env3/bin/python setup.py bdist_wheel upload
	build/env3/bin/python setup.py sdist upload

doc:
	$(MAKE) -C doc html 2>&1 | grep -v \
		'WARNING: more than one target found for cross-reference'

showdoc: doc
	xdg-open file://${CURDIR}/doc/.build/html/index.html >> /dev/null

pep8:
	find browsepy -type f -name "*.py" -exec pep8 --ignore=E123,E126,E121 {} +

eslint:
	eslint \
		--ignore-path .gitignore \
		--ignore-pattern *.min.js \
		${CURDIR}/browsepy

flake8:
	flake8 browsepy/

coverage:
	coverage run --source=browsepy setup.py test

showcoverage: coverage
	coverage html
	xdg-open file://${CURDIR}/htmlcov/index.html >> /dev/null

travis-script: pep8 flake8 coverage

travis-script-sphinx:
	travis-sphinx --nowarn --source=doc build

travis-success:
	coveralls

travis-success-sphinx:
	travis-sphinx deploy

build-opencv: local-dev
	@printf "${YELLOW}If this fails, please make sure the deps defined in '${GREEN}make opencv-fedora-deps' ${YELLOW}are installed...\n${NC}"
	@printf "${YELLOW}\tMore info: \n\t\t${CYAN}https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_setup/py_setup_in_fedora/py_setup_in_fedora.html#install-opencv-python-in-fedora\n\t\thttp://docs.opencv.org/3.1.0/d7/d9f/tutorial_linux_install.html\n\n${NC}"
	mkdir -p ${TMP_DIR}
	-git clone https://github.com/opencv/opencv.git ${OPENCV_SRC}
	cd ${OPENCV_SRC} && git pull
	mkdir -p ${OPENCV_BUILD}
	cd ${OPENCV_BUILD} && \
	cmake \
		-D WITH_TBB=ON \
		-D WITH_EIGEN=ON \
		-D BUILD_DOCS=OFF \
		-D BUILD_TESTS=OFF \
		-D BUILD_PERF_TESTS=OFF \
		-D BUILD_EXAMPLES=OFF \
		-D CMAKE_BUILD_TYPE=RELEASE \
		-D CMAKE_INSTALL_PREFIX=${VENV_DIR} \
		-D PYTHON_DEFAULT_EXECUTABLE=${ENV_BIN_PATH}/python3 \
		-D PYTHON_INCLUDE_DIRS=/usr/include/python3* \
		-D PYTHON_EXECUTABLE=${ENV_BIN_PATH}/python3 \
		-D PYTHON_LIBRARY=/usr/lib64/libpython3.*.so \
		-D PYTHON3_NUMPY_INCLUDE_DIRS=${ENV_LIB_PATH}/python3.6/site-packages/numpy/core/include \
		${OPENCV_SRC} && \
	make -j20 && \
	make install
