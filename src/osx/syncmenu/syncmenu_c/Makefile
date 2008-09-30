# Python calls these .so, even on OS X, which is very wrong. It should be .impl!
PLUGIN = syncmenu.so
SRCS = pysyncmenu.c \
       syncmenu.c

include ../../../../buildsys.mk
include ../../../../extra.mk

# FIXME: This should be done properly...
CFLAGS += ${PLUGIN_CFLAGS} ${PYTHON_CFLAGS} $$(pkg-config --cflags gtk+-2.0 pygobject-2.0)
LIBS += ${PYTHON_LIBS} ${PYGTK_LIBS} $$(pkg-config --libs gtk+-2.0 pygobject-2.0)
LDFLAGS += ${PLUGIN_LDFLAGS} ${PYTHON_LDFLAGS} -framework CoreFoundation
