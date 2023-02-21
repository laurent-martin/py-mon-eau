all::
build:
	python3 -m pip install --upgrade build
	python3 -m build
	twine check dist/*
publish:
	twine upload -r testpypi dist/*
install: build
	python3 -m pip install -e .
#pip install --force-reinstall dist/toutsurmoneau-0.0.1-py3-none-any.whl
test: install
	. private/env.sh && toutsurmoneau -u $$U -p $$P
clean:
	rm -fr dist
	find . -name '*.egg-info' -print0|xargs -0 rm -fr
