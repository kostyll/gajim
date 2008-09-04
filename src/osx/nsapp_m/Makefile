# Python calls these .so, even on OS X, which is very wrong. It should be .impl!
PLUGIN = nsapp.so
SRCS = nsapp.m

include ../../../buildsys.mk
include ../../../extra.mk

OBJCFLAGS += ${PLUGIN_CFLAGS} ${PYTHON_CFLAGS}
LIBS += ${PYTHON_LIBS}
LDFLAGS += ${PLUGIN_LDFLAGS} ${PYTHON_LDFLAGS} -framework CoreFoundation
