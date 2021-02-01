# Megathread Manager

A Reddit bot to automatically generate, create, pin and update megathreads, as well as related tasks.
Additionally, can be used alongside or as well as automatically sync and reformat content between wiki pages and sections of the same (including the sub's sidebar and other content).
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

Finally, install the necessary dependencies (currently only PRAW) using `pip` (or they can be installed with your systemwide package manager, if you use system Python or ``--system-site-packages`` when creating the venv):

```bash
pip install -r requirements.txt
```



## Usage

Currently, to run Megathread Manager, you'll need to activate the appropriate environment you created previously, and then run it as a script with Python.
To see the various command-line options available, pass it the ``--help`` flag.

```bash
source env/bin/activate
python megathreadmanager.py --help
```



## Configuration

Megathread manager automatically generates its config file, currently formatted as JSON, on first run, and updates it with any new parameters added thereafter.
Currently, both the static and dynamic/runtime configuration are stored in this file, though this will change in the future.
By default, the file is located at ``~/.config/megathread_manager/config.json``, but you can specify an alternate config file with the ``--config-file`` command line argument, allowing you to run multiple bots (e.g. for different subs) with different configurations.

All configuration, except for ``repeat_interval_s``, is read and updated for each run while ``megathread-manager`` is active, so settings can be changed on the fly without stopping and restarting it.

It can be set to use separate accounts for actually posting the megathread and performing an moderation actions; only the latter is required to be a moderator.
You'll need to configure and register the account(s) involved for Reddit app access with the Reddit API.
Common parameters (that are passed to PRAW, e.g. username/password, client id/client secret, refresh token, etc) go in the ``praw_credentials`` dict, while any specific to one user or another go in the two more specifically named ones; if none of the latter are specified, the same account is used for both.

To disable the megathread features entirely and only use the wiki sync feature, set ``megathread_enabled`` to ``false``.
For simplicity, ``replace_patterns`` are currently plain text (no regex), though support for the latter may be added in the future.

The ``pattern``s of text specified in ``source`` and ``targets`` are searched for in pseudo Markdown "comments", i.e. empty links that don't appear in the rendered text, like so:

```markdown
[](#/ <PATTERN><PATTERN_START>)

Example section content

[](#/ <PATTERN><PATTERN_END>)
```

If any variable (``pattern``, ``pattern_start``, ``pattern_end``) is not specified for a ``target``, the value from ``source`` is used.
Conversely, any ``replace_patterns`` for a specific target are applied after (and in addition) to those specified in ``source`` for all targets; note the ``source`` section is *not* actually modified unless it is specified as a ``target``.



## Running as a service

The provided systemd unit file allows easily running it as a user service; just copy it to the ``~/.config/systemd/user` directory (creating it if it doesn't already exist).
It currently assumes the `megathread-manager` directory lives at ``~/bots/megathread-manager`` and the virtual environment also lives at ``env`` in that directory; you can modify it to specify the names and paths on your system.
It can be enabled and started in the typical way,

```bash
systemctl --user daemon-reload
systemctl --user enable megathread-manager
systemctl --user start megathread-manager
```

Note that there are [a few considerations to keep in mind](https://wiki.archlinux.org/index.php/systemd/User#Automatic_start-up_of_systemd_user_instances) when running as a user instance of systemd, most notably to get it to autostart on boot rather than login and persist after the user is logged out (e.g. on a server, VPS or other unattended box).
