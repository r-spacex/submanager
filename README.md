# Megathread Manager

A Reddit bot to automatically generate, create, pin and update megathreads, as well as related tasks.
Additionally, can be used alongside or as well as automatically sync and reformat content between wiki pages, widgets and threads, as well as marked sections of the same (including the sub's sidebar and other content).
Includes an installable systemd service unit for real-time operation on modern Linux distributions, which is used in production for the r/SpaceX subreddit, or can be run by any other means you choose on your system.



## Installation

Currently, install is manual-only, but refactoring as a proper Python package is imminent.
To install, first clone the repo to any desired directory with ``git``.

```
git clone <REPO-URL>
cd megathread-manager
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

Currently, to run Megathread Manager, you'll need to activate the appropriate environment you created previously, and then run it as a script with Python.
To see the various command-line options available, pass it the ``--help`` flag.

```bash
source env/bin/activate
python megathreadmanager.py --help
```



## Configuration

Megathread manager automatically generates its primary user config file (formatted as TOML for humans) on first run.
By default, the file is located at ``~/.config/megathread_manager/config.toml``, with dynamically-updated, programmatically-managed runtime config in ``dynamic_config.json`` in the same directory.
However, you can specify an alternate config file for one or both with the ``--config-path`` command line argument, allowing you to run multiple bots (e.g. for different subs) with different sets of accounts.

All configuration, except for ``repeat_interval_s``, is read and updated for each run while ``megathread-manager`` is active, so settings can be changed on the fly without stopping and restarting it.

Individual modules, such as ``megathreads`` and ``sync``, can be enabled and disabled via the corresponding options (e.g. ``megathreads`` and ``sync``) under the top-level ``enable`` table.


### Configuring credentials

Megathread manager can be set to use separate accounts for actually posting the megathread and performing an moderation actions; only the latter is required to be a moderator.
You'll need to configure and register the account(s) involved for Reddit app access with the Reddit API.
We recommend you configure your credentials in ``praw.ini`` and simply refer to them via the PRAW ``site_name`` argument of the respective account listed under the ``accounts`` table, which will avoid any secrets leaking if you accidentally or deliberately store your ``config.toml`` somewhere public.
The various parameters that ``praw.Reddit()`` can accept, e.g. username/password, client id/client secret, refresh token, etc) go in the ``mod`` and ``post`` subkeys of the ``acounts`` table for the respective mod account and public posting account.


### Posting intervals

If posting new threads is enabled for a megathread, it can be set to either post daily, monthly, yearly etc. as soon as the period ticks over (e.g. first of the month), or at an interval of every N periods after the previous thread was posted.

``new_thread_interval`` is specified as a string, either in the form ``"UNIT"`` (e.g. ``"daily"``, ``"month"``, etc) to trigger the first behavior, or `"N UNIT"` (e.g. ``"10 weeks"``, ``"1 year"``, etc) to invoke the second, where ``N`` is a positive integer and ``UNIT`` is a supported period unit.
Supported period units for both include years, months, days, hours, minutes and seconds; weeks are currently supported for the latter, but not the former (since there is no unambiguously agreed-upon, locale-independent start of a week, and they don't divide evenly into months or years).
For either form, the units can be given with or without `s` or `ly` as suffices.

There's currently a minor limitation with this as currently implemented: getting it to create a new thread "on-demand" rather than on a schedule (or not at all) is not completely obvious.
There is a relatively simple workaround, however—just set the ``new_thread_interval`` to ``false``, and then whenever you want a new thread, set it to e.g. ``1 day``, wait `repeat_interval_s` seconds for it to create the new thread (or manually restart it, if you're impatient), and then set it back to ``false``.

We could, and probably eventually will add a proper feature for this, likely in the form of a new CLI command, e.g. ``megathread-manager new-thread <thread_name>`` to programmatically tell the running manager instance to create a new one on-demand.
However, while it would be a bit more obvious and elegant than the current approach, it likely isn't much faster in practice.


### Syncing sections

The ``pattern``s of text specified in ``source`` and ``targets`` are searched for in pseudo-Markdown "comments", i.e. empty links that don't appear in the rendered text, like so:

```markdown
[](#/ <PATTERN><PATTERN_START>)

Example section content

[](#/ <PATTERN><PATTERN_END>)
```

This allows easily syncing just specific sections between sources and targets.

If any variable (e.g. ``pattern``) is not specified for a ``target``, the value from ``source`` is used.
Conversely, any ``replace_patterns`` for a specific target are applied after (and in addition) to those specified in ``source`` for all targets; note the ``source`` section is *not* actually modified unless it is specified as a ``target``.



## Running as a service

The provided systemd unit file allows easily running it as a user service; just copy it to the ``~/.config/systemd/user`` directory (creating it if it doesn't already exist).
It currently assumes the `megathread-manager` directory lives at ``~/bots/megathread-manager`` and the virtual environment also lives at ``env`` in that directory; you can modify it to specify the names and paths on your system.
It can be enabled and started in the typical way,

```bash
systemctl --user daemon-reload
systemctl --user enable megathread-manager
systemctl --user start megathread-manager
```

Note that there are [a few considerations to keep in mind](https://wiki.archlinux.org/index.php/systemd/User#Automatic_start-up_of_systemd_user_instances) when running as a user instance of systemd, most notably to get it to autostart on boot rather than login and persist after the user is logged out (e.g. on a server, VPS or other unattended box).
