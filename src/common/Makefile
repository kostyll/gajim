include ../../extra.mk

SUBDIRS = xmpp zeroconf

SRCS = GnuPG.py			\
       GnuPGInterface.py	\
       __init__.py		\
       atom.py			\
       caps.py			\
       check_paths.py		\
       commands.py		\
       config.py		\
       configpaths.py		\
       connection.py		\
       connection_handlers.py	\
       contacts.py		\
       crypto.py		\
       dataforms.py		\
       dbus_support.py		\
       defs.py			\
       dh.py			\
       events.py		\
       exceptions.py		\
       fuzzyclock.py		\
       gajim.py			\
       helpers.py		\
       i18n.py			\
       idle.py			\
       logger.py		\
       optparser.py		\
       passwords.py		\
       pep.py			\
       proxy65_manager.py	\
       pubsub.py		\
       resolver.py		\
       rst_xhtml_generator.py	\
       sleepy.py		\
       socks5.py		\
       stanza_session.py	\
       xmpp_stringprep.py

include ../../buildsys.mk

all: ${OBJS}

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE}/common && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/common/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
