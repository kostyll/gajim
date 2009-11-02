SRCS = custom.py	\
       hosts.py		\
       __init__.py	\
       middleware.py	\
       standard.py

include ../../../buildsys.mk

all: ${OBJS}

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/command_system/implementation && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/command_system/implementation/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
