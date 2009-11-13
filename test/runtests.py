#!/usr/bin/env python


'''
Runs Gajim's Test Suite

Unit tests tests will be run on each commit.
'''

import sys
import unittest
import getopt
use_x = True
verbose = 1

try:
	shortargs = 'hnv:'
	longargs = 'help no-x verbose='
	opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
except getopt.error, msg:
	print msg
	print 'for help use --help'
	sys.exit(2)
for o, a in opts:
	if o in ('-h', '--help'):
		print 'runtests [--help] [--no-x] [--verbose level]'
		sys.exit()
	elif o in ('-n', '--no-x'):
		use_x = False
	elif o in ('-v', '--verbose'):
		try:
			verbose = int(a)
		except Exception:
			print 'verbose must be a number >= 0'
			sys.exit(2)

# new test modules need to be added manually
modules = ( 'unit.test_xmpp_dispatcher_nb',
				'unit.test_xmpp_transports_nb',
				'unit.test_caps',
				'unit.test_contacts',
				'unit.test_gui_interface',
				'unit.test_sessions',
				'unit.test_account',
			 )
#modules = ()

if use_x:
	modules += ('integration.test_gui_event_integration',
					'integration.test_roster',
					'integration.test_resolver',
					'integration.test_xmpp_client_nb',
					'integration.test_xmpp_transports_nb'
	)

nb_errors = 0
nb_failures = 0

for mod in modules:
	suite = unittest.defaultTestLoader.loadTestsFromName(mod)
	result = unittest.TextTestRunner(verbosity=verbose).run(suite)
	nb_errors += len(result.errors)
	nb_failures += len(result.failures)

sys.exit(nb_errors + nb_failures)

# vim: se ts=3:
