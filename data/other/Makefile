include ../../buildsys.mk

install-extra:
	for i in *.pem *.xml; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/other && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/other/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
