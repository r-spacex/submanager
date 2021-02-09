# Sub Manager Changelog


## Version 0.2.2 (2021-02-01)

Bugfix and enhancement release with the following changes:
* Add support for updating megathread links in wiki, sidebar/menu and removal messages
* Add basic error handling (restart, etc) to systemd service unit (to recover from random Reddit errors)
* Set unbuffered output so the systemd journal/syslog output is updated in real time
* Fix reliability issues with unstickying and stickying the correct sticky



## Version 0.2.1 (2021-01-22)

Bugfix and enhancement release with the following changes:
* Add option to enable/disable megathread manager module
* Recheck date more reliably every run
* Add requirements.txt for dependencies
* Add provided systemd service unit
* Add README with documentation
* Add ROADMAP with project roadmap
* Add LICENSE with MIT License
* Add Git metafiles



Version 0.2.0 (2021-01-21)

Major feature release with a major new module.

Add new Sync Manager module:
* Sync arbitrary source wiki pages to target wiki pages
* Sync full pages or subsections designated by special marker comments
* Supports multiple targets per source page with custom settings
* Customizable pattern replacements (i.e. for reformatting, etc) between them

Under the hood:
* Add accompanying config for sync manager
* Major code refactoring to support current and future changes
* Various minor bug fixes



## Version 0.1.2 (2021-01-20)

Performance and minor enhancement release with the following changes:
* Automatically update config with newly added options
* Cache current thread for better performance
* Further refactor session objects



## Version 0.1.1 (2021-01-20)

Bugfix and enhancement release with the following changes:
* Add ability to run in a loop at a set interval
* Fix various minor bugs
* Refactor config/variable names to make more sense



## Version 0.1.0 (2021-01-01)

Initial deployed release.

Major features:
* Create and approve new megathreads at a customizable interval
* Sync current metathread content from wiki page when changed
* Generate fully customizable title with variable replacement
* Load and sync post text drawn from a wiki page
* Customizable replace patterns for post text
* Pin the new thread and unpin the old thread

Under the hood:
* Supports any subreddit; no hardcoding
* Session and timestamp caching to avoid unnecessary requests
* Controlled from automatically-generated JSON config file
* Can be run from a custom config file for multiple instances
* Basic CLI with run, version and help
