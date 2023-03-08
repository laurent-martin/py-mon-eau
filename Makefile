all::
build: clean
	python3 -m pip install --upgrade build
	python3 -m build src
	pip install twine
	twine check dist/*
publish: build
	twine upload --non-interactive dist/*
install: clean build
	python3 -m pip install -e .
#pip install --force-reinstall dist/toutsurmoneau-0.0.1-py3-none-any.whl
fulltest: install test
testlegacy:
	set -e;. private/env.sh;\
	for test_id in attributes check_credentials;do \
		echo "== $${test_id} (--legacy) =========================================================";\
		$$toutsurmoneau --legacy -u $$U -p $$P -e $$test_id $$compat;\
	done
testasync:
	set -e;. private/env.sh;\
	for test_id in meter_id contracts latest_meter_reading monthly_recent daily_for_month check_credentials;do \
		echo "== $${test_id} =========================================================";\
		$$toutsurmoneau -u $$U -p $$P -e $$test_id $$compat;\
	done;\
	. private/env.sh && \
	two_month_earlier=$$(date -v1d -v-65d +%Y%m) && \
	$$toutsurmoneau -u $$U -p $$P -e daily_for_month -d $${two_month_earlier}
test: testlegacy testasync
	python3 --version
	. private/env.sh && $$toutsurmoneau -h
clean:
	rm -fr dist
	find . -name '*.egg-info' -print0|xargs -0 rm -fr
	find . -name __pycache__ -print0|xargs -0 rm -fr
bumpver:
	bumpver update --patch
