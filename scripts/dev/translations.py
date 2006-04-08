#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Initially written by Nikos Kouremenos
# Dedicated to Yann Le Boulanger
# Usage: './translations.py [help] [stats] [update]'

import os
import sys

stats = False
update = False
check = False

def visit(arg, dirname, names):
	if dirname.find('.svn') != -1:
		return
	if dirname.endswith('LC_MESSAGES'):
		if 'gajim.po' in names:
			path_to_po = os.path.join(dirname, 'gajim.po')
			pos = path_to_po.find('po/') + 3 #3 = len('po/')
			endpos = path_to_po.find('/', pos)
			name = path_to_po[pos:endpos]
			if update: # update an existing po file)
				os.system('msgmerge -q -U ../../po/'+name+'/LC_MESSAGES/gajim.po ../../po/gajim.pot')
			if stats:
				print name, 'has now:'
				os.system('msgfmt --statistics ' + path_to_po)
			if check:
				os.system('msgfmt -c ' + path_to_po)
		else:
			print 'PROBLEM: cannot find gajim.po in', dirname

def show_help():
	print sys.argv[0], '[help] [stats] [update] [check]'
	sys.exit(0)

def update_pot():
	# create header for glade strings
	os.system('intltool-extract --type=gettext/glade ../../src/gtkgui.glade')
	os.system('intltool-extract --type=gettext/glade ../../src/'
		'history_manager.glade')
	# update the pot
	os.system('make -C ../../po/ all gajim.pot')
	print 'gajim.pot was updated successfully'

if __name__ == '__main__':
	if os.path.basename(os.getcwd()) != 'dev':
		print 'run me with cwd: scripts/dev'
		sys.exit()

	path_to_dir = '../../po'

	if len(sys.argv) == 2:
		if sys.argv[1].startswith('h'):
			show_help()

		param = sys.argv[1]
		if param == 'stats': # stats only
			stats = True
			os.path.walk(path_to_dir, visit, None)
		elif param == 'update': # update only
			update_pot()
			update = True
			os.path.walk(path_to_dir, visit, None) # update each po & no stats
			print 'Done'
		elif param == 'check':
			check = True
			os.path.walk(path_to_dir, visit, None)

	elif len(sys.argv) == 1: # update & stats & no check
		update_pot()
		update = True
		stats = True
		os.path.walk(path_to_dir, visit, None)
		print 'Done'

	else:
		show_help()

