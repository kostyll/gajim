SUBDIRS = growl_c growlImage_m

SRCS = Growl.py		\
       __init__.py
DISTCLEAN = _growl.so _growlImage.so

include ../../../buildsys.mk

all: ${OBJS} _growl.so _growlImage.so

# Don't depend on the actual file, we can create the symlink anyway
_growl.so:
	rm -f _growl.so
	ln -s growl_c/_growl.so _growl.so
_growlImage.so:
	rm -f _growlImage.so
	ln -s growlImage_m/_growlImage.so _growlImage.so

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/osx/growl && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/osx/growl/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
