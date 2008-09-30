SUBDIRS = syncmenu_c
DISTCLEAN = syncmenu.so

include ../../../buildsys.mk

PACKAGE := ${PACKAGE}/src/osx/syncmenu
DATA = ${OBJS}

all: ${OBJS} syncmenu.so

# Don't depend on the actual file, we can create the symlink anyway
syncmenu.so:
	rm -f syncmenu.so
	ln -s syncmenu_c/syncmenu.so syncmenu.so
