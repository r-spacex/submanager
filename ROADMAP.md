# Roadmap

## [0.7.0] - 2021-10

* On-demand automated new thread generation and creation
* New command to automatically create sources and/or targets
* New command to generate clean config without examples
* Built-in support for refresh token setup
* Re-add support for optionally filling variables in the source/target content
* Add support for inline source declarations in the source content that get injected in the target
* Add optional regex support for replace patterns
* Improve error handling when one request/module fails
* Add YAML support for config
* Fully document config schema
* Improve setup/teardown in functional tests and check Reddit results more thoroughly



## [0.8.0] - 2021-12

* Refactor validators and managers into modular, extensible class-based architecture with consistent API
* More comprehensive validation and validator control
* Add a ``managed-thread`` source/target type, that targets the current thread for a key
* More unit and integration tests



## [1.0.0] - ???

* Greatly improve unit and integration test coverage
* Use Python logging module and add many more specific logging messages
* Further improve documentation
* Add ability to re/generate popup menu of threads (e.g. in removal dialog)?



## [2.0.0] - ???

* Add more desired features (sticky comments, moderation tools, more automod automation...)
* Add support for running within the Brokkr framework?
    * Create wrappers for plugin(s) for session, wiki sync and megathread sync
    * Create preset(s) for plugins(s)
* Create example Brokkr system config?
* Add more detailed logging, optionally integrated with Brokkr
