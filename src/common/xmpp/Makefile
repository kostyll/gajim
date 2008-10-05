SRCS = __init__.py	\
       auth.py		\
       auth_nb.py	\
       browser.py	\
       c14n.py		\
       client.py	\
       client_nb.py	\
       commands.py	\
       debug.py		\
       dispatcher.py	\
       dispatcher_nb.py	\
       features.py	\
       features_nb.py	\
       filetransfer.py	\
       idlequeue.py	\
       protocol.py	\
       roster.py	\
       roster_nb.py	\
       session.py	\
       simplexml.py	\
       transports.py	\
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
