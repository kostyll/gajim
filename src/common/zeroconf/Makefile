SRCS = __init__.py			\
       client_zeroconf.py		\
       connection_handlers_zeroconf.py	\
       connection_zeroconf.py		\
       roster_zeroconf.py		\
       zeroconf.py			\
       zeroconf_avahi.py		\
       zeroconf_bonjour.py

include ../../../buildsys.mk

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/common/zeroconf && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/common/zeroconf/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done

all: ${OBJS}
