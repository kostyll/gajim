include ../extra.mk

SUBDIRS = common ${TRAYMODULE} ${SPELLMODULE} osx

SRCS = adhoc_commands.py		\
       advanced.py			\
       atom_window.py			\
       cell_renderer_image.py		\
       chat_control.py			\
       config.py			\
       conversation_textview.py		\
       dataforms_widget.py		\
       dialogs.py			\
       disco.py				\
       dock.py				\
       features_window.py		\
       filetransfers_window.py		\
       gajim-remote.py			\
       gajim.py				\
       gajim_themes_window.py		\
       groupchat_control.py		\
       groups.py			\
       gtkexcepthook.py			\
       gtkgui_helpers.py		\
       history_manager.py		\
       history_window.py		\
       htmltextview.py			\
       ipython_view.py			\
       message_control.py		\
       message_textview.py		\
       message_window.py		\
       music_track_listener.py		\
       negotiation.py			\
       network_manager_listener.py	\
       notify.py			\
       profile_window.py		\
       remote_control.py		\
       roster_window.py			\
       search_window.py			\
       secrets.py			\
       session.py			\
       statusicon.py			\
       systray.py			\
       tooltips.py			\
       vcard.py
DISTCLEAN = gtkspell.so trayicon.so

include ../buildsys.mk

all: ${OBJS} gtkspell.so trayicon.so

# Don't depend on the actual file, we can create the symlink anyway
gtkspell.so:
	rm -f gtkspell.so
	ln -s spellmodule/gtkspell.so gtkspell.so
trayicon.so:
	rm -f trayicon.so
	ln -s traymodule/trayicon.so trayicon.so

install-extra:
	for i in ${OBJS}; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${libdir}/${PACKAGE} && ${INSTALL} -m 644 $$i ${DESTDIR}${libdir}/${PACKAGE}/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
