include ../../extra.mk

SUBDIRS = ${OSX_IDLEMODULE} ${OSX_MODULES}

SRCS = __init__.py	\
       dbus.py		\
       growler.py	\
       prep_py2app.py
DISTCLEAN = idle.so nsapp.so

include ../../buildsys.mk

PACKAGE := ${PACKAGE}/src/osx
DATA = ${OBJS}

all: ${OBJS} idle.so nsapp.so

# Don't depend on the actual file, we can create the symlink anyway
idle.so:
	rm -f idle.so
	ln -s idle_c/idle.so idle.so
nsapp.so:
	rm -f nsapp.so
	ln -s nsapp_m/nsapp.so nsapp.so
