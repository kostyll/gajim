include ../../buildsys.mk

install-extra:
	for i in *.bmp *.icns *.ico *.png *.svg agents/*.png dock_icns/*.icns events/*.png; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/pixmaps/$$(dirname $$i) && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/pixmaps/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
