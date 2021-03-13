

#!/usr/bin/env python
# -*- coding: utf-8 -*-
# modified from https://encarsia.github.io/en/posts/setuptools-spicker/

import glob
import os
import shutil
import site
import codecs
import sys
import pathlib

from setuptools import setup, Command
from setuptools.command.install import install


# get the version here
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")

# path related stuff
here = = pathlib.Path(__file__).parent
rel_icon_path_scalable = "share/icons/hicolor/scalable/apps"

# package meta data
NAME = "XMIssion"
DESCRIPTION = "XMIssion XMI/AWS/HET Gnome File Manager"
URL = "https://github.com/mainframed/xmission"
EMAIL = "mainframed767@gmail.com"
AUTHOR = "Philip Young"
LICENSE = "GPLv2"
URL = "https://github.com/encarsia/non"
VERSION = get_version("xmission/xmission.py"),
REQUIRES_PYTHON = ">=3.8"
REQUIRED = [
            "PyGObject",
            "xmi-reader",
            ]
# put desktop and app icon in the right place
DATAFILES = [
        ('share/icons/hicolor/48x48/apps', ['xmission/ui/xmission.png']),
        (rel_icon_path_scalable, ['xmission/ui/xmission.svg']),
        ('share/applications', ['data/org.github.xmission.desktop']),
            ]
# add non-code ui (glade/icon) files
PACKAGES = ["xmission"]
PACKAGE_DIR = {"xmission": "xmission"}
PACKAGE_DATA = {"xmission":
                    [
                    "ui/*",
                    ]
                }

with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = "\n" + f.read()

def _find_install_path():
    if "--user" in sys.argv:
        inst = site.getusersitepackages()
        prefix = site.getuserbase()
    else:
        inst = site.getsitepackages()[0]
        prefix = sys.prefix
    return inst, prefix


class CustomInstall(install):

    def run(self):
        install_path, prefix = _find_install_path()
        self.update_desktop_file("data/org.github.xmission.desktop.in",
                                 install_path,
                                 os.path.join(prefix, rel_icon_path_scalable))
        install.run(self)

    def update_desktop_file(self, filename, install_path, icon_path):
        """Set exec/icon path of install dir in .desktop file."""
        with open(filename) as f:
            content = f.readlines()
        content_new = ""
        for line in content:
            if line.startswith("Exec="):
                line = line.replace("/path/to/xmission/xmission", install_path)
            elif line.startswith("Icon="):
                line = line.replace("../xmission/ui/", "")
            content_new += line
        with open("data/org.github.xmission.desktop", "w") as f:
            f.writelines(content_new)


class UnInstall(Command):
    """Custom command to remove all files from the install/build/sdist processes.
       This includes
            * files in the extracted repo folder
            * the Python module
            * .desktop files and the application icon

       Usage: 1) run 'python setup.py uninstall' without any options for
                    uninstalling system-wide, you may run this command
                    with superuser privilege
              2) run 'python setup.py uninstall --user' to undo
                    installation in local user directory.
    """

    description = "remove files from installation and build processes"
    user_options = [("user", "u", "delete local user installation")]

    def initialize_options(self):
        """Abstract method that is required to be overwritten.
           Define all available options here.
        """
        self.user = None

    def finalize_options(self):
        """Abstract method that is required to be overwritten."""

    def run(self):
        install_path, prefix = _find_install_path()

        print("Removing setuptools files...")
        dir_list = ["build",
                    "dist",
                    "non.egg-info",
                    ]
        for d in dir_list:
            try:
                shutil.rmtree(d)
                print("Removed '{}' folder...".format(d))
            except OSError as e:
                print(self._oserr_message(e, d))

        print("Removing Python package...") # and also the Egg dir
        for match in glob.glob(os.path.join(install_path, "non*")):
            try:
                shutil.rmtree(match)
            except OSError as e:
                print(self._oserr_message(e, match))

        print("Removing desktop files...")
        desktop_files = [(prefix, "share/applications", "org.github.xmission.desktop"),
                         (prefix, rel_icon_path_scalable, "xmission.svg"),
                         (prefix, "share/icons/hicolor/48x48/apps", "xmission.png"),
                         ("data", "org.github.xmission.desktop"),
                         ]
        for f in desktop_files:
            filepath = os.path.join(*f)
            try:
                os.remove(filepath)
                print("Removed '{}'...".format(filepath))
            except OSError as e:
                print(self._oserr_message(e, filepath))

    def _oserr_message(self, e, name):
        if e.errno == 2:
            return "Info: '{}' - {}.".format(name, e.strerror)
        else:
            return "Error: '{}' - {}.".format(name, e.strerror)

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    license=LICENSE,
    packages=PACKAGES,
    package_dir=PACKAGE_DIR,
    package_data=PACKAGE_DATA,
    install_requires=REQUIRED,
    include_package_data=True,
    data_files=DATAFILES,
    cmdclass={"install": CustomInstall,
              "uninstall": UnInstall,
              }
    )