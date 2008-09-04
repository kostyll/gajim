# Python calls these .so, even on OS X, which is very wrong. It should be .impl!
PLUGIN = gtkspell.so
SRCS = gtkspellmodule.c

include ../../buildsys.mk
include ../../extra.mk

CFLAGS += ${PLUGIN_CFLAGS} ${PYTHON_CFLAGS} ${PYGTK_CFLAGS} ${GTKSPELL_CFLAGS}
LIBS += ${PYTHON_LIBS} ${PYGTK_LIBS} ${GTKSPELL_LIBS}
LDFLAGS += ${PLUGIN_LDFLAGS} ${PYTHON_LDFLAGS}
