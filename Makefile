all::
penv:
	python3 -m venv .venv
	@echo "source .venv/bin/activate"
inst:
	pip3 install $$(sed -n -e 's/dependencies//p' pyproject.toml|tr -d "'[]=,")
bumpver:
	bumpver update --patch
release:
	gh release create
build: clean
	python3 -m pip install --upgrade build
	python3 -m build .
publish: build
	pip install twine
	twine check dist/*
	twine upload --non-interactive dist/*
install: clean build
	python3 -m pip install -e .
#pip install --force-reinstall dist/toutsurmoneau-0.0.1-py3-none-any.whl
fulltest: install test
testlegacy:
	set -ex;\
	. private/env.sh;\
	for test_id in attributes check_credentials;do \
		echo "== $${test_id} (--legacy) =========================================================";\
		$$toutsurmoneau --legacy -e $$test_id $$compat;\
	done
testasync:
	set -ex;\
	. private/env.sh;\
	for test_id in meter_id contracts latest_meter_reading monthly_recent daily_for_month check_credentials;do \
		echo "== $${test_id} =========================================================";\
		$$toutsurmoneau -e $$test_id $$compat;\
	done;\
	. private/env.sh && \
	two_month_earlier=$$(date -v1d -v-65d +%Y%m) && \
	$$toutsurmoneau -e daily_for_month -d $${two_month_earlier}
test: testlegacy testasync
	python3 --version
	. private/env.sh && $$toutsurmoneau -h
clean:
	rm -fr dist
	find . -name '*.egg-info' -print0|xargs -0 rm -fr
	find . -name __pycache__ -print0|xargs -0 rm -fr
changes:
	@latest_tag=$$(git describe --tags --abbrev=0);\
	echo "Changes since [$$latest_tag]";\
	git log $$latest_tag..HEAD --oneline
changesv:
	@v1=0.0.$$(($(V) - 1));\
	v2=0.0.$(V);\
	echo "Changes between $$v1..$$v2";\
	git show $$v1..$$v2 --oneline
