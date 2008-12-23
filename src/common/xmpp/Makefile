SRCS = __init__.py		\
       auth_nb.py		\
       bosh.py			\
       c14n.py			\
       client.py		\
       client_nb.py		\
       debug.py			\
       dispatcher_nb.py		\
       features_nb.py		\
       idlequeue.py		\
       protocol.py		\
       proxy_connectors.py	\
       roster_nb.py		\
       simplexml.py		\
       tls_nb.py		\
       transports_nb.py

include ../../../buildsys.mk

all: ${OBJS}

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/common/xmpp && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/common/xmpp/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
