include ../../buildsys.mk

install-extra:
	for i in *.glade; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/glade && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/glade/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
