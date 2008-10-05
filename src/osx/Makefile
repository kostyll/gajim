include ../../extra.mk

SUBDIRS = ${OSX_IDLEMODULE} ${OSX_MODULES}

SRCS = __init__.py	\
       growler.py	\
       prep_py2app.py
DISTCLEAN = idle.so nsapp.so

include ../../buildsys.mk

all: ${OBJS} idle.so nsapp.so

# Don't depend on the actual file, we can create the symlink anyway
idle.so:
	rm -f idle.so
	ln -s idle_c/idle.so idle.so
nsapp.so:
	rm -f nsapp.so
	ln -s nsapp_m/nsapp.so nsapp.so

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/osx && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/osx/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
