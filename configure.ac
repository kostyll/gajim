AC_INIT([Gajim - A Jabber Instant Messager],
		[0.12.1.2-svn],[http://trac.gajim.org/],[gajim])
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
PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.8.0 pygtk-2.0 >= 2.8.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)

dnl *****
dnl dbus
dnl *****
AC_ARG_ENABLE([remote], 
  [  --disable-remote        disable remote control via DBus [default auto]],
  enable_remote=$enableval, enable_remote=auto)

if test "x$enable_remote" = "xauto"; then
	 PKG_CHECK_EXISTS([dbus-1],enable_remote=yes,enable_remote=no)
fi

if test "x$enable_remote" = "xyes";then
	PKG_CHECK_MODULES([DBUS], [dbus-1 >= 0.60])
	AC_SUBST(DBUS_CFLAGS)
	AC_SUBST(DBUS_LIBS)
	have_remote=true
else
	have_remote=false
fi
AM_CONDITIONAL(BUILD_REMOTE_CONTROL, $have_remote)

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

dnl ****
dnl tray icon
dnl ****
AC_ARG_ENABLE(trayicon,
  [  --disable-trayicon      do not build trayicon module [default yes]],
  enable_trayicon=$enableval, enable_trayicon=yes)
if test "x$enable_trayicon" = "xyes" -a "x$have_cocoa" != "xtrue"; then
	have_trayicon=true
	AC_SUBST(TRAYMODULE, traymodule)
else
	have_trayicon=false
	AC_SUBST(TRAYMODULE,)
fi

ACLOCAL_AMFLAGS="\${ACLOCAL_FLAGS}"
AC_SUBST(ACLOCAL_AMFLAGS)

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])
AC_SUBST([PYTHON_INCLUDES])

AS_AC_EXPAND(DATADIR, "${datadir}")
AS_AC_EXPAND(LIBDIR, "${libdir}")
AS_AC_EXPAND(DOCDIR, "${docdir}")
AS_AC_EXPAND(LOCALEDIR, "${localedir}")

AC_SUBST(VERSION)
AC_SUBST(PACKAGE, gajim)

AC_CONFIG_FILES([ 
	buildsys.mk
	extra.mk
	data/gajim.desktop.in
	data/defs.py
	scripts/gajim
	scripts/gajim-remote
	scripts/gajim-history-manager
	po/Makefile.in
])
BUILDSYS_TOUCH_DEPS
AC_OUTPUT
echo " 
***************************** 
  Build features:
    spell check ...... ${have_gtkspell}
    remote control ... ${have_remote}
    trayicon ......... ${have_trayicon}
    idle module OSX .. ${have_idle_osx}
    cocoa (OSX)....... ${have_cocoa}
*****************************"
