# Release instructions for Sub Manager

## Perform pre-release tasks

1. Ensure ``MANIFEST.in``, ``setup.cfg`` and README/docs are up to date and commit any changes
2. Test the development version: ``python -b -X dev -m submanager validate-config`` and ``submanager --config-path path/to/test_config.toml start``
3. Close Github milestone (if open)
4. Check ``git status`` then ensure repo is up to date: ``hub sync`` (``git fetch upstream && git pull upstream master && git push origin master``)
5. Update version in ``submanager/__init__.py`` to release version and add ``CHANGELOG.md`` entry


## Build and test

1. Activate the appropriate virtual environment: e.g. ``source env/bin/activate``
2. Install/update packaging packages: e.g. pip install --upgrade pip`` then ``pip install --upgrade setuptools wheel packaging build pep517``
3. Build source and wheel distributions: ``python -b -X dev -m build``
4. In a clean env, install the build: ``pip install dist/submanager-X.Y.Z.TAG-py3-none-any.whl``
5. Test the installed version: ``submanager monitor`` and ``submanager start``


## Upload to PyPI (production release)

1. Install/update Twine: ``pip install --upgrade twine``
2. Perform basic checks: ``twine check --strict dist/*``
3. Upload to TestPyPI first ``twine upload --repository testpypi dist/*``
4. In your development environment, download/install: ``pip install --index-url https://test.pypi.org/simple/ --no-deps submanager``
5. Test the installed version: ``python -b -X dev -m submanager validate-config`` and ``submanager --config-path path/to/test_config.toml start``
6. Upload to live PyPI: ``twine upload dist/*``


## Finalize release

1. Re-install dev build: ``pip install -e .``
2. Commit release: ``git commit -am "Release Sub Manager version X.Y.Z"``
3. Tag release: ``git tag -a vX.Y.Z -m "Sub Manager version X.Y.Z"``
4. If new major or minor version (X or Y in X.Y.Z), create release branch to maintain deployed version: ``git switch -c X.Y.x && git push -u origin X.Y.x && git push upstream X.Y.z && git switch master``
5. If release from ``master``, increment ``__version__`` in ``__init__.py`` to next expected release and add ``dev0`` (or ``dev<N+1>``, if a pre-release)
6. Commit change back to dev mode on ``master``: ``git commit -am "Begin development of version X.Y.x"``
7. Push changes upstream and to user repo: ``git push upstream master --follow-tags && git push origin master``
