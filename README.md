# Quetzalcoatl

## MPD Client for KDE

Quetzalcoatl is an MPD client for KDE.

It's one (Python) file. To run it, just make it executable and execute it.

It requires [python-mpd](http://jatreuman.indefero.net/p/python-mpd/) 3.0 and Python 2 (2.6 or newer).

Please note that it needs to be run on a [PEP394](http://www.python.org/dev/peps/pep-0394/)-compliant Linux system. PEP394 compliance means that your PATH contains a **python2** executable that launches the Python 2 interpreter. If you're system is not compliant, then you can make it compliant by creating a symlink. For example, you can make Slackware 13.37 compliant with the following two commands:

> cd /usr/bin ; ln -s python2.6 python

* [Homepage](http://duganchen.ca/project/software-development/quetzalcoatl-mpd-client)
* [Project Page](https://github.com/duganchen/quetzalcoatl/)
