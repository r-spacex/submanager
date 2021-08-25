# Release procedure

A step by step checklist for cutting a new release.

**Note:** This guide uses [``hub``](https://hub.github.com/) to sync branches more easily, but it can be substituted with switching to the ``master``/release branch and running ``git pull upstream <BRANCH-NAME>``.


<!-- markdownlint-disable -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Preliminaries](#preliminaries)
- [Update pinned dependencies](#update-pinned-dependencies)
- [Update pre-commit hooks](#update-pre-commit-hooks)
- [Build and test on RPi/production machine](#build-and-test-on-rpiproduction-machine)
- [Transition new version to production on RPi](#transition-new-version-to-production-on-rpi)
- [Update documentation and finish release PR](#update-documentation-and-finish-release-pr)
- [Rebuild and upload to PyPI on RPi/production machine](#rebuild-and-upload-to-pypi-on-rpiproduction-machine)
- [Re-install production release on Pi](#re-install-production-release-on-pi)
- [Finalize release](#finalize-release)
- [Cleanup on the RPi/production machine](#cleanup-on-the-rpiproduction-machine)
- [Cleanup locally](#cleanup-locally)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- markdownlint-restore -->


## Preliminaries

0. Check that no release steps need updating
1. Ensure all issues/PRs linked to Github milestone are closed or moved to next release
2. Check ``git status`` and ``git diff`` for any untracked local changes and handle as needed
3. Sync from ``upstream`` repo, push to ``origin`` and clean up old branches: ``git fetch --all``, then ``hub sync``/``git pull upstream``, then ``git push origin``, and finally ``git branch -d <BRANCH>`` and ``git push -d <REMOTE> <BRANCH>`` for any branches
4. Create a new branch ``prepare-release-XYZ`` and push to ``upstream``: ``git switch -c prepare-release-XYZ`` then ``git push -u upstream prepare-release-XYZ``



## Update pinned dependencies

0. Check ``MANIFEST.in`` and ``setup.cfg`` to ensure they are up to date and all data files are included
1. Check each dependency for new upper bound version and examine changelogs for breaking changes
2. Commit and push if changes made to run regen deps on Linux machine (RPi), and open PR against base branch
3. On RPi, activate env and run ``python -X dev tools/generate_requirements_files.py build`` to update build deps
4. Run ``python -m pip install --upgrade -r requirements-build.txt`` to install updated build deps
5. Run ``python -X dev tools/generate_requirements_files.py`` to update all reqs files
6. Run ``pip install --upgrade -r requirements-dev.txt`` install updated dev deps
7. Run ``pip install -e .`` to ensure package install is up to date
8. Run ``pip check`` to verify environment integrity
9. Run ``python -bb -X dev -W error -m pytest --run-online`` and fix any issues
10. Run ``pre-commit run --all-files`` and fix any issues
11. Sync back changes to dev machine and fixup prior commit
12. Push and test on PR and ``git reset --hard`` on Pi



## Update pre-commit hooks

0. Address any outstanding trivial tweaks with hooks
1. Run ``pre-commit autoupdate`` to update hooks
2. Manually check ``additional_dependencies`` for updates and update as needed
3. Check hook/dep changelogs and add/update any new settings
4. Run ``pre-commit run --all-files`` and fix any issues
5. Run ``python -bb -X dev -W error -m pytest --run-online`` and fix any issues
6. Commit changes, push & test on PR



## Build and test on RPi/production machine

0. Pull latest changes from release branch down to RPi
1. Activate the existing dev virtual environment: e.g. ``source env/bin/activate``
2. Delete existing ``dist/`` if present: ``rm -rfd dist``
3. Build source and wheel distributions: ``python -bb -X dev -W error -m build``
4. Check with twine: ``twine check --strict dist/*``
5. Create a fresh, clean virtual environment, e.g. ``deactivate`` then ``python3 -m venv clean-env``
6. Activate the new environment, e.g. ``source clean-env/bin/activate``
7. Install/upgrade core install deps in new environment: ``python -m pip install --upgrade pip setuptools wheel``
8. Install the build in the new environment: ``pip install dist/submanager-X.Y.Z.dev0-py3-none-any.whl[test]``
9. Check the env with pip: ``pip check``
10. Test the installed version: ``python -bb -X dev -W error -m pytest --run-online``
11. Fix any bugs, commit, push and retest



## Transition new version to production on RPi

0. Disable and stop production service: ``systemctl --user disable submanager`` then ``systemctl --user stop submanager``
1. Activate production venv (e.g. ``source env/bin/activate``)
2. Upgrade core install deps ``python -m pip install --upgrade pip setuptools wheel``
3. Install/upgrade pinned deps from requirements file: ``pip install --upgrade -r requirements.txt``
4. Install package from built wheel: ``pip install dist/submanager-X.Y.Z.dev0-py3-none-any.whl``
5. Ensure config/state dir names, locations and structure is up to date
6. Sync static config and praw.ini from dev machine
7. Update local dynamic config as needed
8. Validate config with ``python -b -X dev -m submanager validate-config``
9. Start running and verify nominal performance: ``python -b -X dev -m submanager start``
10. Install service with ``python -bb -X dev -W error -m submanager install-service``
11. Enable and start service, wait 30 seconds and verify ``status``, ``journalctl`` log output and on sub



## Update documentation and finish release PR

0. Skim ``README.md``, ``CONTRIBUTING.md`` and ``RELEASE.md`` to ensure they are up to date and render correctly on Github, and commit any changes
1. Update ``ROADMAP.md`` to remove current release and add plans for next release(s), commit and verify rendering
2. Add ``CHANGELOG.md`` entries for current version, commit and verify rendering
3. Update version in ``submanager/__init__.py`` and SECURITY.md to release version and commit as "Release Sub Manager version X.Y.Z"
4. Check ``hub sync`` and ``git status`` one more time, and then push to the PR and wait for checks to pass



## Rebuild and upload to PyPI on RPi/production machine

0. Repeat steps 0 through 4 (inclusive) in "Build and test on RPi" section to rebuild release version
1. Install built wheel in dev environment: ``pip install dist/submanager-X.Y.Z.dev0-py3-none-any.whl[lint,test]``
2. Verify version is correct: ``submanager --version``
3. Run basic tests one last time: ``python -bb -X dev -W error -m pytest``
4. Merge PR and wait for checks to pass
5. Upload to live PyPI: ``twine upload dist/*``



## Re-install production release on Pi

0. Check for any errors in service, and then disable and stop
1. Activate production environment, e.g. ``source env/bin/activate``
2. Install release version from PyPI: ``pip install --upgrade submanager``
3. Verify version is correct: ``submanager --version``
4. Enable and restart service, wait 30 seconds and verify no errors occur with ``status`` and ``journalctl``



## Finalize release

0. Close Github milestone
1. Switch to master/release branch and sync: ``git switch master``/``git switch X.Y.Z`` then ``hub sync``
2. Tag release: ``git tag -a vX.Y.Z -m "Sub Manager version X.Y.Z"``
3. Push tags: ``git push upstream --tags``
4. Create a Github release from the tag and with the version's changelog, plus any important notices up top
5. Increment ``__init__.__version__`` to next release and re-add ``dev0`` (or ``dev<N+1>``, if a pre-release)
6. If a release from ``master``, i.e. new major or minor version, create release branch to maintain it:

   ```bash
   git switch -c X.Y.x
   git push -u origin X.Y.x
   git push upstream X.Y.z
   git switch master
   ```

7. Commit change to ``master`` / release branch with message: "Begin development of version X.Y.x"
8. If from ``master``, push ``master`` & ``staging``: ``git push upstream master`` ``git push upstream staging``
   If from a release branch: ``git push upstream X.Y.x`` ``git push upstream staging-release``
9. Update your fork's master branch: ``git push origin master``
10. Open a Github milestone as needed for the next release



## Cleanup on the RPi/production machine

0. Switch and re-pull ``master`` in the dev env: ``git switch master`` then ``git pull upstream master``
1. Re-install dev build; with the dev env activated, run: ``pip install -e .[lint,test]``
2. Verify version with ``submanager --version``
3. Remove clean test environment (``test-env``) and ``dist/`` on RPi
4. Delete any other old services, config files, dirs and environments on RPi



## Cleanup locally

0. Ensure everything is synced: ``hub sync``
1. Re-install dev build locally: ``pip install -e .[lint,test]``
2. Verify version with ``submanager --version``
3. Delete the prepare release branch locally: ``git branch -d prepare-release-XYZ``
4. Delete the branch on the remote: ``git branch -d upstream prepare-release-XYZ``
