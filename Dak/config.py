###
# Copyright (c) 2008, Joerg Jaspert <joerg@debian.org>
# GPL v2 (not later)
#
#
###

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Dak', True)


Dak = conf.registerPlugin('Dak')
# This is where your configuration variables (if any) should go.  For example:
# conf.registerGlobalValue(Dak, 'someConfigVariableName',
#     registry.Boolean(False, """Help for someConfigVariableName."""))

conf.registerGlobalValue(Dak, 'dinstall',
                         registry.Boolean(False, """Shows if we told about dinstall already"""))
conf.registerGlobalValue(Dak, 'warned',
                         registry.Boolean(False, """Shows if we warned about dinstall already"""))
conf.registerGlobalValue(Dak, 'channel',
                         registry.String('#debian-ftp', """Which channel to act in"""))
conf.registerGlobalValue(Dak, 'dinstallminute',
                         registry.NonNegativeInteger(52, """At which minute does DINSTALL start?"""))

conf.registerGlobalValue(Dak, 'webwmlminute',
                         registry.NonNegativeInteger(24, """At which minute does webwml start?"""))

conf.registerGlobalValue(Dak, 'britneyminute',
                         registry.NonNegativeInteger(0, """At which minute does britney start?"""))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
