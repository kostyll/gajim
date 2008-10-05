include ../../buildsys.mk

install-extra:
	for i in */*/*.png */*/*/*.png; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/iconsets/$$(dirname $$i) && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/iconsets/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
