include ../../buildsys.mk

install-extra:
	for i in *.wav; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/sounds && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/sounds/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
