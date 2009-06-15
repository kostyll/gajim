SUBDIRS = data src po scripts

include buildsys.mk
include extra.mk

.PHONY: dist

dist:
	rm -fr dist
	hg archive -t files dist/gajim-${VERSION}
	cp configure config.h.in dist/gajim-${VERSION}
	cp po/Makefile.in.in po/POTFILES.in dist/gajim-${VERSION}/po
	chmod +x dist/gajim-${VERSION}
	cd dist && tar cfz ../gajim-${VERSION}.tar.gz gajim-${VERSION}
	rm -fr dist
	echo "Successfully created gajim-${VERSION}.tar.gz."
