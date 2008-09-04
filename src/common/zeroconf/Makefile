SRCS = __init__.py			\
       client_zeroconf.py		\
       connection_handlers_zeroconf.py	\
       connection_zeroconf.py		\
       roster_zeroconf.py		\
       zeroconf.py			\
       zeroconf_avahi.py		\
       zeroconf_bonjour.py

include ../../../buildsys.mk

PACKAGE := ${PACKAGE}/src/common/zeroconf
DATA = ${OBJS}

all: ${OBJS}
