all::
build:
	python3 -m pip install --upgrade build
	python3 -m build
	twine check dist/*
publish: build
	twine upload dist/*
install: clean build
	python3 -m pip install -e .
#pip install --force-reinstall dist/toutsurmoneau-0.0.1-py3-none-any.whl
fulltest: install test
test:
	. private/env.sh && toutsurmoneau -u $$U -p $$P
	. private/env.sh && toutsurmoneau -u $$U -p $$P -e attributes
	. private/env.sh && toutsurmoneau -u $$U -p $$P -e contracts
	. private/env.sh && toutsurmoneau -u $$U -p $$P -e total_volume
	. private/env.sh && toutsurmoneau -u $$U -p $$P -e monthly_recent
	. private/env.sh && toutsurmoneau -u $$U -p $$P -e daily_for_month
clean:
	rm -fr dist
	find . -name '*.egg-info' -print0|xargs -0 rm -fr
# bumpver update --patch --allow-dirty
