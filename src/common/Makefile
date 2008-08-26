# FIXME: Install files
include ../../extra.mk

SUBDIRS = xmpp zeroconf ${IDLEMODULE}

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
       logger.py		\
       nslookup.py		\
       optparser.py		\
       passwords.py		\
       pep.py			\
       proxy65_manager.py	\
       pubsub.py		\
       rst_xhtml_generator.py	\
       sleepy.py		\
       socks5.py		\
       stanza_session.py	\
       xmpp_stringprep.py

include ../../buildsys.mk

all: ${OBJS}

# Don't depend on the actual file, we can create the symlink anyway
idle.so:
	rm -f idle.so
	ln -s idle_c/idle.so idle.so
