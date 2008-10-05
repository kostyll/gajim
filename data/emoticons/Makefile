include ../../buildsys.mk

install-extra:
	for i in */emoticons.py */*.png */*.gif; do \
		${INSTALL_STATUS}; \
		if ${MKDIR_P} ${DESTDIR}${datadir}/${PACKAGE}/emoticons/$$(dirname $$i) && ${INSTALL} -m 644 $$i ${DESTDIR}${datadir}/${PACKAGE}/emoticons/$$i; then \
			${INSTALL_OK}; \
		else \
			${INSTALL_FAILED}; \
		fi \
	done
