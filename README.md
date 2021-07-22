# Sub Manager

Sub Manager is a bot framework for Reddit to automate a variety of tasks on one or more subreddits, and can be configured and run without writing any code.
Its initial application was to automatically generate, create, pin and update threads, as well as related tasks.
Additionally, it can be used to automatically sync and reformat content between wiki pages, widgets and threads, as well as marked sections of the same (including the sub's sidebar and other content).
It includes an installable systemd service unit for real-time operation on modern Linux distributions, which is used in production for the r/SpaceX subreddit, or can be run by any other means you choose on your system.



## Installation

Currently, install is manual-only, but refactoring as a proper Python package is imminent.
To install, first clone the repo to any desired directory with ``git``.

```
git clone <REPO-URL>
cd submanager
```

Then, while it can be installed in your system Python, we highly recommend you create and activate a virtual environment to avoid any conflicts with other packages on your system or causing any other issues
For example, using venv:

```bash
python3 -m venv env
source env/bin/activate
```

Currently, to install the necessary dependencies using `pip`, you must do so via the ``requirements.txt``:

```bash
pip install -r requirements.txt
```

Alternatively, they can be installed with your systemwide package manager or Python distribution, if you use system Python (not recommended) or ``--system-site-packages`` when creating the venv.



## Usage

To run Sub Manager, you'll need to activate the appropriate environment you created previously, and then run it as a script with Python.
To see the various command-line options available, pass it the ``--help`` flag.

```bash
source env/bin/activate
python submanager.py --help
```



## Configuration

First, you'll want to generate the primary Sub Manager user config file, in order to tell it what you want it to do.
To do so, simply run ``python submanager.py generate-config`` to generate it at the default path, and a stock config file with some starting examples will be output (formatted as TOML for humans).
By default, the file is located at ``~/.config/submanager/config.toml``, with dynamically-updated, programmatically-managed runtime config in ``dynamic_config.json`` in the same directory, and any refresh tokens saved in the ``refresh_tokens`` subdirectory.
However, you can specify an alternate config file for one or both with the various ``--config-path`` command line arguments, allowing you to run multiple instances of the bot simultaneously on the same machine (for example, to avoid cramming everything into one big configuration file, or use multiple cores).

To improve robustness and enforce safe maintenance practices, Sub Manager must now be stopped and restarted to read-in updated config.
Individual modules, such as ``sync_manager`` and ``thread_manager``, can be enabled and disabled via their corresponding ``enabled`` options, and can be further configured as described below.
To perform a variety of checks that your configuration is valid and will result in a successful run, without actually executing any state-changing Reddit actions, run ``python submanager.py validate-config``; if an error occurs, informative output will explain the problem and, often, how to fix it.



### Configuring credentials

Starting with Sub Manager v0.5.0 and later, the Reddit account to use for a given action can be specified per module (``sync_manager``, ``thread_manager``), per task (sync item, thread) and even per source and target, as well as globally.
You'll need to configure and register the account(s) involved for Reddit app access with the Reddit API.
We recommend you configure your credentials in ``praw.ini`` and simply refer to them via the PRAW ``site_name`` argument of the respective account listed under the ``accounts`` table, which will avoid any secrets leaking if you accidentally or deliberately store your ``config.toml`` somewhere public.
However, if you prefer, the various arguments that ``praw.Reddit()`` can accept, e.g. username/password, client id/client secret, refresh token, etc) can be also all be included as subkeys of the named account in the ``accounts`` table.
Sub Manager fully supports the new Reddit refresh token handling; just enter your initial refresh token under the `refresh_token` key for the account in the ``accounts`` table, and it will automatically set up a handler to store it and keep it updated going forward.


### Posting intervals

If posting new threads is enabled for a configured thread item, it can be set to either post daily, monthly, yearly etc. as soon as the period ticks over (e.g. first of the month), or at an interval of every N periods after the previous thread was posted.

``new_thread_interval`` is specified as a string, either in the form ``"UNIT"`` (e.g. ``"daily"``, ``"month"``, etc) to trigger the first behavior, or `"N UNIT"` (e.g. ``"10 weeks"``, ``"1 year"``, etc) to invoke the second, where ``N`` is a positive integer and ``UNIT`` is a supported period unit.
Supported period units for both include years, months, days, hours, minutes and seconds; weeks are currently supported for the latter, but not the former (since there is no unambiguously agreed-upon, locale-independent start of a week, and they don't divide evenly into months or years).
For either form, the units can be given with or without `s` or `ly` as suffices.

There's currently a minor limitation with this as currently implemented: getting it to create a new thread "on-demand" rather than on a schedule (or not at all) is not completely obvious.
There is a relatively simple workaround, however—just set the ``new_thread_interval`` to ``false``, and then whenever you want a new thread, set it to e.g. ``1 day``, wait `repeat_interval_s` seconds for it to create the new thread (or manually restart it, if you're impatient), and then set it back to ``false``.

We will soon add a proper feature for this, likely in the form of a new CLI command, e.g. ``submanager create-thread <thread_name>``, to programmatically tell the running Sub Manager instance to create a new post on-demand.


### Syncing sections

The ``pattern``s of text specified in ``source`` and ``targets`` are searched for in pseudo-Markdown "comments", i.e. empty links that don't appear in the rendered text, like so:

```markdown
[](#/ <PATTERN><PATTERN_START>)

Example section content

[](#/ <PATTERN><PATTERN_END>)
```

This allows easily syncing just specific sections between sources and targets.

If any variable (e.g. ``pattern``) is not specified for a ``target``, the value is recursively inherited from the respective ``defaults`` table in the sync pair, and then sync config section, including the ``context`` sub-table in each as well as the ``default_context`` in the config.
Conversely, any ``replace_patterns`` for a specific target are applied after (and in addition) to those specified in ``source`` for all targets; note the ``source`` section is *not* actually modified unless it is specified as a ``target``.



## Running as a service

The provided systemd unit file allows easily running it as a user service; just copy it to the ``~/.config/systemd/user`` directory (creating it if it doesn't already exist).
It currently assumes the `submanager` directory lives at ``~/bots/submanager`` and the virtual environment also lives at ``env`` in that directory; you can modify it to specify the names and paths on your system.
It can be enabled and started in the typical way,

```bash
systemctl --user daemon-reload
systemctl --user enable submanager
systemctl --user start submanager
```

Note that there are [a few considerations to keep in mind](https://wiki.archlinux.org/index.php/systemd/User#Automatic_start-up_of_systemd_user_instances) when running as a user instance of systemd, most notably to get it to autostart on boot rather than login and persist after the user is logged out (e.g. on a server, VPS or other unattended box).
