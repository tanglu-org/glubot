###
# Copyright (c) 2008, Joerg Jaspert <joerg@debian.org>
# Copyright (c) 2008, Thomas Viehmann
# Copyright (c) 2009, Gerfried Fuchs <rhonda@debian.at>
# Copyright (c) 2014, Mehdi Dogguy <mehdi@debian.org>
# GPL v2 (not later)
###

import time
import datetime
import config
import re
from urllib2 import urlopen, URLError

import supybot.log as log
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.conf as conf

class Dak(callbacks.Plugin):
    """Little FTPMaster tools. Tells about dinstall times, warns if you have a lock set,
    and lets people set/unset locks.
    Possible commands are "lock", "unlock", "forceunlock", "locked", "setlastnew".
    """
    pass

    def __init__(self, irc):
        self.__parent = super(Dak, self)
        self.__parent.__init__(irc)
        self.irc = irc
        self.fname = "dinstallcheck"
        self.dinstallhour = [1, 7, 13, 19]
        self.dinstallmin = self.registryValue('dinstallminute')
        self.webwmlhour = [3, 7, 11, 15, 19, 23]
        self.webwmlmin = self.registryValue('webwmlminute')
        self.britneyhour = [10, 22]
        self.britneymin = self.registryValue('britneyminute')
        self.warntime=10
        self.dinstallduration=4
        self.channel = self.registryValue('channel')
        self.locks = {}

        def checktime():
            log.debug("DAK: Regular dinstall time check")

            now = datetime.datetime.utcnow()
            # figure out time (in minutes) to next and from last dinstall
            nextdinstall = None
            lastdinstall = None
            for h in self.dinstallhour:
                ndt = now.replace(hour=h, minute=self.dinstallmin)
                ldt = ndt
                if ndt < now:
                    ndt += datetime.timedelta(1)
                if ldt > now:
                    ldt -= datetime.timedelta(1)
                ndt = int((ndt-now).seconds/60)
                ldt = int((now-ldt).seconds/60)
                if nextdinstall == None or ndt < nextdinstall:
                    nextdinstall = ndt
                if lastdinstall == None or ldt < lastdinstall:
                    lastdinstall = ldt

            if lastdinstall <= self.dinstallduration:
                msgMaker = ircmsgs.privmsg
                log.debug("DAK: In Dinstall timeframe")
                # No longer time to warn only, now is time to act, if we haven't already
                if self.registryValue('dinstall') == True:
                    log.debug("DAK: Already done once, dinstall flag is %s" %(self.registryValue('dinstall')))
                    return
                log.debug("DAK: Not yet done, dinstall flag %s" % (self.registryValue('dinstall')))
                conf.supybot.plugins.Dak.get('dinstall').setValue(True)
                conf.supybot.plugins.Dak.get('warned').setValue(True)
                if self.locks.has_key("ALL"):
                    irc.queueMsg(msgMaker(self.channel, "While it is DINSTALL time, there is an ALL lock. Assuming nothing happens."))
                    irc.queueMsg(msgMaker(self.channel, "%s: Hope that is correct, Mr. \"Lets_lock_ALL_and_block_everyone.\"" % (self.locks['ALL']) ))
                    return
                irc.queueMsg(msgMaker(self.channel, "It is DINSTALL time"))
                if len(self.locks) >= 1:
                    for key in [lock for lock in self.locks if lock != 'NEW']:
                        irc.queueMsg(msgMaker(self.channel, "%s: DINSTALL time, stop working, unlocking %s" % (self.locks[key], key)))
                    map(lambda lock: self.locks.pop(lock), [lock for lock in self.locks if lock != 'NEW'])
                return
            elif nextdinstall <= self.warntime:
                # Not dinstall as far as we know, but we want to warn people if they have locks, dinstall is soon.
                # We only want to warn once about locks people have, or we would do it every 30 seconds, which wouldnt be nice.
                # Also, with warnframe larger than dinstallframe, this might warn in case the bot somehow misses dinstallframe.
                # Like if it comes up late, or so. Or?
                msgMaker = ircmsgs.privmsg
                log.debug("DAK: In Dinstall Warnframe")
                if self.registryValue('warned') == True:
                    log.debug("DAK: We already warned once, warn flag %s" % (self.registryValue('warned')))
                    return
                log.debug("DAK: Not yet warned about upcoming Dinstall run, flag is %s." % (self.registryValue('warned')))

                if len(self.locks) >= 1:
                    conf.supybot.plugins.Dak.get('warned').setValue(True)
                    for key in [lock for lock in self.locks if lock != 'NEW']:
                        log.debug("DAK: Warning %s, has %s locked." % (self.locks[key], key))
                        irc.queueMsg(msgMaker(self.channel, "%s: DINSTALL soon, hurry up" % (self.locks[key]) ))
                        if key == "ALL":
                            irc.queueMsg(msgMaker(self.channel, "%s: ALL locked. If you want to keep that, remember turning off cron" % (self.locks[key]) ))
            else: # if hour in self.dinstallhour
                # We are far outside a dinstall start
                log.debug("DAK: no dinstall close, lastdinstall: %d, nextdinstall: %d" % (lastdinstall, nextdinstall))
                conf.supybot.plugins.Dak.get('dinstall').setValue(False)
                conf.supybot.plugins.Dak.get('warned').setValue(False)

        # end def checktime
        log.info("DAK: Setting periodic scheduler for checktime")
        try:
            schedule.removePeriodicEvent(self.fname)
        except KeyError:
            pass
        schedule.addPeriodicEvent(checktime, 30, self.fname, now=False)
        schedule.addEvent(checktime, time.time()+1)
        log.info("DAK: Plugin loaded")

    def die(self):
        try:
            log.info("DAK: We should die, removing periodic scheduler")
            schedule.removePeriodicEvent(self.fname)
        except KeyError:
            pass

    def dinstall_phases(self):
        try:
            dinstall = urlopen('http://ftp-master.tanglu.org/dinstall.status', timeout=5)
        except URLError:
            log.debug("Unable to get dinstall status")
        else:
            data = dinstall.read()
            try:
                action = re.findall('Current action: (.*)', data)[0]
            except:
                log.debug("Unable to get dinstall status")
            else:
                if action.startswith('all done'):
                    pass
                elif action.startswith('postlock'):
                    pass
                else:
                    return 'Dinstall is running, %s phase' % action

    def dinstall(self, irc, msg, args):
        """takes no arguments

        Returns the time until next dinstall
        """

        def deltatime(start, stop):
            def toSeconds(timeString):
                hour, min, sec = map(int, timeString.split(':'))
                return (hour * 60 + min) * 60 + sec
            d_time_min, d_time_sec = divmod(toSeconds(stop) - toSeconds(start), 60)
            d_time_hr, d_time_min = divmod(d_time_min, 60)
            return '%dhr %dmin %ssec' % (d_time_hr % 24, d_time_min, d_time_sec)

        (year, month, day, hour, minute, second, undef, undef, undef) = time.gmtime()

        dinstall_phase = self.dinstall_phases()
        log.debug("The latest run is at %s:%s" % (self.dinstallhour[-1], self.dinstallmin))
        log.debug("I think we now have %s:%s" % (hour, minute))

        newhour = hour
        if minute >= self.dinstallmin and newhour in self.dinstallhour:
            # If we already passed dinstallminute, we are running and want the next runtime.
            log.debug("We are past this hours dinstall already")
            newhour+=1

        if newhour > self.dinstallhour[-1]:
            log.debug("We are also past the last dinstall run for today")
            # We are past the last dinstall today, so next one must be the first tomorrow, start searching at midnight
            newhour = self.dinstallhour[0]
        else:
            while newhour not in self.dinstallhour:
                newhour+=1
                log.debug("Looking at possible hour %s" % (newhour))
                if newhour > 23:
                    newhour=0

        log.debug("I found that next dinstall will be at %s:%s" % (newhour, self.dinstallmin))

        start="%s:%s:%s" % (hour, minute, second)
        stop="%s:%s:00" % (newhour, self.dinstallmin)
        difference=deltatime(start, stop)
        if dinstall_phase:
            irc.reply(dinstall_phase)
        else:
            irc.reply("I guess the next dinstall will be in %s" % (difference))
    dinstall = wrap(dinstall)

    def locked(self, irc, msg, args):
        """takes no arguments

        Returns the currently set locks
        """

        if len(self.locks) == 0:
            irc.reply("Nothing locked")
        else:
            text="Current locks: "
            for key in self.locks:
                text += "[%s, by %s] " % (key, self.locks[key])
            irc.reply(text)
    locked = wrap(locked)

    def dakinfo(self, irc, msg, what):
        """takes no arguments

        Returns a little info about this plugins status"""

        text=[]
        text.append("Dak plugin for the FTPMaster channel %s." % (self.channel))
        text.append("Dinstall hour: %s, minute: %s" % (self.dinstallhour, self.dinstallmin))
        if len(self.locks) > 1:
            text.append("Current locks: %d (%s)" % (len(self.locks), self.locks))
        text.append("Warns %d minutes before dinstall" % (self.warntime,))
        text.append("Dinstall unlocking grace interval: dinstall to dinstall+%d" % (self.dinstallduration,))
        text.append("Dinstall flag: %s, Warnflag: %s" % (conf.supybot.plugins.Dak.get('dinstall'), conf.supybot.plugins.Dak.get('warned')))
        for key in text:
            irc.reply(key)
    dakinfo = wrap(dakinfo)

    def lock(self, irc, msg, args, what):
        """<lock>

        Locks <lock>.
        """
        if self.locks.has_key("ALL"):
            irc.error("No, %s has an ALL lock" % (self.locks["ALL"]))
            return

        for key in what.split(","):
            key = key.strip()
            if key == "ALL" and len(self.locks) > 0:
                irc.error("Can't lock all, there are existing locks")
                return
            if key != "NEW":
                dinstall_phase = self.dinstall_phases()
                if dinstall_phase:
                    irc.error("Go fishing! %s" % dinstall_phase)
                    return
            if self.locks.has_key(key):
                if key == "NEW":
                    if msg.nick in self.locks[key]:
                        irc.reply("Loser, you already locked %s" % (key) )
                    else:
                        self.locks[key].append(msg.nick)
                        irc.reply("also locked %s" % (key))
                elif self.locks[key] == msg.nick:
                    irc.reply("Loser, you already locked %s" % (key) )
                else:
                    irc.reply("You suck, this is already locked by %s" % (self.locks[key]) )
            else:
                if key == "NEW":
                    self.locks[key] = []
                    self.locks[key].append(msg.nick)
                else:
                    self.locks[key]=msg.nick
                irc.reply("locked %s" % (key) )
    lock = wrap(lock, ['text'])

    def unlock(self, irc, msg, args, what):
        """[lock]

        Unlocks [lock] or everything locked from you.
        """
        if len(self.locks) == 0:
            irc.reply("Nothing locked")
            return

        unlocked="unlocked: "
        if self.locks.has_key(what):
            if what == "NEW":
                if msg.nick in self.locks[what]:
                    self.locks[what].remove(msg.nick)
                    if len(self.locks[what]) == 0:
                        del(self.locks[what])
                    irc.reply("unlocked %s" % (what))
            elif self.locks[what] == msg.nick:
                del(self.locks[what])
                irc.reply("unlocked %s" % (what) )
            else:
                irc.reply("%s is locked by %s, not by you. Not unlocked." % (what, self.locks[what]) )
        else:
            keys=[]
            for key in self.locks:
                if key == "NEW":
                    if msg.nick in self.locks[key]:
                        self.locks[key].remove(msg.nick)
                        if len(self.locks[key]) == 0:
                            keys.append(key)
                else:
                    if self.locks[key] == msg.nick:
                        keys.append(key)
            for key in keys:
                del(self.locks[key])
            unlocked += ", ".join(keys)
            irc.reply(unlocked)
    unlock = wrap(unlock, [optional('text')])

    def forceunlock(self, irc, msg, args, what):
        """<lock>

        Force-Unlocks [lock] or everything locked from you.
        """
        if len(self.locks) == 0:
            irc.reply("Nothing locked")
            return

        if self.locks.has_key(what):
            msgMaker = ircmsgs.privmsg
            irc.queueMsg(msgMaker(self.channel, "%s: Careful, %s just forceunlocked %s from you!" % (self.locks[what], msg.nick, what)))
            del(self.locks[what])
            irc.reply("unlocked %s" % (what))
    forceunlock = wrap(forceunlock, ['text'])

    def setlastnew(self, irc, msg, args):
        """

        setlastnew takes no parameter"""

        re_topic = re.compile(r"(.*)\s+\|\| last NEW ended:\s+\w{3} \d\d \d\d:\d\d UTC \d{4}(?:\s+\|\|\s+(.*))?")
        topic = irc.state.channels[self.channel].topic
        m = re_topic.match(topic)
        newtopic = ""
        if m:
            newtopic = "%s || %s" % (m.group(1),
                                     time.strftime("last NEW ended:  %b %d %H:%M UTC %Y", time.gmtime()))
            if m.group(2):
                newtopic += " || %s" % (m.group(2))
        else:
            # Woot, looks we never had this part in the topic yet
            newtopic = "%s || %s" % (topic,
                                     time.strftime("last NEW ended:  %b %d %H:%M UTC %Y", time.gmtime()))
        irc.queueMsg(ircmsgs.topic(self.channel, newtopic))
        irc.reply("Ok master")

    setlastnew = wrap(setlastnew)

    def webwml(self, irc, msg, args):
        """takes no arguments

        Returns the time until next webwml run
        """

        def deltatime(start, stop):
            def toSeconds(timeString):
                hour, min, sec = map(int, timeString.split(':'))
                return (hour * 60 + min) * 60 + sec
            d_time_min, d_time_sec = divmod(toSeconds(stop) - toSeconds(start), 60)
            d_time_hr, d_time_min = divmod(d_time_min, 60)
            return '%dhr %dmin %ssec' % (d_time_hr % 24, d_time_min, d_time_sec)

        (year, month, day, hour, minute, second, undef, undef, undef) = time.gmtime()

        log.debug("The latest run is at %s:%s" % (self.webwmlhour[-1], self.webwmlmin))
        log.debug("I think we now have %s:%s" % (hour, minute))

        newhour = hour
        if minute >= self.webwmlmin and newhour in self.webwmlhour:
            # If we already passed webwmlminute, we are running and want the next runtime.
            log.debug("We are past this hours webwml run already")
            newhour+=1

        if newhour > self.webwmlhour[-1]:
            log.debug("We are also past the last webwml run for today")
            # We are past the last webwml today, so next one must be the first tomorrow, start searching at midnight
            newhour = self.webwmlhour[0]
        else:
            while newhour not in self.webwmlhour:
                newhour+=1
                log.debug("Looking at possible hour %s" % (newhour))
                if newhour > 23:
                    newhour=0

        log.debug("I found that next webwml run will be at %s:%s" % (newhour, self.webwmlmin))

        start="%s:%s:%s" % (hour, minute, second)
        stop="%s:%s:00" % (newhour, self.webwmlmin)
        difference=deltatime(start, stop)
        irc.reply("I guess the next webwml run will be in %s" % (difference))
    webwml = wrap(webwml)

    def britney_phases(self):
        try:
            status = urlopen('http://release.debian.org/britney/britney.status', timeout=5)
        except URLError:
            log.debug("Unable to get britney status")
        else:
            data = status.read()
            if data.endswith(':\n'):
                return 'Britney is running, %s phase' % data[:-2].lower()

    def britney(self, irc, msg, args):
        """takes no arguments

        Returns the time until next britney run
        """

        def deltatime(start, stop):
            def toSeconds(timeString):
                hour, min, sec = map(int, timeString.split(':'))
                return (hour * 60 + min) * 60 + sec
            d_time_min, d_time_sec = divmod(toSeconds(stop) - toSeconds(start), 60)
            d_time_hr, d_time_min = divmod(d_time_min, 60)
            return '%dhr %dmin %ssec' % (d_time_hr % 24, d_time_min, d_time_sec)

        (year, month, day, hour, minute, second, undef, undef, undef) = time.gmtime()

        log.debug("The latest run is at %s:%s" % (self.britneyhour[-1], self.britneymin))
        log.debug("I think we now have %s:%s" % (hour, minute))

        newhour = hour
        if minute >= self.britneymin and newhour in self.britneyhour:
            # If we already passed britneyminute, we are running and want the next runtime.
            log.debug("We are past this hours britney run already")
            newhour+=1

        if newhour > self.britneyhour[-1]:
            log.debug("We are also past the last britney run for today")
            # We are past the last britney today, so next one must be the first tomorrow, start searching at midnight
            newhour = self.britneyhour[0]
        else:
            while newhour not in self.britneyhour:
                newhour+=1
                log.debug("Looking at possible hour %s" % (newhour))
                if newhour > 23:
                    newhour=0

        log.debug("I found that next britney run will be at %s:%s" % (newhour, self.britneymin))

        start="%s:%s:%s" % (hour, minute, second)
        stop="%s:%s:00" % (newhour, self.britneymin)
        difference=deltatime(start, stop)

        britney_phase = self.britney_phases()
        if britney_phase:
            irc.reply(britney_phase)
        else:
            irc.reply("I guess the next britney run will be in %s" % (difference))
    britney = wrap(britney)

Class = Dak

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
