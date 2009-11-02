SUBDIRS = implementation

SRCS = dispatching.py	\
       errors.py	\
       framework.py	\
       __init__.py	\
       mapping.py

include ../../buildsys.mk

all: ${OBJS}

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/command_system && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/command_system/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
