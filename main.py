from xbmcswift2 import Plugin, ListItem
import re
import requests
import xbmc, xbmcaddon, xbmcvfs, xbmcgui
import xbmcplugin
import base64
import random
import urllib
import sqlite3
import time
import threading
import json
import os, os.path
import stat
import subprocess
from datetime import datetime, timedelta, tzinfo
#TODO strptime bug fix
import uuid
from HTMLParser import HTMLParser
import calendar
import pytz
from struct import *
from collections import namedtuple
from language import get_string as _
import chardet
import gzip



def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')


def log(v):
    xbmc.log(repr(v), xbmc.LOGERROR)


plugin = Plugin()
big_list_view = True


if plugin.get_setting("multiline") == "true":
    CR = "[CR]"
else:
    CR = ""


def get_icon_path(icon_name):
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(), icon_name)


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]", '', label)
    label = re.sub(r"\[/?COLOR.*?\]", '', label)
    return label


def escape( str ):
    str = str.replace("&", "&amp;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    str = str.replace("\"", "&quot;")
    return str


def unescape( str ):
    str = str.replace("&lt;", "<")
    str = str.replace("&gt;", ">")
    str = str.replace("&quot;", "\"")
    str = str.replace("&amp;", "&")
    return str


def delete(path):
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        xbmcvfs.delete(path+file)
    for dir in dirs:
        delete(path + dir + '/')
    xbmcvfs.rmdir(path)


@plugin.route('/play_channel/<channelname>')
def play_channel(channelname):
    channelname = channelname.decode("utf8")
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    channel = c.execute("SELECT * FROM streams WHERE name=?", (channelname, )).fetchone()
    if not channel:
        return
    uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel

    xbmc.Player().play(url)


@plugin.route('/play_channel_external/<channelname>')
def play_channel_external(channelname):
    channelname = channelname.decode("utf8")
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    channel = c.execute("SELECT * FROM streams WHERE name=?", (channelname, )).fetchone()
    if not channel:
        return
    uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel

    if url:
        cmd = [plugin.get_setting('external.player')]

        args = plugin.get_setting('external.player.args')
        if args:
            cmd.append(args)

        cmd.append(url)

        #TODO shell?
        subprocess.Popen(cmd,shell=windows())


@plugin.route('/play_external/<path>')
def play_external(path):
    cmd = [plugin.get_setting('external.player')]

    args = plugin.get_setting('external.player.args')
    if args:
        cmd.append(args)

    cmd.append(xbmc.translatePath(path))

    subprocess.Popen(cmd,shell=windows())


def xml2local(xml):
    #TODO combine
    return utc2local(xml2utc(xml))


def utc2local(utc):
    timestamp = calendar.timegm(utc.timetuple())
    local = datetime.fromtimestamp(timestamp)
    return local.replace(microsecond=utc.microsecond)


def str2dt(string_date):
    format ='%Y-%m-%d %H:%M:%S'
    try:
        res = datetime.strptime(string_date, format)
    except TypeError:
        res = datetime(*(time.strptime(string_date, format)[0:6]))
    return utc2local(res)


def total_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


@plugin.route('/jobs')
def jobs():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    jobs = cursor.execute("SELECT * FROM jobs ORDER by channelname, start").fetchall()

    items = []

    for uid, uuid, channelid, channelname, title, start, stop, type in jobs:

        context_items = []

        context_items.append((_("Delete Job"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job, job=uuid))))
        context_items.append((_("Delete All Jobs"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_jobs))))

        label = "%s [COLOR yellow]%s[/COLOR] %s[COLOR grey]%s - %s[/COLOR] %s" % (channelname, title, CR, utc2local(start), utc2local(stop), type)

        items.append({
            'label': label,
            'path': plugin.url_for(delete_job, job=uuid),
            'context_menu': context_items,
            'thumbnail':get_icon_path('recordings'),
        })

    return items


@plugin.route('/rules')
def rules():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rules = cursor.execute('SELECT uid, channelid, channelname, title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", description, type FROM rules ORDER by channelname, title, start, stop').fetchall()

    items = []

    for uid, channelid, channelname, title, start, stop, description, type  in rules:

        context_items = []
        context_items.append((_("Delete Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_rule, uid=uid))))
        context_items.append((_("Delete All Rules"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_rules))))

        if type.startswith("WATCH"):
            type = type.replace("WATCH ","")
            type_label = "WATCH"
        elif type.startswith("REMIND"):
            type = type.replace("REMIND ","")
            type_label = "REMIND"
        else:
            type_label = "RECORD"

        label = "TODO"
        if type == "ALWAYS":
            label = "%s [COLOR yellow]%s[/COLOR] %s" % (channelname, title, type_label)
        elif type == "DAILY":
            label =  "%s [COLOR yellow]%s[/COLOR] %s[COLOR grey]%s - %s[/COLOR] %s" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time(), type_label)
        elif type == "SEARCH":
            label = "%s [COLOR yellow]%s[/COLOR] %s" % (channelname, title, type_label)
        elif type == "PLOT":
            label = "%s [COLOR yellow](%s)[/COLOR] %s" % (channelname, description, type_label)

        items.append({
            'label': label,
            'path': plugin.url_for(delete_rule, uid=uid),
            'context_menu': context_items,
            'thumbnail':get_icon_path('recordings'),
        })

    return items


@plugin.route('/delete_all_rules')
def delete_all_rules(ask=True):
    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder", _("Delete All Rules?"))):
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    conn.execute("DELETE FROM rules")

    conn.commit()
    conn.close()

    refresh()


@plugin.route('/delete_rule/<uid>')
def delete_rule(uid, ask=True):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder", _("Cancel Record?"))):
        return

    conn.execute("DELETE FROM rules WHERE uid=?", (uid, ))

    conn.commit()
    conn.close()

    refresh()


@plugin.route('/delete_all_jobs')
def delete_all_jobs(ask=True):
    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder", _("Delete All Jobs?"))):
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    conn.execute("DELETE FROM jobs")

    conn.commit()
    conn.close()

    refresh()


@plugin.route('/delete_job/<job>')
def delete_job(job, kill=True, ask=True):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    job_details = cursor.execute("SELECT * FROM jobs WHERE uuid=?", (job, )).fetchone()
    if not job_details:
        return

    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder", _("Cancel Record?"))):
        return

    if windows() and plugin.get_setting('task.scheduler') == 'true':
        cmd = ["schtasks", "/delete", "/f", "/tn", job]
        subprocess.Popen(cmd, shell=True)
    else:
        xbmc.executebuiltin('CancelAlarm(%s, True)' % job)

    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    pyjob = directory + job + ".py"

    pid = xbmcvfs.File(pyjob+'.pid').read()
    if pid and kill:
        if windows():
            subprocess.Popen(["taskkill", "/im", pid], shell=True)
        else:
            #TODO correct kill switch
            subprocess.Popen(["kill", "-9", pid])

    xbmcvfs.delete(pyjob)
    xbmcvfs.delete(pyjob+'.pid')

    conn.execute("DELETE FROM jobs WHERE uuid=?", (job, ))
    conn.commit()
    conn.close()

    refresh()


def windows():
    if os.name == 'nt':
        return True
    else:
        return False


def android_get_current_appid():
    with open("/proc/%d/cmdline" % os.getpid()) as fp:
        return fp.read().rstrip("\0")


def ffmpeg_location():
    ffmpeg_src = xbmc.translatePath(plugin.get_setting('ffmpeg'))

    if xbmc.getCondVisibility('system.platform.android'):
        ffmpeg_dst = '/data/data/%s/ffmpeg' % android_get_current_appid()

        if not xbmcvfs.exists(ffmpeg_dst) and ffmpeg_src != ffmpeg_dst:
            xbmcvfs.copy(ffmpeg_src, ffmpeg_dst)

        ffmpeg = ffmpeg_dst
    else:
        ffmpeg = ffmpeg_src

    if ffmpeg:
        try:
            st = os.stat(ffmpeg)
            if not (st.st_mode & stat.S_IXUSR):
                try:
                    os.chmod(ffmpeg, st.st_mode | stat.S_IXUSR)
                except:
                    pass
        except:
            pass
    if xbmcvfs.exists(ffmpeg):
        return ffmpeg
    else:
        xbmcgui.Dialog().notification("IPTV Recorder", _("ffmpeg exe not found!"))


@plugin.route('/record_once/<programmeid>')
def record_once(programmeid, do_refresh=True, watch=False, remind=False):
    threading.Thread(target=record_once_thread,args=[programmeid, do_refresh, watch, remind]).start()


@plugin.route('/watch_once/<programmeid>')
def watch_once(programmeid, do_refresh=True, watch=True, remind=False):
    threading.Thread(target=record_once_thread,args=[programmeid, do_refresh, watch, remind]).start()


@plugin.route('/remind_once/<programmeid>')
def remind_once(programmeid, do_refresh=True, watch=False, remind=True):
    threading.Thread(target=record_once_thread,args=[programmeid, do_refresh, watch, remind]).start()


def record_once_thread(programmeid, do_refresh=True, watch=False, remind=False):
    #TODO check for ffmpeg process already recording if job is re-added

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programme = cursor.execute('SELECT channelid, title, sub_title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date, description, episode, categories FROM programmes WHERE uid=? LIMIT 1', (programmeid, )).fetchone()
    channelid, title, sub_title, start, stop, date, description, episode, categories = programme

    nfo = {"programme":{"channelid":channelid, "title":title, "sub_title":sub_title, "start":datetime2timestamp(start), "stop":datetime2timestamp(stop), "date":date, "description":description, "episode":episode, "categories":categories}}

    channel = cursor.execute("SELECT * FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
    if not channel:
        channel = cursor.execute("SELECT * FROM channels WHERE id=?", (channelid, )).fetchone()
        uid, tvg_id, name, tvg_logo = channel
        url = ""
    else:
        uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel
    thumbnail = tvg_logo
    channelname = name
    nfo["channel"] = {"channelname":channelname, "thumbnail":thumbnail, "channelid":tvg_id}

    if not url:
        xbmc.log("No url for %s" % channelname, xbmc.LOGERROR)
        return

    url_headers = url.split('|', 1)
    url = url_headers[0]
    headers = {}
    if len(url_headers) == 2:
        sheaders = url_headers[1]
        aheaders = sheaders.split('&')
        if aheaders:
            for h in aheaders:
                k, v = h.split('=', 1)
                headers[k] = v

    local_starttime = utc2local(start)
    local_endtime = utc2local(stop)

    ftitle = sane_name(title)
    if sub_title:
        fsub_title = sane_name(sub_title)
    fchannelname = sane_name(channelname)

    folder = ""
    movie = False
    series = False
    if episode:
        if episode == "MOVIE":
            movie = True
            if date and len(date) == 4:
                filename = "%s (%s)" % (ftitle, date)
                folder = "%s (%s) - %s - %s" % (ftitle, date, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
            else:
                folder = ftitle
                filename = "%s - %s - %s" % (ftitle, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
        else:
            series = True
            folder = ftitle
            filename = "%s %s - %s - %s" % (ftitle, episode, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
    else:
        if sub_title:
            filename = "%s %s - %s - %s" % (ftitle, fsub_title, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
        else:
            filename = "%s - %s - %s" % (ftitle, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))

    if watch:
        type = "WATCH"
    elif remind:
        type = "REMIND"
    else:
        type = "RECORD"

    job = cursor.execute("SELECT * FROM jobs WHERE channelid=? AND start=? AND stop=? AND type=?", (channelid, start, stop, type)).fetchone()
    if job:
        return

    before = int(plugin.get_setting('minutes.before') or "0")
    after = int(plugin.get_setting('minutes.after') or "0")
    local_starttime = local_starttime - timedelta(minutes=before)
    local_endtime = local_endtime + timedelta(minutes=after)

    now = datetime.now()
    if (local_starttime < now) and (local_endtime > now):
        local_starttime = now
        immediate = True
    else:
        immediate = False

    length = local_endtime - local_starttime
    seconds = total_seconds(length)

    if series:
        dir = os.path.join(xbmc.translatePath(plugin.get_setting('recordings')), "TV", folder)
    elif movie:
        dir = os.path.join(xbmc.translatePath(plugin.get_setting('recordings')), "Movies", folder)
    else:
        dir = os.path.join(xbmc.translatePath(plugin.get_setting('recordings')), "Other", folder)
    xbmcvfs.mkdirs(dir)
    path = os.path.join(dir, filename)
    json_path = path + '.json'
    path = path + '.ts'
    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return

    json_nfo = json.dumps(nfo)
    f = xbmcvfs.File(json_path,'w')
    f.write(json_nfo)
    f.close()

    cmd = [ffmpeg]
    for h in headers:
        cmd.append("-headers")
        cmd.append("%s:%s" % (h, headers[h]))
    cmd.append("-i")
    cmd.append(url)
    probe_cmd = cmd

    cmd = probe_cmd + ["-y", "-t", str(seconds), "-c", "copy", path.encode('utf8')]

    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    job = str(uuid.uuid1())
    pyjob = directory + job + ".py"

    f = xbmcvfs.File(pyjob, 'wb')
    f.write("import os, subprocess, time\n")

    if watch == False and remind == False:
        f.write("cmd = %s\n" % repr(cmd))
        f.write("for trial in range(2):\n")
        f.write("  p = subprocess.Popen(cmd, shell=%s)\n" % windows())
        f.write("  f = open(r'%s', 'w+')\n" % xbmc.translatePath(pyjob+'.pid'))
        f.write("  f.write(repr(p.pid))\n")
        f.write("  f.close()\n")
        f.write("  result = p.wait()\n")
        f.write("  time.sleep(1)\n")
        f.write("  if result == 0 or os.path.exists(r'%s') == False:\n" % xbmc.translatePath(pyjob))
        f.write("    break\n")
        f.write("  time.sleep(5)\n")
        #TODO copy file somewhere else
    elif remind == True:
        cmd = 'xbmcgui.Dialog().notification("%s", "%s", sound=%s)\n' % (channelname, title, plugin.get_setting('silent')=="false")
        f.write("import xbmc, xbmcgui\n")
        f.write("%s\n" % cmd.encode("utf8"))
    else:
        if (plugin.get_setting('external.player.watch') == 'true') or (windows() and (plugin.get_setting('task.scheduler') == 'true')):
            cmd = [plugin.get_setting('external.player'), plugin.get_setting('external.player.args'), url]
            f.write("cmd = %s\n" % repr(cmd))
            f.write("p = subprocess.Popen(cmd, shell=%s)\n" % windows())
        else:
            cmd = 'xbmc.Player().play("%s")\n' % url
            f.write("import xbmc\n")
            f.write("%s\n" % cmd.encode("utf8"))
    f.close()

    if windows() and (plugin.get_setting('task.scheduler') == 'true'):
        if immediate:
            cmd = 'RunScript(%s)' % (pyjob)
            xbmc.executebuiltin(cmd)
        else:
            st = "%02d:%02d" % (local_starttime.hour, local_starttime.minute)
            sd = "%02d/%02d/%04d" % (local_starttime.day, local_starttime.month, local_starttime.year)
            cmd = ["schtasks", "/create", "/f", "/tn", job, "/sc", "once", "/st", st, "/sd", sd, "/tr", "%s %s" % (xbmc.translatePath(plugin.get_setting('python')), xbmc.translatePath(pyjob))]
            subprocess.Popen(cmd, shell=True)
    else:
        now = datetime.now()
        diff = local_starttime - now
        minutes = ((diff.days * 86400) + diff.seconds) / 60
        #minutes = 1
        if minutes < 1:
            if local_endtime > now:
                cmd = 'RunScript(%s)' % (pyjob)
                xbmc.executebuiltin(cmd)
            else:
                xbmcvfs.delete(pyjob)
                return
        else:
            cmd = 'AlarmClock(%s, RunScript(%s), %d, True)' % (job, pyjob, minutes)
            xbmc.executebuiltin(cmd)

    conn.execute("INSERT OR REPLACE INTO jobs(uuid, channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?, ?)",
    [job, channelid, channelname, title, start, stop, type])
    conn.commit()
    conn.close()

    if do_refresh:
        refresh()

def sane_name(name):
    if windows():
        name = urllib.quote(name.encode("utf8"))
        name = name.replace("%20",' ')
    else:
        quote = {'"': '%22', '|': '%7C', '*': '%2A', '/': '/', '<': '%3C', ':': '%3A', '\\': '%5C', '?': '%3F', '>': '%3E'}
        for char in quote:
            name = name.replace(char, quote[char])
    return name

def refresh():
    containerAddonName = xbmc.getInfoLabel('Container.PluginName')
    AddonName = xbmcaddon.Addon().getAddonInfo('id')
    if (containerAddonName == AddonName) and (plugin.get_setting('refresh') == 'true') :
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/record_daily/<channelid>/<channelname>/<title>/<start>/<stop>')
def record_daily(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title)

    start = timestamp2datetime(float(start))
    stop = timestamp2datetime(float(stop))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND start=? AND stop =? AND type=?', (channelid, channelname, title, start, stop, "DAILY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, title, start, stop, "DAILY"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always/<channelid>/<channelname>/<title>')
def record_always(channelid, channelname, title):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title)

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND type=?', (channelid, channelname, title, "ALWAYS")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, title, "ALWAYS"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always_search/<channelid>/<channelname>')
def record_always_search(channelid, channelname):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    title = xbmcgui.Dialog().input("IPTV Recorder: " + _("Title Search (% is wildcard)?"))
    if not title:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND type=?', (channelid, channelname, title, "SEARCH")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, title, "SEARCH"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always_search_plot/<channelid>/<channelname>')
def record_always_search_plot(channelid, channelname):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    description = xbmcgui.Dialog().input("IPTV Recorder: " + _("Plot Search (% is wildcard)?"))
    if not description:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND description=? AND type=?', (channelid, channelname, description, "PLOT")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, description, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, description, "PLOT"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/watch_daily/<channelid>/<channelname>/<title>/<start>/<stop>')
def watch_daily(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title)

    start = timestamp2datetime(float(start))
    stop = timestamp2datetime(float(stop))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND start=? AND stop =? AND type=?', (channelid, channelname, title, start, stop, "WATCH DAILY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, title, start, stop, "WATCH DAILY"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/watch_always/<channelid>/<channelname>/<title>')
def watch_always(channelid, channelname, title):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title)

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND type=?', (channelid, channelname, title, "WATCH ALWAYS")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, title, "WATCH ALWAYS"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/watch_always_search/<channelid>/<channelname>')
def watch_always_search(channelid, channelname):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    title = xbmcgui.Dialog().input("IPTV watcher: " + _("Title Search (% is wildcard)?"))
    if not title:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND type=?', (channelid, channelname, title, "WATCH SEARCH")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, title, "WATCH SEARCH"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/watch_always_search_plot/<channelid>/<channelname>')
def watch_always_search_plot(channelid, channelname):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    description = xbmcgui.Dialog().input("IPTV watcher: " + _("Plot Search (% is wildcard)?"))
    if not description:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND description=? AND type=?', (channelid, channelname, description, "WATCH PLOT")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, description, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, description, "WATCH PLOT"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/remind_daily/<channelid>/<channelname>/<title>/<start>/<stop>')
def remind_daily(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title)

    start = timestamp2datetime(float(start))
    stop = timestamp2datetime(float(stop))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND start=? AND stop =? AND type=?', (channelid, channelname, title, start, stop, "REMIND DAILY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, title, start, stop, "REMIND DAILY"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/remind_always/<channelid>/<channelname>/<title>')
def remind_always(channelid, channelname, title):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title)

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND type=?', (channelid, channelname, title, "REMIND ALWAYS")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, title, "REMIND ALWAYS"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/remind_always_search/<channelid>/<channelname>')
def remind_always_search(channelid, channelname):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    title = xbmcgui.Dialog().input("IPTV reminder: " + _("Title Search (% is wildcard)?"))
    if not title:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND type=?', (channelid, channelname, title, "REMIND SEARCH")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, title, "REMIND SEARCH"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/remind_always_search_plot/<channelid>/<channelname>')
def remind_always_search_plot(channelid, channelname):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    description = xbmcgui.Dialog().input("IPTV reminder: " + _("Plot Search (% is wildcard)?"))
    if not description:
        return

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND description=? AND type=?', (channelid, channelname, description, "REMIND PLOT")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, description, type) VALUES(?, ?, ?, ?)",
        [channelid, channelname, description, "REMIND PLOT"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/broadcast/<programmeid>')
def broadcast(programmeid):

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programme = cursor.execute('SELECT channelid, title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]" FROM programmes WHERE uid=? LIMIT 1', (programmeid, )).fetchone()
    channelid, title, start, stop = programme

    channel = cursor.execute("SELECT * FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
    if not channel:
        channel = cursor.execute("SELECT * FROM channels WHERE id=?", (channelid, )).fetchone()
        uid, tvg_id, name, tvg_logo = channel
        url = ""
    else:
        uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel
    thumbnail = tvg_logo
    channelname = name

    echannelid = channelid.encode("utf8")
    echannelname = channelname.encode("utf8")
    etitle = title.encode("utf8")

    items = []

    items.append({
        'label': _("Record Once") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start), utc2local(stop)),
        'path': plugin.url_for(record_once, programmeid=programmeid),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Record Always") + " - %s - %s" % (channelname, title),
        'path': plugin.url_for(record_always, channelid=echannelid, channelname=echannelname, title=etitle),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    start_ts = datetime2timestamp(start)
    stop_ts = datetime2timestamp(stop)
    items.append({
        'label': _("Record Daily") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time()),
        'path': plugin.url_for(record_daily, channelid=echannelid, channelname=echannelname, title=etitle, start=start_ts, stop=stop_ts),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Watch Once") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start), utc2local(stop)),
        'path': plugin.url_for(watch_once, programmeid=programmeid),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Watch Always") + " - %s - %s" % (channelname, title),
        'path': plugin.url_for(watch_always, channelid=echannelid, channelname=echannelname, title=etitle),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    start_ts = datetime2timestamp(start)
    stop_ts = datetime2timestamp(stop)
    items.append({
        'label': _("Watch Daily") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time()),
        'path': plugin.url_for(watch_daily, channelid=echannelid, channelname=echannelname, title=etitle, start=start_ts, stop=stop_ts),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Remind Once") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start), utc2local(stop)),
        'path': plugin.url_for(remind_once, programmeid=programmeid),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Remind Always") + " - %s - %s" % (channelname, title),
        'path': plugin.url_for(remind_always, channelid=echannelid, channelname=echannelname, title=etitle),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    start_ts = datetime2timestamp(start)
    stop_ts = datetime2timestamp(stop)
    items.append({
        'label': _("Remind Daily") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time()),
        'path': plugin.url_for(remind_daily, channelid=echannelid, channelname=echannelname, title=etitle, start=start_ts, stop=stop_ts),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Play Channel") + " - %s" % (channelname),
        'path': plugin.url_for(play_channel, channelname=echannelname),
        'thumbnail': thumbnail or get_icon_path('tv'),
    })

    if plugin.get_setting('external.player'):
        items.append({
            'label': _("Play Channel External") + " - %s" % (channelname),
            'path': plugin.url_for(play_channel_external, channelname=echannelname),
            'thumbnail': thumbnail or get_icon_path('tv'),
        })

    #TODO Watch Timers

    return items


def datetime2timestamp(dt):
    epoch=datetime.fromtimestamp(0.0)
    td = dt - epoch
    return (td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**6


def timestamp2datetime(ts):
    return datetime.fromtimestamp(ts)


def time2str(t):
    return "%02d:%02d" % (t.hour,t.minute)


def str2time(s):
    return datetime.time(hour=int(s[0:1],minute=int(s[3:4])))


def day(timestamp):
    if timestamp:
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        if today.date() == timestamp.date():
            return _('Today')
        elif tomorrow.date() == timestamp.date():
            return _('Tomorrow')
        elif yesterday.date() == timestamp.date():
            return _('Yesterday')
        else:
            return _(timestamp.strftime("%A"))


@plugin.route('/delete_search_title/<title>')
def delete_search_title(title):
    title = title.decode("utf8")

    searches = plugin.get_storage('search_title')
    if title in searches:
        del searches[title]
    refresh()


@plugin.route('/search_title_dialog')
def search_title_dialog():
    searches = plugin.get_storage('search_title')

    items = []
    items.append({
        "label": "New",
        "path": plugin.url_for('search_title_input', title='title'),
        "thumbnail": get_icon_path('search'),
    })

    for search in searches:
        context_items = []
        context_items.append((_("Delete Search"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_title, title=search))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_title', title=search),
            "thumbnail": get_icon_path('search'),
            'context_menu': context_items,
            })
    return items


@plugin.route('/search_title_input/<title>')
def search_title_input(title):
    searches = plugin.get_storage('search_title')
    if title == "title":
        title = ""
    d = xbmcgui.Dialog()
    what = d.input(_("Search Title"), title)
    if not what:
        return
    searches[what] = ''
    return search_title(what)


@plugin.route('/search_title/<title>')
def search_title(title):
    title = title.decode("utf8")

    if plugin.get_setting('add.context.searches') == 'true':
        searches = plugin.get_storage('search_title')
        searches[title] = ''

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title LIKE ? ORDER BY start, stop, channelid',
    ("%"+title+"%", )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/delete_search_plot/<plot>')
def delete_search_plot(plot):
    plot = plot.decode("utf8")

    searches = plugin.get_storage('search_plot')
    if plot in searches:
        del searches[plot]
    refresh()


@plugin.route('/search_plot_dialog')
def search_plot_dialog():
    searches = plugin.get_storage('search_plot')

    items = []
    items.append({
        "label": _("New"),
        "path": plugin.url_for('search_plot_input', plot='plot'),
        "thumbnail": get_icon_path('search'),
    })

    for search in searches:
        context_items = []
        context_items.append(("Delete Search" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_plot, plot=search))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_plot', plot=search),
            "thumbnail": get_icon_path('search'),
            'context_menu': context_items,
            })
    return items


@plugin.route('/search_plot_input/<plot>')
def search_plot_input(plot):
    plot = plot.decode("utf8")
    searches = plugin.get_storage('search_plot')
    if plot == "plot":
        plot = ""
    d = xbmcgui.Dialog()
    what = d.input(_("Search Plot"), plot)
    if not what:
        return
    searches[what] = ''
    return search_plot(what)


@plugin.route('/search_plot/<plot>')
def search_plot(plot):
    plot = plot.decode("utf8")

    #TODO combine with search_title() and group()
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE description LIKE ? ORDER BY start, stop, channelid',
    ("%"+plot+"%", )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/delete_search_categories/<categories>')
def delete_search_categories(categories):
    categories = categories.decode("utf8")

    searches = plugin.get_storage('search_categories')
    if categories in searches:
        del searches[categories]
    refresh()


@plugin.route('/search_categories_dialog')
def search_categories_dialog():
    searches = plugin.get_storage('search_categories')

    items = []
    items.append({
        "label": _("New"),
        "path": plugin.url_for('search_categories_input', categories='categories'),
        "thumbnail": get_icon_path('search'),
    })

    for search in searches:
        context_items = []
        context_items.append(("Delete Search" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_categories, categories=search.encode("utf8")))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_categories', categories=search.encode("utf8")),
            "thumbnail": get_icon_path('search'),
            'context_menu': context_items,
            })
    return items


@plugin.route('/search_categories_input/<categories>')
def search_categories_input(categories):
    categories = categories.decode("utf8")
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute('SELECT DISTINCT categories FROM programmes').fetchall()

    cats = set()
    for programme in programmes:
        programme_categories = programme[0]
        cats.add(programme_categories)
        programme_categories = programme_categories.split(', ')
        for category in programme_categories:
            if category:
                cats.add(category)
    cats = sorted(list(cats))

    searches = plugin.get_storage('search_categories')
    if categories == "categories":
        categories = ""
    d = xbmcgui.Dialog()
    what = d.select(_("Search categories"), cats)
    if not what:
        return
    what = cats[what]
    what = what.strip()
    searches[what] = ''
    return search_categories(what)


@plugin.route('/search_categories/<categories>')
def search_categories(categories):
    categories = categories.decode("utf8")

    if plugin.get_setting('add.context.searches') == 'true':
        searches = plugin.get_storage('search_categories')
        searches[categories] = ''

    #TODO combine with search_title() and group()
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE categories LIKE ? ORDER BY start, stop, channelid',
    ("%"+categories+"%", )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/channel/<channelid>')
def channel(channelid):
    channelid = channelid.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    channel = cursor.execute("SELECT * FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
    if not channel:
        channel = cursor.execute("SELECT * FROM channels WHERE id=?", (channelid, )).fetchone()
        uid, tvg_id, name, tvg_logo = channel
        url = ""
    else:
        uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel
    thumbnail = tvg_logo
    channelname = name

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE channelid=?', (channelid, )).fetchall()

    conn.commit()
    conn.close()

    if plugin.get_setting('add.favourite.channel') == 'true':
        add_favourite_channel(channelname, channelid, thumbnail)

    return listing(programmes, scroll=True)


@plugin.route('/tv_show/<title>')
def tv_show(title):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=?', (title, )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/other/<title>')
def other(title):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=?', (title, )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/category/<title>')
def category(title):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE categories LIKE ?', ("%"+title+"%", )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/movie/<title>/<date>')
def movie(title, date):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    if date != "None":
        programmes = cursor.execute(
        'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=? AND date=?', (title, date)).fetchall()
    else:
        programmes = cursor.execute(
        'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=?', (title, )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


def listing(programmes, scroll=False):
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    streams = cursor.execute("SELECT * FROM streams").fetchall()
    streams = {x[3]:x for x in streams}
    channels = cursor.execute("SELECT * FROM channels").fetchall()
    channels = {x[1]:x for x in channels}

    items = []

    now = datetime.now()

    current = None

    i = 1
    for p in programmes:
        uid, channelid , title , sub_title , start , stop , date , description , episode, categories = p

        stream = streams.get(channelid) #cursor.execute("SELECT * FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
        channel = channels.get(channelid)
        if stream:
            cuid, channelname, tvg_name, tvg_id, tvg_logo, groups, url = stream
            thumbnail = tvg_logo
        elif channel:
            uid, tvg_id, channelname, tvg_logo = channel
            url = ""
            thumbnail = tvg_logo
        else:
            continue


        jobs = cursor.execute("SELECT uuid, type FROM jobs WHERE channelid=? AND start=? AND stop=?", (channelid, start, stop)).fetchall()
        if jobs:
            types = []
            for uuid, type in jobs:
                types.append(type)
            recording = "[COLOR red]%s[/COLOR]" % ', '.join(types)
        else:
            recording = ""

        starttime = utc2local(start)
        endtime = utc2local(stop)

        if plugin.get_setting('show.categories') == 'true':
            categories_label = "[COLOR grey]%s[/COLOR]" % categories
        else:
            categories_label = ""

        if endtime < now:
            color = "orange"
            if plugin.get_setting('show.finished') == 'false':
                continue
        else:
            if current == None:
                current = i
            color = "yellow"
        i += 1

        if sub_title:
            stitle = "[COLOR %s]%s[/COLOR] [COLOR grey]- %s[/COLOR]" % (color, title, sub_title)
        else:
            stitle = "[COLOR %s]%s[/COLOR]" % (color, title)

        if (plugin.get_setting('hide.channel.name') == "true") and thumbnail:
            channelname_label = ""
        else:
            channelname_label = channelname

        label = "%02d:%02d [COLOR grey]%s[/COLOR] %s %s %s%s %s" % (starttime.hour, starttime.minute, day(starttime), channelname_label, categories_label, CR, stitle, recording)

        context_items = []

        echannelid = channelid.encode("utf8")
        echannelname=channelname.encode("utf8")
        etitle=title.encode("utf8")
        ecategories=categories.encode("utf8")

        if recording:
            for uuid, type in jobs:
                if type == "RECORD":
                    message = _("Cancel Record")
                elif type == "REMIND":
                    message = _("Cancel Remind")
                elif type == "WATCH":
                    message = _("Cancel Watch")
                context_items.append((message, 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job, job=uuid))))
        else:
            if url:
                context_items.append((_("Record Once"), 'XBMC.RunPlugin(%s)' %
                (plugin.url_for(record_once, programmeid=uid))))

        if url:
            context_items.append((_("Play Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel, channelname=echannelname))))
            if plugin.get_setting('external.player'):
                context_items.append((_("Play Channel External"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external, channelname=echannelname))))

        context_items.append((echannelname, 'ActivateWindow(%s,%s,return)' % (xbmcgui.getCurrentWindowId(), plugin.url_for('channel', channelid=echannelid))))
        context_items.append((etitle, 'ActivateWindow(%s,%s,return)' % (xbmcgui.getCurrentWindowId(), plugin.url_for('search_title', title=etitle))))
        if ecategories:
            context_items.append((ecategories, 'ActivateWindow(%s,%s,return)' % (xbmcgui.getCurrentWindowId(), plugin.url_for('search_categories', categories=ecategories))))

        if url:
            path = plugin.url_for(broadcast, programmeid=uid)
        else:
            path = plugin.url_for('channel', channelid=echannelid)

        dictitem = {
            'label': label,
            'path': path,
            'thumbnail': thumbnail,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": title, "plot":description, "genre":categories}
        }
        listitem = ListItem().from_dict(**dictitem)
        #TODO which one is Krypton Estuary widelist thumbnail?
        #listitem._listitem.setArt({"icon": thumbnail, "landscape": thumbnail, "clearart": thumbnail, "clearlogo": thumbnail, "thumb": thumbnail, "poster": thumbnail, "banner": thumbnail, "fanart":thumbnail})
        items.append(listitem)

    conn.commit()
    conn.close()

    if scroll and plugin.get_setting('scroll.now') == 'true':
        threading.Thread(target=focus,args=[current]).start()

    return items


def focus(i):

    #TODO find way to check this has worked (clist.getSelectedPosition returns -1)
    xbmc.sleep(int(plugin.get_setting('scroll.ms') or "0"))
    #TODO deal with hidden ..
    win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    cid = win.getFocusId()
    if cid:
        clist = win.getControl(cid)
        if clist:
            try: clist.selectItem(i)
            except: pass


@plugin.route('/remove_favourite_channel/<channelname>')
def remove_favourite_channel(channelname):
    channelname = channelname.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))

    conn.execute("DELETE FROM favourites WHERE channelname=?", (channelname, ))

    conn.commit()
    conn.close()

    refresh()


@plugin.route('/add_favourite_channel/<channelname>/<channelid>/<thumbnail>')
def add_favourite_channel(channelname, channelid, thumbnail):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))

    conn.execute("INSERT OR REPLACE INTO favourites(channelname, channelid, logo) VALUES(?, ?, ?)",
    [channelname, channelid, thumbnail])

    conn.commit()
    conn.close()

    refresh()


@plugin.route('/favourite_channels')
def favourite_channels():
    return group(section="FAVOURITES")


@plugin.route('/epg')
def epg():
    return group(section="EPG")


@plugin.route('/group/<channelgroup>')
def group(channelgroup=None,section=None):
    if channelgroup:
        channelgroup=channelgroup.decode("utf8")

    show_now_next = False

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    logos = {}
    if section == "EPG":
        channels = cursor.execute("SELECT * FROM channels ORDER BY name").fetchall()
        streams = cursor.execute("SELECT tvg_id, tvg_logo FROM streams").fetchall()
        logos = {x[0]:x[1] for x in streams}
        collection = channels
        show_now_next = plugin.get_setting('show.now.next.all') == "true"
    elif section == "FAVOURITES":
        favourite_channels = cursor.execute("SELECT * FROM favourites ORDER BY channelname").fetchall()
        collection = favourite_channels
        show_now_next = plugin.get_setting('show.now.next.favourites') == "true"
    else:
        if channelgroup == "All Channels":
            streams = cursor.execute("SELECT * FROM streams ORDER BY name").fetchall()
            channels = cursor.execute("SELECT * FROM channels ORDER BY name").fetchall()
            show_now_next = plugin.get_setting('show.now.next.all') == "true"
        else:
            streams = cursor.execute("SELECT * FROM streams WHERE groups=? ORDER BY name", (channelgroup, )).fetchall()
            show_now_next = plugin.get_setting('show.now.next.lists') == "true"
        collection = streams

    favourites = cursor.execute("SELECT channelname FROM favourites").fetchall()
    favourites = [x[0] for x in favourites]

    items = []

    now = datetime.utcnow()

    if show_now_next:
        now_titles = cursor.execute('SELECT channelid, title, start AS "start [TIMESTAMP]", description, categories FROM programmes WHERE start<? AND stop>?', (now, now)).fetchall()
        now_titles = {x[0]:(x[1],x[2],x[3],x[4]) for x in now_titles}
        #TODO limit to one per channelid
        next_titles = cursor.execute('SELECT channelid, title, start AS "start [TIMESTAMP]", categories FROM programmes WHERE start>? ORDER BY start DESC', (now,)).fetchall()
        next_titles = {x[0]:(x[1],x[2],x[3]) for x in next_titles}

    for stream_channel in collection:

        if section == "EPG":
            uid, id, name, icon = stream_channel
            channelname = name
            channelid = id
            thumbnail = logos.get(channelid) or icon or get_icon_path('tv')
            logo = icon
        elif section == "FAVOURITES":
            channelname, channelid, thumbnail = stream_channel
            logo = thumbnail
        else:
            uid, name, tvg_name, tvg_id, tvg_logo, groups, url = stream_channel
            channelname = name
            channelid = tvg_id
            if not channelid:
                continue
            thumbnail = tvg_logo or get_icon_path('tv')
            logo = tvg_logo

        description = ""
        categories = ""

        if show_now_next:

            if channelid in now_titles:
                title = now_titles[channelid][0]
                local_start = utc2local(now_titles[channelid][1])
                description = now_titles[channelid][2]
                if plugin.get_setting('show.categories') == 'true':
                    categories = "[COLOR grey]%s[/COLOR]" % now_titles[channelid][3]
                else:
                    categories = ""
                now_title = "[COLOR yellow]%02d:%02d %s[/COLOR] %s" % (local_start.hour, local_start.minute, title, categories)
            else:
                now_title = ""

            if channelid in next_titles:
                title = next_titles[channelid][0]
                local_start = utc2local(next_titles[channelid][1])
                if plugin.get_setting('show.categories') == 'true':
                    next_categories = "[COLOR grey]%s[/COLOR]" % next_titles[channelid][2]
                else:
                    next_categories = ""
                next_title =  "[COLOR blue]%02d:%02d %s[/COLOR] %s" % (local_start.hour, local_start.minute, title, next_categories)
            else:
                next_title = ""

            if (plugin.get_setting('hide.channel.name') == "true") and logo:
                label = "%s %s%s" % (now_title, CR, next_title)
            else:
                label = "%s %s %s%s" % (channelname, now_title, CR, next_title)


        else:
            label = channelname

        context_items = []

        channelname = channelname.encode("utf8")
        channelid =channelid.encode("utf8")

        context_items.append((_("Add Title Search Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search, channelid=channelid, channelname=channelname))))
        context_items.append((_("Add Plot Search Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot, channelid=channelid, channelname=channelname))))
        context_items.append((_("Play Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel, channelname=channelname))))
        if plugin.get_setting('external.player'):
            context_items.append((_("Play Channel External"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external, channelname=channelname))))

        if channelname not in favourites:
            context_items.append((_("Add Favourite Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_channel, channelname=channelname, channelid=channelid, thumbnail=thumbnail))))
        else:
            context_items.append((_("Remove Favourite Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel, channelname=channelname))))

        items.append({
            'label': label,
            'path': plugin.url_for(channel, channelid=channelid),
            'context_menu': context_items,
            'thumbnail': thumbnail,
            'info':{"plot":description, "genre":categories}
        })

    return items


@plugin.route('/groups')
def groups():
    items = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    channelgroups = cursor.execute("SELECT DISTINCT groups FROM streams ORDER BY groups").fetchall()

    for channelgroup in [("All Channels", )] + channelgroups:
        channelgroup = channelgroup[0]

        if not channelgroup:
            continue

        items.append({
            'label': channelgroup,
            'path': plugin.url_for(group, channelgroup=channelgroup.encode("utf8")),
            'thumbnail': get_icon_path('folder'),
        })

    return items


@plugin.route('/tv')
def tv():
    items = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    titles = cursor.execute('SELECT DISTINCT title FROM programmes WHERE episode IS NOT null AND episode IS NOT "MOVIE" ORDER BY title').fetchall()

    for title_row in titles:
        title = title_row[0]

        items.append({
            'label': title.encode("utf8"),
            'path': plugin.url_for(tv_show, title=title.encode("utf8")),
            'thumbnail': get_icon_path('folder'),
        })

    return items

@plugin.route('/movies')
def movies():
    items = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    titles = cursor.execute('SELECT DISTINCT title, date FROM programmes WHERE episode IS "MOVIE" ORDER BY title').fetchall()

    for title_row in titles:
        title = title_row[0]
        date = title_row[1] or "None"

        if date == "None":
            label = title
        else:
            label = "%s (%s)" % (title, date)

        items.append({
            'label': label,
            'path': plugin.url_for(movie, title=title.encode("utf8"), date=date.encode("utf8")),
            'thumbnail': get_icon_path('folder'),
        })

    return items

@plugin.route('/others')
def others():
    items = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    titles = cursor.execute('SELECT DISTINCT title FROM programmes WHERE episode IS null ORDER BY title').fetchall()

    for title_row in titles:
        title = title_row[0]

        label = title

        items.append({
            'label': label,
            'path': plugin.url_for(other, title=title.encode("utf8")),
            'thumbnail': get_icon_path('folder'),
        })

    return items


@plugin.route('/categories')
def categories():
    items = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    titles = cursor.execute('SELECT DISTINCT categories FROM programmes ORDER BY categories').fetchall()

    cats = set()
    for title in titles:
        programme_categories = title[0]
        cats.add(programme_categories)
        programme_categories = programme_categories.split(', ')
        for cat in programme_categories:
            if cat:
                cats.add(cat)
    cats = sorted(list(cats))

    for cat in cats:
        if not cat or ',' in cat:
            continue
        label = cat
        title = cat.encode("utf8")

        items.append({
            'label': label,
            'path': plugin.url_for(category, title=title),
            'thumbnail': get_icon_path('folder'),
        })

    return items


@plugin.route('/service')
def service():
    threading.Thread(target=service_thread).start()


@plugin.route('/full_service')
def full_service():
    xmltv()
    service_thread()


@plugin.route('/service_thread')
def service_thread():
    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    rules = cursor.execute('SELECT uid, channelid, channelname, title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", description, type FROM rules ORDER by channelname, title, start, stop').fetchall()

    for uid, jchannelid, jchannelname, jtitle, jstart, jstop, jdescription, type  in rules:

        if '%' in jtitle:
            compare='LIKE'
        else:
            compare='='

        watch = False
        remind = False
        if type.startswith("WATCH"):
            type = type.replace("WATCH ","")
            watch = True
        elif type.startswith("REMIND"):
            type = type.replace("REMIND ","")
            remind = True

        if type == "ALWAYS":
            #TODO scrub [] from title

            programmes = cursor.execute(
            'SELECT uid, channelid , title , sub_title , date , description , episode, categories FROM programmes WHERE channelid=? AND title %s ?' % compare,
            (jchannelid, jtitle)).fetchall()

            for p in programmes:
                uid, channel , title , sub_title , date , description , episode, categories = p
                record_once(programmeid=uid, do_refresh=False, watch=watch, remind=remind)

        elif type == "DAILY":
            tjstart = jstart.time()
            tjstop = jstop.time()

            programmes = cursor.execute(
            'SELECT uid, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]" FROM programmes WHERE channelid=? AND title %s ?' % compare,
            (jchannelid, jtitle)).fetchall()

            for p in programmes:
                uid, start, stop = p
                tstart = start.time()
                tstop = stop.time()
                if tjstart == tstart and tjstop == tstop:
                    record_once(programmeid=uid, do_refresh=False, watch=watch, remind=remind)

        elif type == "SEARCH":
            programmes = cursor.execute("SELECT uid FROM programmes WHERE channelid=? AND title LIKE ?", (jchannelid, "%"+jtitle+"%")).fetchall()
            for p in programmes:
                uid = p[0]
                record_once(programmeid=uid, do_refresh=False, watch=watch, remind=remind)

        elif type == "PLOT":
            programmes = cursor.execute("SELECT uid FROM programmes WHERE channelid=? AND description LIKE ?", (jchannelid, "%"+jdescription+"%")).fetchall()
            for p in programmes:
                uid = p[0]
                record_once(programmeid=uid, do_refresh=False, watch=watch, remind=remind)

    refresh()


@plugin.route('/delete_recording/<label>/<path>')
def delete_recording(label, path):
    label = label.decode("utf8")
    if not (xbmcgui.Dialog().yesno("IPTV Recorder", "[COLOR red]" + _("Delete Recording?") + "[/COLOR]", label)):
        return
    xbmcvfs.delete(path)
    xbmcvfs.delete(path[:-3]+'.json')
    refresh()


@plugin.route('/delete_all_recordings')
def delete_all_recordings():
    if not (xbmcgui.Dialog().yesno("IPTV Recorder", "[COLOR red]" + _("Delete All Recordings?") + "[/COLOR]")):
        return

    dir = plugin.get_setting('recordings')
    dirs, files = xbmcvfs.listdir(dir)

    items = []

    for file in sorted(files):
        if file.endswith('.ts') or file.endswith('.json'):
            path = os.path.join(xbmc.translatePath(dir), file)
            xbmcvfs.delete(path)

    refresh()


def find_files(root):
    dirs, files = xbmcvfs.listdir(root)
    found_files = []
    for dir in dirs:
        path = os.path.join(xbmc.translatePath(root), dir)
        found_files = found_files + find_files(path)
    file_list = []
    for file in files:
        if file.endswith('.ts'):
            file = os.path.join(xbmc.translatePath(root), file)
            file_list.append(file)
    return found_files + file_list


@plugin.route('/recordings')
def recordings():
    dir = plugin.get_setting('recordings')
    found_files = find_files(dir)

    items = []
    starts = []

    for path in found_files:
        json_file = path[:-3]+'.json'
        info = json.loads(xbmcvfs.File(json_file).read())
        programme = info["programme"]

        title = programme['title']
        sub_title = programme['sub_title'] or ''
        episode = programme['episode']
        date = "(%s)" % programme['date'] or ''
        start = programme['start']
        starts.append(start)

        if episode and episode != "MOVIE":
            label = "%s [COLOR grey]%s[/COLOR] %s" % (title, episode, sub_title)
        elif episode == "MOVIE":
            label = "%s %s" % (title,date)
        else:
            label = "%s %s" % (title, sub_title)

        description = programme['description']

        context_items = []

        context_items.append((_("Delete Recording"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_recording, label=label.encode("utf8"), path=path))))
        context_items.append((_("Delete All Recordings"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_recordings))))
        if plugin.get_setting('external.player'):
            context_items.append((_("External Player"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_external, path=path))))

        items.append({
            'label': label,
            'path': path,
            'is_playable': True,
            'context_menu': context_items,
            'info_type': 'Video',
            'info':{"title": label, "plot":description},
        })

    xbmcplugin.addSortMethod( handle=int( sys.argv[ 1 ] ), sortMethod=xbmcplugin.SORT_METHOD_UNSORTED )
    xbmcplugin.addSortMethod( handle=int( sys.argv[ 1 ] ), sortMethod=xbmcplugin.SORT_METHOD_LABEL )
    xbmcplugin.addSortMethod( handle=int( sys.argv[ 1 ] ), sortMethod=xbmcplugin.SORT_METHOD_DATE )

    start_items = zip(starts,items)
    start_items.sort(reverse=True)
    items = [x for y, x in start_items]
    return items


def xml2utc(xml):
    match = re.search(r'([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2}) ([+-])([0-9]{2})([0-9]{2})', xml)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))
        sign = match.group(7)
        hours = int(match.group(8))
        minutes = int(match.group(9))
        dt = datetime(year, month, day, hour, minute, second)
        td = timedelta(hours=hours, minutes=minutes)
        if sign == '+':
            dt = dt - td
        else:
            dt = dt + td
        return dt
    return ''


@plugin.route('/xmltv')
def xmltv():
    dialog = xbmcgui.DialogProgressBG()
    dialog.create("IPTV Recorder", _("Loading data..."))

    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    xbmcvfs.mkdirs(profilePath)

    dialog.update(0, message=_("Creating database"))
    databasePath = os.path.join(profilePath, 'xmltv.db')
    conn = sqlite3.connect(databasePath, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    conn.execute('DROP TABLE IF EXISTS programmes')
    conn.execute('DROP TABLE IF EXISTS channels')
    conn.execute('DROP TABLE IF EXISTS streams')
    conn.execute('CREATE TABLE IF NOT EXISTS channels(uid INTEGER PRIMARY KEY ASC, id TEXT, name TEXT, icon TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS programmes(uid INTEGER PRIMARY KEY ASC, channelid TEXT, title TEXT, sub_title TEXT, start TIMESTAMP, stop TIMESTAMP, date TEXT, description TEXT, episode TEXT, categories TEXT, xml TEXT)')
    #TODO unique fails with timestamps: UNIQUE(channelid, channelname, start, stop, description, type)
    conn.execute('CREATE TABLE IF NOT EXISTS rules(uid INTEGER PRIMARY KEY ASC, channelid TEXT, channelname TEXT, title TEXT, sub_title TEXT, start TIMESTAMP, stop TIMESTAMP, date TEXT, description TEXT, episode TEXT, categories TEXT, type TEXT)')
    #TODO check primary key
    conn.execute('CREATE TABLE IF NOT EXISTS streams(uid INTEGER PRIMARY KEY ASC, name TEXT, tvg_name TEXT, tvg_id TEXT, tvg_logo TEXT, groups TEXT, url TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS favourites(channelname TEXT, channelid TEXT, logo TEXT, PRIMARY KEY(channelname))')
    conn.execute('CREATE TABLE IF NOT EXISTS jobs(uid INTEGER PRIMARY KEY ASC, uuid TEXT, channelid TEXT, channelname TEXT, title TEXT, start TIMESTAMP, stop TIMESTAMP, type TEXT)')

    shifts = {}

    for x in ["1","2"]:

        dialog.update(0, message=_("Finding streams"))
        mode = plugin.get_setting('external.m3u.'+x)
        if mode == "0":
            if x == "1":
                try:
                    m3uPathType = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uPathType')

                    if m3uPathType == "0":
                        path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uPath')
                    else:
                        path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uUrl')
                except:
                    path = ""
            else:
                path = ""
        elif mode == "1":
            path = plugin.get_setting('external.m3u.file.'+x)
        else:
            path = plugin.get_setting('external.m3u.url.'+x)

        if path:

            m3uFile = 'special://profile/addon_data/plugin.video.iptv.recorder/channels'+x+'.m3u'

            xbmcvfs.copy(path, m3uFile)
            f = open(xbmc.translatePath(m3uFile),'rb')
            f = open(xbmc.translatePath(m3uFile),'rb')
            data = f.read()
            encoding = chardet.detect(data)
            data = data.decode(encoding['encoding'])

            global_shift = 0
            header = re.search('#EXTM3U(.*)', data)
            if header:
                tvg_shift = re.search('tvg-shift="(.*?)"', header.group(1))
                if tvg_shift:
                    tvg_shift = tvg_shift.group(1)
                    global_shift = int(tvg_shift)

            channels = re.findall('#EXTINF:(.*?)(?:\r\n|\r|\n)(.*?)(?:\r\n|\r|\n|$)', data, flags=(re.I | re.DOTALL))
            total = len(channels)
            i = 0
            for channel in channels:

                name = channel[0].rsplit(',', 1)[-1]
                tvg_name = re.search('tvg-name="(.*?)"', channel[0])
                if tvg_name:
                    tvg_name = tvg_name.group(1)

                tvg_id = re.search('tvg-id="(.*?)"', channel[0])
                if tvg_id:
                    tvg_id = tvg_id.group(1)

                tvg_logo = re.search('tvg-logo="(.*?)"', channel[0])
                if tvg_logo:
                    tvg_logo = tvg_logo.group(1)

                shifts[tvg_id] = global_shift
                tvg_shift = re.search('tvg-shift="(.*?)"', channel[0])
                if tvg_shift:
                    tvg_shift = tvg_shift.group(1)
                    shifts[tvg_id] = tvg_shift

                url = channel[1]
                search = plugin.get_setting('m3u.regex.search')
                replace = plugin.get_setting('m3u.regex.replace')
                if search:
                    url = re.sub(search, replace, url)

                groups = re.search('group-title="(.*?)"', channel[0])
                if groups:
                    groups = groups.group(1)

                conn.execute("INSERT OR IGNORE INTO streams(name, tvg_name, tvg_id, tvg_logo, groups, url) VALUES (?, ?, ?, ?, ?, ?)",
                [name.strip(), tvg_name, tvg_id, tvg_logo, groups, url.strip()])

                i += 1
                percent = 0 + int(100.0 * i / total)
                dialog.update(percent, message=_("Finding streams"))

    for x in ["1","2"]:

        mode = plugin.get_setting('external.xmltv.'+x)
        if mode == "0":
            if x == "1":
                try:
                    epgPathType = xbmcaddon.Addon('pvr.iptvsimple').getSetting('epgPathType')
                    if epgPathType == "0":
                        path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('epgPath')
                    else:
                        path = xbmcaddon.Addon('pvr.iptvsimple').getSetting('epgUrl')
                except:
                    path = ""
            else:
                path = ""
        elif mode == "1":
            path = plugin.get_setting('external.xmltv.file.'+x)
        else:
            path = plugin.get_setting('external.xmltv.url.'+x)

        if path:

            tmp = os.path.join(profilePath, 'xmltv'+x+'.tmp')
            xml = os.path.join(profilePath, 'xmltv'+x+'.xml')
            dialog.update(0, message=_("Copying xmltv file"))
            xbmcvfs.copy(path, tmp)

            f = xbmcvfs.File(tmp, "rb")
            magic = f.read(3)
            f.close()
            if magic == "\x1f\x8b\x08":
                dialog.update(0, message=_("Unzipping xmltv file"))
                g = gzip.open(tmp)
                data = g.read()
                f = xbmcvfs.File(xml, "wb")
                f.write(data)
                f.close()
            else:
                xbmcvfs.copy(tmp, xml)

            data = xbmcvfs.File(xml, 'rb').read()

            match = re.search('<\?xml.*?encoding="(.*?)"',data,flags=(re.I|re.DOTALL))
            if match:
                encoding = match.group(1)
            else:
                chardet_encoding = chardet.detect(data)
                encoding = chardet_encoding['encoding']
            data = data.decode(encoding)

            htmlparser = HTMLParser()

            dialog.update(0, message=_("Finding channels"))
            match = re.findall('<channel(.*?)</channel>', data, flags=(re.I|re.DOTALL))
            if match:
                total = len(match)
                i = 0
                for m in match:
                    id = re.search('id="(.*?)"', m)
                    if id:
                        id = htmlparser.unescape(id.group(1))

                    name = None
                    names = re.findall('<display-name.*?>(.*?)</display-name', m)
                    if names:
                        for name in reversed(names): #First only
                            name = htmlparser.unescape(name)

                    icon = re.search('<icon.*?src="(.*?)"', m)
                    if icon:
                        icon = icon.group(1)

                    conn.execute("INSERT OR IGNORE INTO channels(id, name, icon) VALUES (?, ?, ?)", [id, name, icon])

                    i += 1
                    percent = 0 + int(100.0 * i / total)
                    dialog.update(percent, message=_("Finding channels"))

            dialog.update(0, message=_("Finding programmes"))
            match = re.findall('<programme(.*?)</programme>', data, flags=(re.I|re.DOTALL))
            if match:
                total = len(match)
                i = 0
                for m in match:
                    xml = "" #'<programme%s</programme>' % m

                    channel = re.search('channel="(.*?)"', m)
                    if channel:
                        channel = htmlparser.unescape(channel.group(1))

                    if channel in shifts:
                        shift = int(shifts[channel])
                    else:
                        shift = None

                    start = re.search('start="(.*?)"', m)
                    if start:
                        start = start.group(1)
                        start = xml2utc(start)
                        if shift:
                            start = start + timedelta(hours=shift)

                    stop = re.search('stop="(.*?)"', m)
                    if stop:
                        stop = stop.group(1)
                        stop = xml2utc(stop)
                        if shift:
                            stop = stop + timedelta(hours=shift)

                    title = re.search('<title.*?>(.*?)</title', m, flags=(re.I|re.DOTALL))
                    if title:
                        title = htmlparser.unescape(title.group(1))
                    search = plugin.get_setting('xmltv.title.regex.search')
                    replace = plugin.get_setting('xmltv.title.regex.replace')
                    if search:
                        title = re.sub(search, replace, title)
                    if title:
                        title = title.strip()

                    sub_title = re.search('<sub-title.*?>(.*?)</sub-title', m, flags=(re.I|re.DOTALL))
                    if sub_title:
                        sub_title = htmlparser.unescape(sub_title.group(1))

                    description = re.search('<desc.*?>(.*?)</desc', m, flags=(re.I|re.DOTALL))
                    if description:
                        description = htmlparser.unescape(description.group(1))

                    date = re.search('<date.*?>(.*?)</date', m)
                    if date:
                        date = date.group(1)

                    cats = re.findall('<category.*?>(.*?)</category>', m, flags=(re.I|re.DOTALL))
                    if cats:
                        categories = htmlparser.unescape((', '.join(cats)))
                    else:
                        categories = ''
                    cats = categories.lower()
                    film_movie = ("movie" in cats) or ("film" in cats)

                    #TODO other systems
                    episode = re.findall('<episode-num system="(.*?)">(.*?)<', m, flags=(re.I|re.DOTALL))
                    episode = {x[0]:x[1] for x in episode}

                    SE = None
                    if episode:
                        if episode.get('xmltv_ns'):
                            num = episode.get('xmltv_ns')
                            parts = num.split('.')
                            if len(parts) >= 2:
                                S = parts[0]
                                E = parts[1].split('/')[0]
                                S = int(S if S else 0) + 1
                                E = int(E if E else 0) + 1
                            SE = "S%02dE%02d" % (S,E)
                        elif episode.get('common'):
                            SE = episode.get('common')
                        elif episode.get('dd_progid'):
                            num = episode.get('dd_progid')
                            if num.startswith('EP') and date and len(date) == 8:
                                SE = "%s-%s-%s" % (date[0:4], date[4:6], date[6:8])
                            elif num.startswith('MV'):
                                SE = "MOVIE"
                    elif film_movie:
                        SE = "MOVIE"
                    episode = SE

                    conn.execute("INSERT OR IGNORE INTO programmes(channelid, title, sub_title, start, stop, date, description, episode, categories, xml) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [channel, title, sub_title, start, stop, date, description, episode, categories, xml])

                    i += 1
                    percent = 0 + int(100.0 * i / total)
                    dialog.update(percent, message=_("Finding programmes"))

    missing_streams = conn.execute('SELECT name, tvg_name FROM streams WHERE tvg_id IS null OR tvg_id IS ""').fetchall()
    sql_channels = conn.execute('SELECT id, name FROM channels').fetchall()
    lower_channels = {x[1].lower():x[0] for x in sql_channels}
    for name, tvg_name in missing_streams:
        if tvg_name:
            tvg_id = None
            _tvg_name = tvg_name.replace("_"," ").lower()
            if _tvg_name in lower_channels:
                tvg_id = lower_channels[_tvg_name]
                conn.execute("UPDATE streams SET tvg_id=? WHERE tvg_name=?", (tvg_id, tvg_name))
        elif name.lower() in lower_channels:
            tvg_id = lower_channels[name.lower()]
            conn.execute("UPDATE streams SET tvg_id=? WHERE name=?", (tvg_id, name))

    conn.commit()
    conn.close()

    dialog.update(100, message=_("Finished loading data"))
    time.sleep(1)
    dialog.close()
    return


@plugin.route('/nuke')
def nuke():
    if not (xbmcgui.Dialog().yesno("IPTV Recorder", _("Delete Everything and Start Again?"))):
        return

    xbmcvfs.delete(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    time.sleep(5)
    full_service()


@plugin.route('/')
def index():
    items = []
    context_items = []

    items.append(
    {
        'label': _("Favourite Channels"),
        'path': plugin.url_for('favourite_channels'),
        'thumbnail':get_icon_path('favourites'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Channel Groups"),
        'path': plugin.url_for('groups'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("TV Shows"),
        'path': plugin.url_for('tv'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Movies"),
        'path': plugin.url_for('movies'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Other"),
        'path': plugin.url_for('others'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Categories"),
        'path': plugin.url_for('categories'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })


    items.append(
    {
        'label': _("Jobs"),
        'path': plugin.url_for('jobs'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Rules"),
        'path': plugin.url_for('rules'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Recordings"),
        'path': plugin.url_for('recordings'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Recordings Folder"),
        'path': plugin.get_setting('recordings'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Full EPG"),
        'path': plugin.url_for('epg'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Search Title"),
        'path': plugin.url_for('search_title_dialog'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Search Plot"),
        'path': plugin.url_for('search_plot_dialog'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Search Categories"),
        'path': plugin.url_for('search_categories_dialog'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    if plugin.get_setting('debug') == "true":
        items.append(
        {
            'label': _("Service"),
            'path': plugin.url_for('service'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

        items.append(
        {
            'label': _("Reload Data"),
            'path': plugin.url_for('xmltv'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

        items.append(
        {
            'label': _("NUKE"),
            'path': plugin.url_for('nuke'),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

    return items

if __name__ == '__main__':
    plugin.run()

    containerAddonName = xbmc.getInfoLabel('Container.PluginName')
    AddonName = xbmcaddon.Addon().getAddonInfo('id')

    if containerAddonName == AddonName:

        if big_list_view == True:

            view_mode = int(plugin.get_setting('view.mode') or "0")

            if view_mode:
                plugin.set_view_mode(view_mode)
