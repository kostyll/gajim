AC_INIT([Gajim - A Jabber Instant Messager],
		[0.13.10.0-dev],[http://trac.gajim.org/],[gajim])
AC_PREREQ([2.59])
AC_CONFIG_MACRO_DIR(m4)
AC_CONFIG_SRCDIR(src)
AC_CONFIG_HEADER(config.h)
AC_CONFIG_AUX_DIR(.)

AC_CANONICAL_HOST
AC_CANONICAL_TARGET

AC_ISC_POSIX
AC_PROG_CC
AC_PROG_OBJC
AC_PROG_LN_S
AC_PROG_INSTALL
AM_PROG_INSTALL_SH
AC_C_CONST
AC_CHECK_HEADERS([libintl.h])

BUILDSYS_SHARED_LIB

IT_PROG_INTLTOOL([0.35.0])
PKG_PROG_PKG_CONFIG([0.19])

GETTEXT_PACKAGE=gajim
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE],["$GETTEXT_PACKAGE"], [Gettext package])
AM_GLIB_GNU_GETTEXT
AM_NLS


dnl ****
dnl pygtk and gtk+
dnl ****
PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.16.0 pygtk-2.0 >= 2.16.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)

AM_PATH_PYTHON([2.5])
if test "x$PYTHON" = "x:"; then
	AC_MSG_ERROR([Python not found])
fi
AC_SUBST(PYTHON_FLAGS, $PYTHON_FLAGS)

dnl ****
dnl Cocoa
dnl ****
AC_ARG_ENABLE([cocoa],
  [  --disable-cocoa         do not build cocoa integration [default auto]],
  enable_cocoa=$enableval, enable_cocoa=yes)

if test "x$enable_cocoa" = "xyes"; then
  dnl There is no pkgconfig for cocoa; lets do a header check
  temp_save_cflags="$CFLAGS"
  CFLAGS="$CFLAGS -ObjC"
  AC_CHECK_HEADER(Cocoa/Cocoa.h, [have_cocoa=true], [have_cocoa=false])
  AC_CHECK_HEADER(AppKit/AppKit.h, [have_appkit=true], [have_appkit=false])
  CFLAGS="$temp_save_cflags"

  if test x"$have_cocoa" = x"true" -a x"$have_appkit" = x"true"; then
    AC_SUBST(OSX_MODULES, "growl nsapp_m syncmenu")
  else
    AC_SUBST(OSX_MODULES, "")
  fi
fi

dnl ****
dnl Carbon
dnl ****
AC_ARG_ENABLE([carbon],
  [  --disable-carbon        do not build with carbon [default auto]],
  enable_carbon=$enableval, enable_carbon=yes)

if test x"$enable_carbon" = x"yes";then 
  dnl There is no pkgconfig for carbon; lets do a header check
  AC_CHECK_HEADER(Carbon/Carbon.h, [have_carbon=true], [have_carbon=false])
  AC_CHECK_HEADER(IOKit/IOKitLib.h, [have_iokit=true], [have_iokit=false])

  if test x"$have_carbon" = x"true" -a x"$have_iokit" = x"true"; then
     have_idle_osx=true
     dnl Disable custom trayicon
     have_trayicon=gtk+
     dnl Hack to work around failure in gettext package detection on OS/X
     if test "x$GMSGFMT" = "x";then
        AC_SUBST(GMSGFMT, msgfmt)
        AC_SUBST(MSGFMT, msgfmt)
        AC_SUBST(XGETTEXT, xgettext)
     fi
     AC_SUBST(OSX_IDLEMODULE, "idle_c")
  else
     AC_SUBST(OSX_IDLEMODULE, "")
     have_carbon=false
     have_idle_osx=false
  fi
fi

ACLOCAL_AMFLAGS="\${ACLOCAL_FLAGS}"
AC_SUBST(ACLOCAL_AMFLAGS)

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])
AC_SUBST([PYTHON_INCLUDES])

dnl ****
dnl enable installation in python-2.x/site-packages/gajim
dnl ****
AC_ARG_ENABLE(site-packages,
  [AS_HELP_STRING([--enable-site-packages],
	[install gajim sources in PYTHONDIR/site-packages/gajim
instead of DATADIR/gajim/src.])]
,
AC_SUBST([gajim_srcdir], [\${pkgpythondir}])
,
AC_SUBST([gajim_srcdir], [\${datadir}/\${PACKAGE}/src])
)

AS_AC_EXPAND(GAJIM_SRCDIR, "${gajim_srcdir}")
AS_AC_EXPAND(PKGDATADIR, "${datadir}/${PACKAGE}")
AS_AC_EXPAND(DOCDIR, "${docdir}")
AS_AC_EXPAND(LOCALEDIR, "${localedir}")

AC_SUBST(PACKAGE, gajim)
AC_SUBST(VERSION, 0.12.1.5)

AC_CONFIG_FILES([ 
	buildsys.mk
	extra.mk
	data/gajim.desktop.in
	data/defs.py
	scripts/gajim
	scripts/gajim-remote:scripts/gajim.in
	scripts/gajim-history-manager:scripts/gajim.in
	po/Makefile.in
])
BUILDSYS_TOUCH_DEPS
AC_OUTPUT
echo "
*****************************
  Installation:
    Prefix ........... ${prefix}
    Python modules ... ${GAJIM_SRCDIR}
    Documentation .... ${DOCDIR}
    Others ........... ${PKGDATADIR}
*****************************"
