#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import optparse, re, sys

try:
	import apt
except ImportError:
	print 'Unable to import Python APT module, please "apt-get install python-apt"!'
	sys.exit(3)

from pprint import pprint

# Define some constants
OK=0
WARN=1
CRIT=2
UNKNOWN=3
RETURNMSG=['OK', 'WARNING', 'CRITICAL', 'UNKNOWN']


# Command line options
parser = optparse.OptionParser()

parser.add_option('-d', '--dist-upgrade', action='store_true', dest='dist_upgrade', help='Use "dist-upgrade", otherwise "upgrade"')
parser.add_option('-c', '--critial', dest='critical', metavar='\'-[sS]ecurity\'', help='RegEx for label, which are critical updates')
parser.add_option('', '--keep', dest='pkgskeep', metavar='OK', help='Packages to keep > 0 is OK (default), WARNING or CRITICAL')
parser.add_option('', '--delete', dest='pkgsdelete', metavar='OK', help='Packages to delete > 0 is OK (default), WARNING or CRITICAL')
parser.add_option('', '--broken', dest='pkgsbroken', metavar='OK', help='Packages which are broken > 0 is OK (default), WARNING or CRITICAL')
parser.add_option('', '--showmaxpkgs', dest='showmaxpkgs', type=int, metavar=10, help='Show this number of packages in short output')
parser.add_option('', '--periodic-check', dest='periodic_check', action='store_true', help='Check if periodic check is enabled')
parser.add_option('', '--periodic-max-days', dest='periodic_max_days', type=int, metavar=1, help='Maximum days before automatic updates')
parser.add_option('-v', '--verbose', action='count', dest='verb', help='Verbose output')

parser.set_defaults(dist_upgrade=False)
parser.set_defaults(critical='-[sS]ecurity')
parser.set_defaults(pkgskeep='OK')
parser.set_defaults(pkgsdelete='OK')
parser.set_defaults(pkgsbroken='OK')
parser.set_defaults(showmaxpkgs=10)
parser.set_defaults(periodic_check=False)
parser.set_defaults(periodic_max_days=1)
parser.set_defaults(verb=0)

(opts, args) = parser.parse_args()

# Test options
if not opts.pkgskeep.upper() in RETURNMSG:
	print 'Unknown argument for --keep!'
	sys.exit(3)
else:
	opts.pkgskeep = RETURNMSG.index( opts.pkgskeep.upper() )

if not opts.pkgsdelete.upper() in RETURNMSG:
	print 'Unknown argument for --delete!'
	sys.exit(3)
else:
	opts.pkgsdelete = RETURNMSG.index( opts.pkgsdelete.upper() )

if not opts.pkgsbroken.upper() in RETURNMSG:
	print 'Unknown argument for --broken!'
	sys.exit(3)
else:
	opts.pkgsbroken = RETURNMSG.index( opts.pkgsbroken.upper() )


re_crit = [ re.compile(l) for l in [opts.critical,] ]

# Now go for the update...
try:
	cache = apt.Cache(memonly=True)
except SystemError, exc:
	print 'APT UNKNOWN - SystemError'
	print u'%s' % exc
	sys.exit(3)

cache.upgrade(dist_upgrade=opts.dist_upgrade)


# Get APT's point of view
pkgs_tobechanged = cache.get_changes()
if opts.verb >=1:
	print '>>> V1: APT wants to %supgrade %s packages' % ( opts.dist_upgrade and 'dist-' or '' ,len(pkgs_tobechanged) ) 
if opts.verb >=2:
	print '>>> V2: APT\'s upgrade: %s' % ', '.join([p.name for p in pkgs_tobechanged])

# Walk over all packages, find (new versions of installed packages) or (candidates marked for install)
pkgs_notuptodate = [p for p in cache if (p.installed and p.installed.version != p.candidate.version) or (p.candidate and p.candidate.package.marked_install)]
if opts.verb >=1:
	print '>>> V1: Cache has %s updated and new installed packages' % ( len(pkgs_notuptodate) ) 
if opts.verb >=2:
	print '>>> V2: Upgrade: %s' % ', '.join([p.name for p in pkgs_notuptodate])

# Prepare lists - fill new installs directly
u_warn = []
u_crit = []
u_unknown_and_new = []
u_unknown = []

u_keep = []
u_new = [p.name for p in cache.get_changes() if p.candidate and p.candidate.package.marked_install]
u_delete = [p.name for p in cache.get_changes() if p.marked_delete]

# Walk over APT's changes, look for candidates of installed packages and put it in u_warn/u_crit - depends on Origin-Label
# u_unknown_and_new includes new packages, clean up later
if opts.verb >=1:
	print '>>> V1: Have a look at changed packages'
for pkg in pkgs_tobechanged:
	state = None
	if pkg.installed and pkg.candidate:
		state = OK
		for pc_origin in pkg.candidate.origins:
			for rem in re_crit:
				if rem.search(pc_origin.label):
					state = max(state, CRIT)
				else:
					state = max(state, WARN)
			
	if state == CRIT:
		u_crit.append(pkg)
	elif state == WARN:
		u_warn.append(pkg)
	else:
		u_unknown_and_new.append(pkg)

	if opts.verb >=3:
		print '>>> V3: Pkg "%s", installed: %s, candidate: %s, state: %s' % (pkg.name, pkg.installed and pkg.installed.version, pkg.candidate and pkg.candidate.version, state )

# Packages which are not uptodate but APT will not upgrade are "kept"
for pkg in pkgs_notuptodate:
	if not pkg in pkgs_tobechanged:
		u_keep.append(pkg)
if opts.verb >=1:
	print '>>> V1: %s packages to keep' % ( len(u_keep) ) 
if opts.verb >=2 and len(u_keep):
	print '>>> V2: Keep: %s' % ', '.join([p.name for p in u_keep])

# Clean up unknown/new packages
for pkg in u_unknown_and_new:
	if not pkg.name in u_new:	
		u_unknown.append(pkg)
if opts.verb >=1:
	print '>>> V1: %s packages unknown' % ( len(u_unknown) ) 
if opts.verb >=2 and len(u_unknown):
	print '>>> V2: Unknown: %s' % ', '.join([p.name for p in u_unknown])



# And now for return message and code
retcode=OK
msg=[]
longmsg=[]

if len(u_unknown):
	retcode=WARN
	msg.insert(0, 'no information available: %s' % len(u_unknown) )
	pkgs = [p.name for p in u_unknown]
	pkgs.sort()
	longmsg.insert(0, 'No information available (%s): %s' % (len(u_unknown), ', '.join(pkgs) ) )

if cache.broken_count:
	msg.insert(0, 'broken packages: %s' % cache.broken_count )

if len(u_keep):
	msg.insert(0, 'kept packages: %s' % len(u_keep) )
	pkgs = [p.name for p in u_keep]
	pkgs.sort()
	longmsg.insert(0, 'Kept back (%s): %s' % (len(u_keep), ', '.join(pkgs) ) )

if len(u_delete):
	# Already list of package names
	u_delete.sort()
	msg.insert(0, 'delete: %s' % len(u_delete) )
	longmsg.insert(0, 'Delete (%s): %s' % (len(u_delete), ', '.join(u_delete) ) )

if len(u_new):
	# Already list of package names
	u_new.sort()
	msg.insert(0, 'new installs: %s' % len(u_new))
	longmsg.insert(0, 'New installs (%s): %s' % (len(u_new), ', '.join(u_new) ) )

if len(u_warn):
	retcode=WARN
	pkgs = [p.name for p in u_warn]
	pkgs.sort()
	pkglist = ''
	if opts.showmaxpkgs:
		pkglist = ', '.join(pkgs[0:10])
		if len(pkgs) > opts.showmaxpkgs:
			pkglist += ', ...'
		pkglist = ' (%s)' % pkglist
	msg.insert(0, 'other updates: %s%s' % (len(u_warn), pkglist) )
	longmsg.insert(0, 'Other updates (%s): %s' % (len(u_warn), ', '.join(pkgs) ) )

if len(u_crit):
	retcode=CRIT
	pkgs = [p.name for p in u_crit]
	pkgs.sort()
	pkglist = ''
	if opts.showmaxpkgs:
		pkglist = ', '.join(pkgs[0:10])
		if len(pkgs) > opts.showmaxpkgs:
			pkglist += ', ...'
		pkglist = ' (%s)' % pkglist
	msg.insert(0, 'security updates: %s%s' % (len(u_crit), pkglist) )
	longmsg.insert(0, 'Security updates (%s): %s' % (len(u_crit), ', '.join(pkgs) ) )


# Periodic checks
if opts.periodic_check:
	import apt_pkg

	apt_pkg.init()

	if opts.verb >= 2:
		print '>>> V2: APT::Periodic::Enable "%s"' % apt_pkg.config.get('APT::Periodic::Enable')
		print '>>> V2: APT::Periodic::Update-Package-Lists "%s"' % apt_pkg.config.get('APT::Periodic::Update-Package-Lists')

	if apt_pkg.config.has_key('APT::Periodic::Enable') and apt_pkg.config.get('APT::Periodic::Enable') == '0':
		retcode = CRIT
		msg.insert(0, 'periodic updates disabled')
		longmsg.insert(0, 'Periodic update disabled via \'APT::Periodic::Enable "0";\'')
	else:
		if apt_pkg.config.has_key('APT::Periodic::Update-Package-Lists'):
			days = apt_pkg.config.find_i('APT::Periodic::Update-Package-Lists')
			if days == 0:
				retcode = CRIT
				msg.insert(0, 'periodic updates disabled')
				longmsg.insert(0, 'Periodic update disabled via \'APT::Periodic::Update-Package-Lists "0";\' (or garbage)')
			elif days > opts.periodic_max_days:
				retcode = WARN
				msg.insert(0, 'periodic updates interval too big')
				longmsg.insert(0, 'Periodic update interval too big via \'APT::Periodic::Update-Package-Lists "%s";\'' % apt_pkg.config.get('APT::Periodic::Update-Package-Lists'))
		else:
			retcode = CRIT
			msg.insert(0, 'periodic updates disabled')
			longmsg.insert(0, 'Periodic update disabled, no \'APT::Periodic::Update-Package-Lists "X";\' found')



if retcode == OK and len(msg) == 0:
	msg = 'No updates to install'
else:
	msg = ', '.join(msg)
	msg = msg[0].upper() + msg[1:]

longmsg = '\n'.join(longmsg)

if len(u_keep):
	retcode = max(retcode, opts.pkgskeep)
if cache.delete_count:
	retcode = max(retcode, opts.pkgsdelete)
if cache.broken_count:
	retcode = max(retcode, opts.pkgsbroken)


perfdata = 'securityupdates=%s;;1;0; updates=%s;1;;0; new=%s;;;; keep=%s;;;; unknownupdates=%s;;;0; ' % ( len(u_crit), len(u_warn), len(u_new), len(u_keep), len(u_unknown), )
perfdata += 'install=%s;;;; delete=%s;;;; broken=%s;;;;' % ( cache.install_count, cache.delete_count, cache.broken_count, )

print 'APT %s - %s|%s' % (RETURNMSG[retcode], msg, perfdata, )
if longmsg:
	print longmsg
sys.exit(retcode)

# vim: se noexpandtab sw=8 ts=8 softtabstop=8

