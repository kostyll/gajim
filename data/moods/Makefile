include ../../buildsys.mk

install-extra:
	for i in */*.png; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/moods/$$(dirname $$i) && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/moods/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
