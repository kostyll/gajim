# Python calls these .so, even on OS X, which is very wrong. It should be .impl!
PLUGIN = trayicon.so
SRCS = eggtrayicon.c	\
       trayiconmodule.c	\
       trayicon.c

include ../../buildsys.mk
include ../../extra.mk

CFLAGS += ${PLUGIN_CFLAGS} ${PYTHON_CFLAGS} ${PYGTK_CFLAGS}
LIBS += ${PYTHON_LIBS} ${PYGTK_LIBS}
LDFLAGS += ${PLUGIN_LDFLAGS} ${PYTHON_LDFLAGS}

trayicon.c: Makefile trayicon.defs trayicon.override
	pygtk-codegen-2.0 --prefix trayicon		\
		--register ${PYGTK_DEFS}/gdk-types.defs	\
		--register ${PYGTK_DEFS}/gtk-types.defs	\
		--override trayicon.override		\
		trayicon.defs >trayicon.c
