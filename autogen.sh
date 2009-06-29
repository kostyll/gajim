#!/bin/sh
if ! which pkg-config >/dev/null 2>&1; then
	echo "*** ERROR: pkg-config not found ***"
	echo "See README.html for build requirements."
	exit 1
fi

echo "[encoding: UTF-8]" > po/POTFILES.in && \
ls -1 data/gajim.desktop.in.in data/glade/*.glade \
	src/*.py src/common/*.py src/common/zeroconf/*.py src/osx/*.py | \
	grep -v ipython_view.py >>po/POTFILES.in || exit 1

intltoolize --force && \
aclocal -I ./m4 && \
autoheader && \
autoconf && \
./configure ${CONF_ARGS} $@
