# Python calls these .so, even on OS X, which is very wrong. It should be .impl!
PLUGIN = idle.so
SRCS = idle.c

include ../../../buildsys.mk
include ../../../extra.mk

CFLAGS += ${PLUGIN_CFLAGS} ${PYTHON_CFLAGS}
LIBS += ${PYTHON_LIBS}
LDFLAGS += ${PLUGIN_LDFLAGS} ${PYTHON_LDFLAGS} -framework CoreFoundation
