# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).



<!-- markdownlint-disable -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [[0.6.0] - 2021-08-24](#060---2021-08-24)
  - [Added](#added)
  - [Changed](#changed)
  - [Fixed](#fixed)
  - [Removed](#removed)
- [[0.5.1] - 2021-06-15](#051---2021-06-15)
  - [Fixed](#fixed-1)
- [[0.5.0] - 2021-05-18](#050---2021-05-18)
  - [Added](#added-1)
  - [Changed](#changed-1)
- [[0.4.0] - 2021-03-24](#040---2021-03-24)
  - [Added](#added-2)
  - [Changed](#changed-2)
- [[0.3.1] - 2021-03-01](#031---2021-03-01)
  - [Changed](#changed-3)
  - [Fixed](#fixed-2)
- [[0.3.0] - 2021-02-08](#030---2021-02-08)
  - [Added](#added-3)
  - [Changed](#changed-4)
- [[0.2.2] - 2021-02-01](#022---2021-02-01)
  - [Added](#added-4)
  - [Fixed](#fixed-3)
- [[0.2.1] - 2021-01-22](#021---2021-01-22)
  - [Added](#added-5)
  - [Fixed](#fixed-4)
- [0.2.0 - 2021-01-21](#020---2021-01-21)
  - [Added](#added-6)
  - [Changed](#changed-5)
  - [Fixed](#fixed-5)
- [[0.1.2] - 2021-01-20](#012---2021-01-20)
  - [Changed](#changed-6)
- [[0.1.1] - 2021-01-20](#011---2021-01-20)
  - [Added](#added-7)
  - [Changed](#changed-7)
  - [Fixed](#fixed-6)
- [[0.1.0] - 2021-01-01](#010---2021-01-01)
  - [Added](#added-8)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- markdownlint-restore -->



## [0.6.0] - 2021-08-24

### Added

* Full command-based CLI with many more options, including separate ``start`` and ``run`` commands
* Command ``get-config-info`` to print information about the config and list endpoints
* Command ``install-service`` to automatically install a systemd service to run the bot
* Command ``generate-config`` to generate a user config file with example defaults
* Command ``validate-config`` to validate the current config file, offline or online
* Command ``cycle-threads`` to post new versions of the indicated threads
* ``--debug`` flag, to control whether user-friendly error messages or full tracebacks are printed
* Config option ``approve_new`` to control if new posted threads are automatically approved (default)
* ``"auto"`` option for ``pin_mode`` (default) will unpin the old thread and pin the new if currently pinned
* ``truncate_lines`` option for source and target endpoints, to truncate to a specified number of lines
* More fillable/replaceable variables in thread titles
* Comprehensive offline and online functional tests exercising the options of every supported command
* Exhaustive suite of pre-commit checks to validate correctness, best-practices, conventions and style
* Tests, linting and analysis all run across a matrix of platforms/versions in CIs via Github Actions


### Changed

* Reorganize much of user and dynamic config for consistency and future extensibility
* Use Platformdirs to install config and state files into platform-appropriate locations
* Validate config and resync all sources for the first run, to handle any config changes
* Use Pydantic for config, allowing robust access and user-friendly validation
* Vastly improved error handing of almost all areas, with much more helpful, user friendly messages
* Safety run multiple instances via locking, to enable new commands and avoid strange bugs
* Enable thread redirect in OP and sticky by default (configurable)
* Inject start and end comments into thread targets, to allow easily adding extra content
* Formally rename everything to Sub Manager, with consistent naming everywhere
* Refactor from a monolithic script into a modular package, greatly improving organization
* Make a Python package for installing from Github or from PyPI and add lint and test extras
* Package is now fully statically typed, improving correctness, robustness and documentation
* Add/greatly improve docs including Readme, Contributing Guide, security policy and more
* Auto-generate pinned requirements files for reproducible dev and production installation


### Fixed

* Issues with hierarchical config defaults not getting inherited correctly
* Not syncing new targets until a change is made in the source
* Not injecting appropriate line breaks in targets for some sources, causing formatting issues
* Many other edge-case bugs and issues


### Removed

* Config file no longer generated automatically if its not present, use ``generate-config`` instead
* Drop previous support for token managers, in line with Reddit and PRAW changes



## [0.5.1] - 2021-06-15

### Fixed

* Fix a bug with disabling top-level sync pair items
* Fix docstrings and add to more functions



## [0.5.0] - 2021-05-18

### Added

* Multi-account support, per-source, target and sync/thread
* Multi-subreddit support with similar granularity, to allow sync between subs
* Ability to leave a customizable OP message and/or sticky when replacing a thread
* Flexible config inheritance (source/target <- task <- module <- global)
* Full refresh token handling to support new Reddit OAUTH changes


### Changed

* Fully reorganize config to be much cleaner and more flexible
* Majorly refactor code for much greater extendability going forward
* Further update README, ROADMAP, documentation and metafiles



## [0.4.0] - 2021-03-24

### Added

* Fixed and floating time intervals for posting megathreads
* Arbitrary integer periods for floating post intervals
* Support for N weekly posting frequency


### Changed

* Refactor and implement much more sophisticated post interval parsing
* Update documentation to describe configuration and post intervals in more detail
* Update roadmap to reflect re-prioritization



## [0.3.1] - 2021-03-01

### Changed

* Replace ``tomlkit`` with ``toml`` to fix strange bugs with PRAW


### Fixed

* Fix bug with unsticky of old megathread not having mod permissions
* Fix bug with not updating megathread URLs correctly
* Optimize link update to use generator
* Fix formatting bug in README



## [0.3.0] - 2021-02-08

### Added

* Sync to/from New Reddit sidebar widgets
* Sync to/from thread OPs
* Sync to new Reddit menus
* Support for managing multiple independent megathreads
* Full sync endpoint features for megathreads
* Broader and more granular enable/disable options
* CHANGELOG tracking releases


### Changed

* Use sync module as backend for megathread update
* Split static and dynamic config files and objects
* Make static config human-editable TOML
* Reorganize and streamline config schema
* Hugely refactor code



## [0.2.2] - 2021-02-01

### Added

* Support for updating megathread links in wiki, sidebar/menu and removal messages
* Basic error handling (restart, etc) to systemd service unit (to recover from random Reddit errors)


### Fixed

* Set unbuffered output so the systemd journal/syslog output is updated in real time
* Fix reliability issues with unstickying and stickying the correct sticky



## [0.2.1] - 2021-01-22

### Added

* Option to enable/disable megathread manager module
* Requirements.txt for dependencies
* Systemd service unit
* README with documentation
* ROADMAP with project roadmap
* LICENSE with MIT License
* Git metafiles


### Fixed

* Recheck date more reliably every run


## 0.2.0 - 2021-01-21

### Added

* New Sync Manager module
* Sync arbitrary source wiki pages to target wiki pages
* Sync full pages or subsections designated by special marker comments
* Support multiple targets per source page with custom settings
* Customizable pattern replacements (i.e. for reformatting, etc) between them
* Accompanying config for sync manager


### Changed

* Major code refactoring to support current and future changes


### Fixed

* Fix various minor bugs



## [0.1.2] - 2021-01-20

### Changed

* Automatically update config with newly added options
* Cache current thread for better performance
* Further refactor session objects



## [0.1.1] - 2021-01-20

### Added

* Ability to run in a loop at a set interval


### Changed

* Refactor config/variable names to make more sense


### Fixed

* Fix various minor bugs



## [0.1.0] - 2021-01-01

### Added

* Create and approve new megathreads at a customizable interval
* Sync current metathread content from wiki page when changed
* Generate fully customizable title with variable replacement
* Load and sync post text drawn from a wiki page
* Customizable replace patterns for post text
* Pin the new thread and unpin the old thread
* Supports any subreddit; no hardcoding
* Session and timestamp caching to avoid unnecessary requests
* Controlled from automatically-generated JSON config file
* Can be run from a custom config file for multiple instances
* Basic CLI with run, version and help
