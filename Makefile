.PHONY: dist

dist:
	rm -rf ./dist/*
	python setup.py sdist bdist_wheel

release-test: dist
	twine upload --repository testpypi dist/*

