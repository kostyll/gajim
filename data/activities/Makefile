include ../../buildsys.mk

install-extra:
	for i in */*/*.png; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/activities/$$(dirname $$i) && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/activities/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
