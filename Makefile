all::
build: clean
	python3 -m pip install --upgrade build
	python3 -m build
	twine check dist/*
publish: build
	twine upload --non-interactive dist/*
install: clean build
	python3 -m pip install -e .
#pip install --force-reinstall dist/toutsurmoneau-0.0.1-py3-none-any.whl
fulltest: install test
test:
	. private/env.sh && $$toutsurmoneau -h
	for compat in --no-compat --compat;do \
		for test_id in attributes meter_id contracts latest_meter_reading monthly_recent daily_for_month check_credentials;do \
		    echo "== $${test_id} ($${compat}) =========================================================";\
		    . private/env.sh && $$toutsurmoneau -u $$U -p $$P -e $$test_id $$compat;\
		done;\
	done
clean:
	rm -fr dist
	find . -name '*.egg-info' -o -name __pycache__ -print0|xargs -0 rm -fr
bumpver:
	bumpver update --patch
