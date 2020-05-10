# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from xbmcswift2 import Plugin, ListItem
from collections import namedtuple
from datetime import datetime, timedelta, tzinfo
from language import get_string as _
from struct import *
import base64
import calendar
import chardet
import ctypes
import glob
import gzip
import json
import os, os.path
import platform
import random
import re
import requests
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
try:
    from urllib.parse import quote, quote_plus, unquote_plus
    from html.parser import HTMLParser
    from io import StringIO
except ImportError:
    from urllib import quote, quote_plus, unquote_plus
    from HTMLParser import HTMLParser
    from StringIO import StringIO

import uuid
from kodi_six import xbmc, xbmcaddon, xbmcvfs, xbmcgui, xbmcplugin

def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')


def log(v):
    xbmc.log(repr(v), xbmc.LOGERROR)



plugin = Plugin()
big_list_view = True


if plugin.get_setting('multiline', str) == "true":
    CR = "[CR]"
else:
    CR = ""


def get_icon_path(icon_name):
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(), icon_name)


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]", '', label, flags=re.I)
    label = re.sub(r"\[/?COLOR.*?\]", '', label, flags=re.I)
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

def rmdirs(path):
    path = xbmc.translatePath(path)
    dirs, files = xbmcvfs.listdir(path)
    for dir in dirs:
        rmdirs(os.path.join(path,dir))
    xbmcvfs.rmdir(path)


def find(path):
    path = xbmc.translatePath(path)
    all_dirs = []
    all_files = []
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        file_path = os.path.join(path,file)
        all_files.append(file_path)
    for dir in dirs:
        dir_path = os.path.join(path,dir)
        all_dirs.append(dir_path)
        new_dirs, new_files = find(os.path.join(path, dir))
        for new_dir in new_dirs:
            new_dir_path = os.path.join(path,dir,new_dir)
            all_dirs.append(new_dir_path)
        for new_file in new_files:
            new_file = os.path.join(path,dir,new_file)
            all_files.append(new_file)
    return all_dirs, all_files


@plugin.route('/play_channel/<channelname>')
def play_channel(channelname):
    channelname = channelname.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    channel = c.execute("SELECT url FROM streams WHERE name=?", (channelname, )).fetchone()

    if not channel:
        return
    url = channel[0]
    #plugin.set_resolved_url(url)
    xbmc.Player().play(url)


@plugin.route('/play_channel_external/<channelname>')
def play_channel_external(channelname):
    channelname = channelname.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')))
    c = conn.cursor()

    channel = c.execute("SELECT url FROM streams WHERE name=?", (channelname, )).fetchone()
    if not channel:
        return
    url = channel[0]

    if url:
        cmd = [plugin.get_setting('external.player', str)]

        args = plugin.get_setting('external.player.args', str)
        if args:
            cmd.append(args)

        cmd.append(url)

        #TODO shell?
        subprocess.Popen(cmd,shell=windows())


@plugin.route('/play_external/<path>')
def play_external(path):
    cmd = [plugin.get_setting('external.player', str)]

    args = plugin.get_setting('external.player.args', str)
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

    now = datetime.now()
    for uid, uuid, channelid, channelname, title, start, stop, type in jobs:
        local_stop = utc2local(stop)
        if local_stop < now:
            continue

        url = ""
        channel = cursor.execute("SELECT name, url FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
        if channel:
            name, url = channel
            echannelname=name.encode("utf8")

        context_items = []

        context_items.append((_("Delete Job"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_job, job=uuid))))
        context_items.append((_("Delete All Jobs"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_jobs))))

        if url:
            context_items.append((_("Play Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel, channelname=echannelname))))
            if plugin.get_setting('external.player', str):
                context_items.append((_("Play Channel External"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external, channelname=echannelname))))


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

    rules = cursor.execute('SELECT uid, channelid, channelname, title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", description, type, name FROM rules ORDER by channelname, title, start, stop').fetchall()

    items = []

    for uid, channelid, channelname, title, start, stop, description, type, rulename  in rules:

        url = ""
        channel = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
        if channel:
            cuid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel
            echannelname=name.encode("utf8")

        context_items = []
        context_items.append((_("Delete Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_rule, uid=uid))))
        context_items.append((_("Delete All Rules"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_rules))))

        if url:
            context_items.append((_("Play Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel, channelname=echannelname))))
            if plugin.get_setting('external.player', str):
                context_items.append((_("Play Channel External"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external, channelname=echannelname))))

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
            label = "%s [COLOR yellow]%s[/COLOR] %s ALWAYS" % (channelname, title, type_label)
        elif type == "DAILY":
            label =  "%s [COLOR yellow]%s[/COLOR] %s[COLOR grey]%s - %s[/COLOR] %s DAILY" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time(), type_label)
        elif type == "WEEKLY":
            label =  "%s [COLOR yellow]%s[/COLOR] %s[COLOR grey]%s - %s[/COLOR] %s WEEKLY" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time(), type_label)
        elif type == "SEARCH":
            label = "%s [COLOR yellow]%s[/COLOR] %s SEARCH" % (channelname, title, type_label)
        elif type == "PLOT":
            label = "%s [COLOR yellow](%s)[/COLOR] %s PLOT" % (channelname, description, type_label)

        if rulename:
            label = "(%s) %s" % (rulename,label)

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

    job_details = cursor.execute("SELECT uuid FROM jobs WHERE uuid=?", (job, )).fetchone()
    if not job_details:
        return

    if ask and not (xbmcgui.Dialog().yesno("IPTV Recorder", _("Cancel Record?"))):
        return

    if windows() and plugin.get_setting('task.scheduler', str) == 'true':
        cmd = ["schtasks", "/delete", "/f", "/tn", job]
        subprocess.Popen(cmd, shell=True)
    else:
        xbmc.executebuiltin('CancelAlarm(%s, True)' % job)

    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    pyjob = directory + job + ".py"

    pid = xbmcvfs.File(pyjob+'.pid').read()

    xbmcvfs.delete(pyjob)
    xbmcvfs.delete(pyjob+'.pid')

    if pid and kill:
        if windows():
            subprocess.Popen(["taskkill", "/im", pid], shell=True)
        else:
            #TODO correct kill switch
            subprocess.Popen(["kill", "-9", pid])

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


@plugin.route('/delete_ffmpeg')
def delete_ffmpeg():
    if xbmc.getCondVisibility('system.platform.android'):
        ffmpeg_dst = '/data/data/%s/ffmpeg' % android_get_current_appid()
        xbmcvfs.delete(ffmpeg_dst)


def ffmpeg_location():
    ffmpeg_src = xbmc.translatePath(plugin.get_setting('ffmpeg', str))

    if xbmc.getCondVisibility('system.platform.android'):
        ffmpeg_dst = '/data/data/%s/ffmpeg' % android_get_current_appid()

        if (plugin.get_setting('ffmpeg', str) != plugin.get_setting('ffmpeg.last', str)) or (not xbmcvfs.exists(ffmpeg_dst) and ffmpeg_src != ffmpeg_dst):
            xbmcvfs.copy(ffmpeg_src, ffmpeg_dst)
            plugin.set_setting('ffmpeg.last',plugin.get_setting('ffmpeg', str))

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


@plugin.route('/record_once/<programmeid>/<channelid>/<channelname>')
def record_once(programmeid, channelid, channelname, do_refresh=True, watch=False, remind=False):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    start = None
    stop = None
    threading.Thread(target=record_once_thread,args=[programmeid, do_refresh, watch, remind, channelid, channelname, start, stop, False, None]).start()


@plugin.route('/watch_once/<programmeid>/<channelid>/<channelname>')
def watch_once(programmeid, channelid, channelname, do_refresh=True, watch=True, remind=False):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    start = None
    stop = None
    threading.Thread(target=record_once_thread,args=[programmeid, do_refresh, watch, remind, channelid, channelname, start, stop, False, None]).start()


@plugin.route('/remind_once/<programmeid>/<channelid>/<channelname>')
def remind_once(programmeid, channelid, channelname, do_refresh=True, watch=False, remind=True):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    start = None
    stop = None
    threading.Thread(target=record_once_thread,args=[programmeid, do_refresh, watch, remind, channelid, channelname, start, stop, False, None]).start()


@plugin.route('/record_one_time/<channelname>')
def record_one_time( channelname):
    #channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    utcnow = datetime.utcnow()
    ts = time.time()
    utc_offset = total_seconds(datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts))

    date = xbmcgui.Dialog().input("Start Date",type=xbmcgui.INPUT_DATE)
    if not date:
        return
    day, month, year = date.split('/')

    start = xbmcgui.Dialog().input("Start Time",type=xbmcgui.INPUT_TIME)
    if not start:
        return
    hms = start.split(':')
    hour = hms[0]
    min = hms[1]
    start = utcnow.replace(day=int(day), month=int(month), year=int(year), hour=int(hour), minute=int(min), second=0, microsecond=0) - timedelta(seconds=utc_offset)

    stop = xbmcgui.Dialog().input("Stop",type=xbmcgui.INPUT_TIME)
    if not stop:
        return
    hms = stop.split(':')
    hour = hms[0]
    min = hms[1]
    stop = utcnow.replace(day=int(day), month=int(month), year=int(year), hour=int(hour), minute=int(min), second=0, microsecond=0) - timedelta(seconds=utc_offset)
    if stop < start:
        stop = stop + timedelta(days=1)

    name = xbmcgui.Dialog().input("Rule Name").decode("utf8")

    do_refresh = False
    watch = False
    remind = False
    channelid = None
    threading.Thread(target=record_once_thread,args=[None, do_refresh, watch, remind, channelid, channelname, start, stop, False, name]).start()


@plugin.route('/record_and_play/<channelname>')
def record_and_play(channelname):
    #channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    utcnow = datetime.utcnow()
    ts = time.time()
    utc_offset = total_seconds(datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts))

    start = utcnow - timedelta(seconds=utc_offset)

    hours = xbmcgui.Dialog().input("Hours",type=xbmcgui.INPUT_NUMERIC,defaultt="4")
    #log(hours)

    stop = utcnow - timedelta(seconds=utc_offset) + timedelta(hours=int(hours))

    do_refresh = False
    watch = False
    remind = False
    channelid = None
    threading.Thread(target=record_once_thread,args=[None, do_refresh, watch, remind, channelid, channelname, start, stop, True, None]).start()
    time.sleep(5)

    return recordings()


@plugin.route('/record_once_time/<channelid>/<channelname>/<start>/<stop>')
def record_once_time(channelid, channelname, start, stop, do_refresh=True, watch=False, remind=True, title=None):
    if channelid:
        channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    threading.Thread(target=record_once_thread,args=[None, do_refresh, watch, remind, channelid, channelname, start, stop, False, title]).start()


@plugin.route('/record_epg/<channelname>/<name>/<start>/<stop>')
def record_epg(channelname, name, start, stop):

    channelname = channelname.decode("utf8")
    name = name.decode("utf8")

    start = get_utc_from_string(start.decode("utf8"))
    stop = get_utc_from_string(stop.decode("utf8"))

    log("Scheduling record for '{}: {} ({} to {})'".format(channelname, name, start, stop))

    do_refresh = False
    watch = False
    remind = False
    channelid = None
    threading.Thread(target=record_once_thread,args=[None, do_refresh, watch, remind, channelid, channelname, start, stop, False, name]).start()


def get_utc_from_string(date_string):
    utcnow = datetime.utcnow()
    ts = time.time()
    utc_offset = total_seconds(datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts))

    r = re.search(r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):\d{2}', date_string)
    if r:
        year, month, day, hour, minute = r.group(1), r.group(2), r.group(3), r.group(4), r.group(5)
        return utcnow.replace(day=int(day), month=int(month), year=int(year), hour=int(hour), minute=int(minute),
                              second=0, microsecond=0) - timedelta(seconds=utc_offset)

def write_in_file(file, string):
    file.write(bytearray(string.encode('utf8')))

def record_once_thread(programmeid, do_refresh=True, watch=False, remind=False, channelid=None, channelname=None, start=None,stop=None, play=False, title=None):
    #TODO check for ffmpeg process already recording if job is re-added

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    if programmeid:
        programme = cursor.execute('SELECT channelid, title, sub_title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date, description, episode, categories FROM programmes WHERE uid=? LIMIT 1', (programmeid, )).fetchone()
        channelid, title, sub_title, start, stop, date, description, episode, categories = programme

        nfo = {"programme":{"channelid":channelid, "title":title, "sub_title":sub_title, "start":datetime2timestamp(start), "stop":datetime2timestamp(stop), "date":date, "description":description, "episode":episode, "categories":categories}}
    else:
        #title = None
        nfo = {}

    #log((channelid,channelname))
    if channelid:
        channel = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE tvg_id=? AND tvg_name=?", (channelid, channelname)).fetchone()
        if not channel:
            channel = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE tvg_id=? AND name=?", (channelid, channelname)).fetchone()
    else:
        channel = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE name=?", (channelname,)).fetchone()
        if not channel:
            channel = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE tvg_name=?", (channelname,)).fetchone()

    if not channel:
        xbmc.log("No channel %s" % channelname, xbmc.LOGERROR)
        return

    uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel
    thumbnail = tvg_logo
    if not channelname:
        channelname = name
    nfo["channel"] = {"channelname":channelname, "thumbnail":thumbnail, "channelid":tvg_id}
    #log(url)
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
                headers[k] = unquote_plus(v)

    local_starttime = utc2local(start)
    local_endtime = utc2local(stop)

    if programmeid:
        ftitle = sane_name(title)
        if sub_title:
            fsub_title = sane_name(sub_title)
    else:
        ftitle = sane_name(title)
    fchannelname = sane_name(channelname)

    folder = ""
    movie = False
    series = False
    if programmeid:
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
            folder = ftitle
            if sub_title:
                filename = "%s %s - %s - %s" % (ftitle, fsub_title, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
            else:
                filename = "%s - %s - %s" % (ftitle, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
    else:
        folder = fchannelname
        if ftitle:
            filename = "%s - %s - %s" % (ftitle, fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))
        else:
            filename = "%s - %s" % (fchannelname, local_starttime.strftime("%Y-%m-%d %H-%M"))

    if watch:
        type = "WATCH"
    elif remind:
        type = "REMIND"
    else:
        type = "RECORD"

    job = cursor.execute("SELECT * FROM jobs WHERE channelid=? AND channelname=? AND start=? AND stop=? AND type=?", (channelid, channelname, start, stop, type)).fetchone()
    if job:
        return

    before = int(plugin.get_setting('minutes.before', str) or "0")
    after = int(plugin.get_setting('minutes.after', str) or "0")
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

    kodi_recordings = xbmc.translatePath(plugin.get_setting('recordings', str))
    ffmpeg_recordings = plugin.get_setting('ffmpeg.recordings', str) or kodi_recordings
    if series:
        dir = os.path.join(kodi_recordings, "TV", folder)
        ffmpeg_dir = os.path.join(ffmpeg_recordings, "TV", folder)
    elif movie:
        dir = os.path.join(kodi_recordings, "Movies", folder)
        ffmpeg_dir = os.path.join(ffmpeg_recordings, "Movies", folder)
    else:
        dir = os.path.join(kodi_recordings, "Other", folder)
        ffmpeg_dir = os.path.join(ffmpeg_recordings, "Other", folder)
    xbmcvfs.mkdirs(dir)
    path = os.path.join(dir, filename)
    json_path = path + '.json'
    path = path + '.' + plugin.get_setting('ffmpeg.ext', str)
    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return

    if plugin.get_setting('json', bool):
        json_nfo = json.dumps(nfo)
        f = xbmcvfs.File(json_path,'w')
        write_in_file(f, json_nfo)
        f.close()

    cmd = [ffmpeg]
    cmd.append("-i")
    cmd.append(url)
    for h in headers:
        cmd.append("-headers")
        cmd.append("%s:%s" % (h, headers[h]))

    probe_cmd = cmd

    ffmpeg_recording_path = os.path.join(ffmpeg_dir, filename + '.' + plugin.get_setting('ffmpeg.ext', str))

    cmd = probe_cmd + ["-y", "-t", str(seconds), "-fflags","+genpts","-vcodec","copy","-acodec","copy"]
    ffmpeg_reconnect = plugin.get_setting('ffmpeg.reconnect', bool)
    if ffmpeg_reconnect:
        cmd = cmd + ["-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "300"]
    ffmpeg_args = plugin.get_setting('ffmpeg.args', str)
    if ffmpeg_args:
        cmd = cmd + ffmpeg_args.split(' ')
    if (plugin.get_setting('ffmpeg.pipe', str) == 'true') and not (windows() and (plugin.get_setting('task.scheduler', str) == 'true')):
        cmd = cmd + ['-f', 'mpegts','-']
    else:
        cmd.append(ffmpeg_recording_path)

    post_command = plugin.get_setting('post.command', str)
    post_cmd = post_command.split(' ')
    post_cmd = [s.replace("$p",ffmpeg_recording_path).replace("$d",ffmpeg_dir).replace("$f",filename + '.' + plugin.get_setting('ffmpeg.ext', str)) for s in post_cmd]

    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    job = str(uuid.uuid1())
    pyjob = directory + job + ".py"

    f = xbmcvfs.File(pyjob, 'wb')
    write_in_file(f, "# -*- coding: utf-8 -*-\n")
    write_in_file(f, "import os, subprocess, time\n")


    debug = plugin.get_setting('debug.ffmpeg', str) == 'true'
    if watch == False and remind == False:
        if not (windows() and (plugin.get_setting('task.scheduler', str) == 'true')):
            write_in_file(f, "from kodi_six import xbmc,xbmcvfs,xbmcgui\n")
            notification = 'xbmcgui.Dialog().notification("Recording: %s", "%s", sound=%s)\n' % (channelname, title, plugin.get_setting('silent', str) == "false")
            write_in_file(f, notification)
            write_in_file(f, "cmd = %s\n" % repr(cmd))

            if url.startswith('plugin://'):
                write_in_file(f, "player = xbmc.Player()\n")
                write_in_file(f, "player.play('%s')\n" % url)
                write_in_file(f, "new_url = ''\n")
                write_in_file(f, "for _ in range(60):\n")
                write_in_file(f, "    time.sleep(1)\n")
                write_in_file(f, "    if player.isPlaying():\n")
                write_in_file(f, "        new_url = player.getPlayingFile()\n")
                write_in_file(f, "        break\n")
                write_in_file(f, "time.sleep(1)\n")
                write_in_file(f, "player.stop()\n")
                write_in_file(f, "time.sleep(1)\n")
                write_in_file(f, "if new_url:\n")
                write_in_file(f, "    cmd[2] = new_url\n")
        else:
            write_in_file(f, "cmd = %s\n" % repr(cmd))
        if debug:
            write_in_file(f, "stdout = open(r'%s','w+')\n" % xbmc.translatePath(pyjob+'.stdout.txt'))
            write_in_file(f, "stderr = open(r'%s','w+')\n" % xbmc.translatePath(pyjob+'.stderr.txt'))
            write_in_file(f, "p = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, shell=%s)\n" % windows())
        else:
            if (plugin.get_setting('ffmpeg.pipe', str) == 'true') and not (windows() and (plugin.get_setting('task.scheduler', str) == 'true')):
                write_in_file(f, "p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=%s)\n" % windows())
            else:
                write_in_file(f, "p = subprocess.Popen(cmd, shell=%s)\n" % windows())
        write_in_file(f, "f = open(r'%s', 'w+')\n" % xbmc.translatePath(pyjob+'.pid'))
        write_in_file(f, "f.write(repr(p.pid).encode('utf-8'))\n")
        write_in_file(f, "f.close()\n")
        if (plugin.get_setting('ffmpeg.pipe', str) == 'true') and not (windows() and (plugin.get_setting('task.scheduler', str) == 'true')):
            write_in_file(f, 'video = xbmcvfs.File(r"%s","wb")\n' % path)
            write_in_file(f, 'playing = False\n')
            write_in_file(f, "while True:\n")
            write_in_file(f, "  data = p.stdout.read(1000000)\n")
            write_in_file(f, "  if data:\n")
            write_in_file(f, "      video.write(data)\n")
            write_in_file(f, "  else:\n")
            write_in_file(f, "      break\n")
            if play:
                write_in_file(f, "  if not playing:\n")
                write_in_file(f, "    xbmc.Player().play(r'%s')\n" % path)
                write_in_file(f, "    playing = True\n")
            write_in_file(f, "video.close()\n")
        else:
            write_in_file(f, "p.wait()\n")
        if debug:
            write_in_file(f, "stderr.close()\n")
            write_in_file(f, "stdout.close()\n")
        if not (windows() and (plugin.get_setting('task.scheduler', str) == 'true')):
            notification = 'xbmcgui.Dialog().notification("Recording finished: %s", "%s", sound=%s)\n' % (channelname, title, plugin.get_setting('silent', str)=="false")
            write_in_file(f, notification)
        if post_command:
            write_in_file(f, "post_cmd = %s\n" % repr(post_cmd))
            write_in_file(f, "p = subprocess.Popen(post_cmd, shell=%s)\n" % windows())
        #TODO copy file somewhere else
    elif remind == True:
        cmd = 'xbmcgui.Dialog().notification("%s", "%s", sound=%s)\n' % (channelname, title, plugin.get_setting('silent', str)=="false")
        write_in_file(f, "from kodi_six import xbmc, xbmcgui\n")
        write_in_file(f, "%s\n" % cmd)
    else:
        if (plugin.get_setting('external.player.watch', str) == 'true') or (windows() and (plugin.get_setting('task.scheduler', str) == 'true')):
            cmd = [plugin.get_setting('external.player', str), plugin.get_setting('external.player.args', str), url]
            write_in_file(f, "cmd = %s\n" % repr(cmd))
            write_in_file(f, "p = subprocess.Popen(cmd, shell=%s)\n" % windows())
        else:
            cmd = 'xbmc.Player().play("%s")\n' % url
            write_in_file(f, "from kodi_six import xbmc\n")
            write_in_file(f, "%s\n" % cmd)
    f.close()

    if windows() and (plugin.get_setting('task.scheduler', str) == 'true') and remind == False:
        if immediate:
            cmd = 'RunScript(%s)' % (pyjob)
            xbmc.executebuiltin(cmd)
        else:
            st = "%02d:%02d" % (local_starttime.hour, local_starttime.minute)
            sd = "%02d/%02d/%04d" % (local_starttime.day, local_starttime.month, local_starttime.year)
            cmd = ["schtasks", "/create", "/f", "/tn", job, "/sc", "once", "/st", st, "/sd", sd, "/tr", "%s %s" % (xbmc.translatePath(plugin.get_setting('python', str)), xbmc.translatePath(pyjob))]
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


@plugin.route('/convert/<path>')
def convert(path):
    input = xbmcvfs.File(path,'rb')
    output = xbmcvfs.File(path.replace('.ts','.mp4'),'wb')
    error = open(xbmc.translatePath("special://profile/addon_data/plugin.video.iptv.recorder/errors.txt"),"w")

    cmd = [ffmpeg_location(),"-fflags","+genpts","-y","-i","-","-vcodec","copy","-acodec","copy","-f", "mpegts", "-"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=error, shell=windows())
    t = threading.Thread(target=read_thread,args=[p,output])
    t.start()

    while True:
        data_bytes = bytes(input.readBytes(100000))
        log(("read", len(data_bytes)))
        if not data_bytes:
            break
        p.stdin.write(bytearray(data_bytes))
    p.stdin.close()
    error.close()



def read_thread(p,output):
    while True:
        data = p.stdout.read(100000)
        if not len(data):
            break
        output.write(data)
    output.close()


@plugin.route('/renew_jobs')
def renew_jobs():
    #TODO check for ffmpeg process already recording if job is re-added

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    try:
        jobs = cursor.execute("SELECT * FROM jobs").fetchall()
    except:
        return

    for uid, uuid, channelid, channelname, title, start, stop, type in jobs:
        local_starttime = utc2local(start)
        local_endtime = utc2local(stop)

        before = int(plugin.get_setting('minutes.before', str) or "0")
        after = int(plugin.get_setting('minutes.after', str) or "0")
        local_starttime = local_starttime - timedelta(minutes=before)
        local_endtime = local_endtime + timedelta(minutes=after)

        now = datetime.now()
        if local_endtime < now:
            delete_job(uuid,ask=False)
            continue

        if (local_starttime < now) and (local_endtime > now):
            local_starttime = now
            immediate = True
        else:
            immediate = False

        directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
        xbmcvfs.mkdirs(directory)
        job = uuid
        pyjob = directory + job + ".py"

        #TODO reduce time of job if already started

        if windows() and (plugin.get_setting('task.scheduler', str) == 'true'):
            if immediate:
                cmd = 'RunScript(%s)' % (pyjob)
                xbmc.executebuiltin(cmd)
            else:
                pass
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
            else:
                cmd = 'AlarmClock(%s, RunScript(%s), %d, True)' % (job, pyjob, minutes)
                xbmc.executebuiltin(cmd)

    conn.close()


def sane_name(name):
    if not name:
        return
    if windows() or (plugin.get_setting('filename.urlencode', str) == 'true'):
        name = quote(name.encode('utf-8'))
        name = name.replace("%20",' ')
        name = name.replace('/',"%2F")
    else:
        _quote = {'"': '%22', '|': '%7C', '*': '%2A', '/': '%2F', '<': '%3C', ':': '%3A', '\\': '%5C', '?': '%3F', '>': '%3E'}
        for char in _quote:
            name = name.replace(char, _quote[char])
    return name


def refresh():
    containerAddonName = xbmc.getInfoLabel('Container.PluginName')
    AddonName = xbmcaddon.Addon().getAddonInfo('id')
    if (containerAddonName == AddonName) and (plugin.get_setting('refresh', str) == 'true') :
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/record_daily_time/<channelname>')
def record_daily_time(channelname):
    #channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    utcnow = datetime.utcnow()
    ts = time.time()
    utc_offset = total_seconds(datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts))

    start = xbmcgui.Dialog().input("Start Time",type=xbmcgui.INPUT_TIME)
    hms = start.split(':')
    hour = hms[0]
    min = hms[1]
    start = utcnow.replace(hour=int(hour),minute=int(min),second=0,microsecond=0) - timedelta(seconds=utc_offset)

    stop = xbmcgui.Dialog().input("Stop",type=xbmcgui.INPUT_TIME)
    hms = stop.split(':')
    hour = hms[0]
    min = hms[1]
    stop = utcnow.replace(hour=int(hour),minute=int(min),second=0,microsecond=0) - timedelta(seconds=utc_offset)
    if stop < start:
        stop = stop + timedelta(days=1)

    name = xbmcgui.Dialog().input("Rule Name").decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    channelid = None

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=null AND start=? AND stop =? AND type=?', (channelid, channelname, start, stop, "DAILY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, start, stop, type, name) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, start, stop, "DAILY", name])

    conn.commit()
    conn.close()

    service()


@plugin.route('/record_weekly_time/<channelname>')
def record_weekly_time(channelname):
    #channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")

    utcnow = datetime.utcnow()
    ts = time.time()
    utc_offset = total_seconds(datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts))

    date = xbmcgui.Dialog().input("Start Date",type=xbmcgui.INPUT_DATE)
    if not date:
        return
    day, month, year = date.split('/')

    start = xbmcgui.Dialog().input("Start Time",type=xbmcgui.INPUT_TIME)
    hms = start.split(':')
    hour = hms[0]
    min = hms[1]

    start = utcnow.replace(day=int(day), month=int(month), year=int(year), hour=int(hour), minute=int(min), second=0, microsecond=0) - timedelta(seconds=utc_offset)

    stop = xbmcgui.Dialog().input("Stop",type=xbmcgui.INPUT_TIME)
    hms = stop.split(':')
    hour = hms[0]
    min = hms[1]
    stop = utcnow.replace(hour=int(hour),minute=int(min),second=0,microsecond=0) - timedelta(seconds=utc_offset)
    if stop < start:
        stop = stop + timedelta(days=1)

    name = xbmcgui.Dialog().input("Rule Name").decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    channelid = None

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=null AND start=? AND stop =? AND type=?', (channelid, channelname, start, stop, "WEEKLY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, start, stop, type, name) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, start, stop, "WEEKLY", name])

    conn.commit()
    conn.close()

    service()


@plugin.route('/record_daily/<channelid>/<channelname>/<title>/<start>/<stop>')
def record_daily(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

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


@plugin.route('/record_weekly/<channelid>/<channelname>/<title>/<start>/<stop>')
def record_weekly(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

    start = timestamp2datetime(float(start))
    stop = timestamp2datetime(float(stop))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND start=? AND stop =? AND type=?', (channelid, channelname, title, start, stop, "WEEKLY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, title, start, stop, "WEEKLY"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/record_always/<channelid>/<channelname>/<title>')
def record_always(channelid, channelname, title):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

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

    title = xbmcgui.Dialog().input("IPTV Recorder: " + _("Title Search (% is wildcard)?")).decode("utf8")
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

    description = xbmcgui.Dialog().input("IPTV Recorder: " + _("Plot Search (% is wildcard)?")).decode("utf8")
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
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

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


@plugin.route('/watch_weekly/<channelid>/<channelname>/<title>/<start>/<stop>')
def watch_weekly(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

    start = timestamp2datetime(float(start))
    stop = timestamp2datetime(float(stop))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND start=? AND stop =? AND type=?', (channelid, channelname, title, start, stop, "WATCH WEEKLY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, title, start, stop, "WATCH WEEKLY"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/watch_always/<channelid>/<channelname>/<title>')
def watch_always(channelid, channelname, title):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

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

    title = xbmcgui.Dialog().input("IPTV watcher: " + _("Title Search (% is wildcard)?")).decode("utf8")
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

    description = xbmcgui.Dialog().input("IPTV watcher: " + _("Plot Search (% is wildcard)?")).decode("utf8")
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
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

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


@plugin.route('/remind_weekly/<channelid>/<channelname>/<title>/<start>/<stop>')
def remind_weekly(channelid, channelname, title, start, stop):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

    start = timestamp2datetime(float(start))
    stop = timestamp2datetime(float(stop))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    #TODO problem with PRIMARY KEYS, UNIQUE and TIMESTAMP
    rule = cursor.execute('SELECT * FROM rules WHERE channelid=? AND channelname=? AND title=? AND start=? AND stop =? AND type=?', (channelid, channelname, title, start, stop, "REMIND WEEKLY")).fetchone()

    if not rule:
        conn.execute("INSERT OR REPLACE INTO rules(channelid, channelname, title, start, stop, type) VALUES(?, ?, ?, ?, ?, ?)",
        [channelid, channelname, title, start, stop, "REMIND WEEKLY"])

    conn.commit()
    conn.close()

    service()


@plugin.route('/remind_always/<channelid>/<channelname>/<title>')
def remind_always(channelid, channelname, title):
    channelid = channelid.decode("utf8")
    channelname = channelname.decode("utf8")
    title = title.decode("utf8")
    title = xbmcgui.Dialog().input(_("% is Wildcard"), title).decode("utf8")

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

    title = xbmcgui.Dialog().input("IPTV reminder: " + _("Title Search (% is wildcard)?")).decode("utf8")
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

    description = xbmcgui.Dialog().input("IPTV reminder: " + _("Plot Search (% is wildcard)?")).decode("utf8")
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


@plugin.route('/broadcast/<programmeid>/<channelname>')
def broadcast(programmeid, channelname):
    channelname = channelname.decode("utf8")
    #log(channelname)

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programme = cursor.execute('SELECT channelid, title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", episode FROM programmes WHERE uid=? LIMIT 1', (programmeid, )).fetchone()
    channelid, title, start, stop, episode = programme

    channel = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE name=?", (channelname,)).fetchone()
    if not channel:
        channel = cursor.execute("SELECT * FROM channels WHERE tvg_name=?", (channelname, )).fetchone()
        uid, tvg_id, name, tvg_logo = channel
        url = ""
    else:
        uid, name, tvg_name, tvg_id, tvg_logo, groups, url = channel
    thumbnail = tvg_logo
    if not channelname:
        channelname = name

    echannelid = channelid.encode("utf8")
    echannelname = channelname.encode("utf8")
    etitle = title.encode("utf8")

    items = []

    items.append({
        'label': _("Record Once") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start), utc2local(stop)),
        'path': plugin.url_for(record_once, programmeid=programmeid, channelid=echannelid, channelname=echannelname),
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
        'label': _("Record Weekly") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time()),
        'path': plugin.url_for(record_weekly, channelid=echannelid, channelname=echannelname, title=etitle, start=start_ts, stop=stop_ts),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })
    items.append({
        'label': _("Watch Once") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start), utc2local(stop)),
        'path': plugin.url_for(watch_once, programmeid=programmeid, channelid=echannelid, channelname=echannelname),
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
        'label': _("Watch Weekly") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time()),
        'path': plugin.url_for(watch_weekly, channelid=echannelid, channelname=echannelname, title=etitle, start=start_ts, stop=stop_ts),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })

    items.append({
        'label': _("Remind Once") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start), utc2local(stop)),
        'path': plugin.url_for(remind_once, programmeid=programmeid, channelid=echannelid, channelname=echannelname),
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
        'label': _("Remind Weekly") + " - %s - %s %s[COLOR grey]%s - %s[/COLOR]" % (channelname, title, CR, utc2local(start).time(), utc2local(stop).time()),
        'path': plugin.url_for(remind_weekly, channelid=echannelid, channelname=echannelname, title=etitle, start=start_ts, stop=stop_ts),
        'thumbnail': thumbnail or get_icon_path('recordings'),
    })
    items.append({
        'label': _("Play Channel") + " - %s" % (channelname),
        'path': plugin.url_for(play_channel, channelname=echannelname),
        'thumbnail': thumbnail or get_icon_path('tv'),
        'info_type': 'video',
        'info':{"title": channelname},
        'is_playable': True,
    })

    if plugin.get_setting('external.player', str):
        items.append({
            'label': _("Play Channel External") + " - %s" % (channelname),
            'path': plugin.url_for(play_channel_external, channelname=echannelname),
            'thumbnail': thumbnail or get_icon_path('tv'),
            'info_type': 'video',
            'info':{"title": channelname},
            'is_playable': True,
        })

    if xbmc.getCondVisibility('System.HasAddon(%s)' % plugin.get_setting('meta', str)) == 1:
        icon = xbmcaddon.Addon(plugin.get_setting('meta', str)).getAddonInfo('icon')
        name = xbmcaddon.Addon(plugin.get_setting('meta', str)).getAddonInfo('name')
        if episode:
            #log((channelname,channelid,title,episode))
            tvdb_url = "http://thetvdb.com/api/GetSeries.php?seriesname=%s&language=en" % title
            #log(tvdb_url)
            data = requests.get(tvdb_url).text
            found = False
            if data:
                match = re.search('seriesid>(.*?)<',data)
                if match:
                    tvdb_id = match.group(1)
                    match = re.search('S(\d+)E(\d+)',episode,flags=re.I)
                    if match:
                        found = True
                        season = match.group(1)
                        ep = match.group(2)
                        meta_url = "plugin://%s/tv/play/%s/%d/%d/library" % (plugin.get_setting('meta', str).lower(),tvdb_id,int(season),int(ep))
                        items.append({
                            'label': "%s - %s %s" % (name,title,episode),
                            'path': meta_url,
                            'thumbnail': icon,
                        })
            if not found:
                meta_url = "plugin://%s/tv/search_term/%s/1" % (plugin.get_setting('meta', str).lower(),quote_plus(title.encode("utf8")))
                items.append({
                    'label': "%s - %s" % (name,title),
                    'path': meta_url,
                    'thumbnail': icon,
                })
        else:
            meta_url = "plugin://%s/movies/search_term/%s/1" % (plugin.get_setting('meta', str).lower(),quote_plus(title.encode("utf8")))
            items.append({
                'label': "%s - Movie - %s" % (name,title),
                'path': meta_url,
                'thumbnail': icon,
            })
            meta_url = "plugin://%s/tv/search_term/%s/1" % (plugin.get_setting('meta', str).lower(),quote_plus(title.encode("utf8")))
            items.append({
                'label': "%s - TV Show - %s" % (name,title),
                'path': meta_url,
                'thumbnail': icon,
            })
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
        #log(search)
        context_items.append((_("Delete Search"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_title, title=search.encode("utf8")))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_title', title=search.encode("utf-8")),
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
    #log(what)
    if not what:
        return
    searches[what] = ''
    return search_title(what.encode("utf-8"))


@plugin.route('/search_title/<title>')
def search_title(title):
    title = title.decode("utf8")

    if plugin.get_setting('add.context.searches', str) == 'true':
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
        context_items.append(("Delete Search" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_search_plot, plot=search.encode("utf8")))))
        items.append({
            "label": search,
            "path": plugin.url_for('search_plot', plot=search.encode("utf8")),
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
    what = d.input(_("Search Plot"), plot).decode("utf8")
    if not what:
        return
    searches[what] = ''
    return search_plot(what.encode("utf8"))


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

    if plugin.get_setting('add.context.searches', str) == 'true':
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


@plugin.route('/channel/<channelid>/<channelname>')
def channel(channelid,channelname):
    channelid = channelid.decode("utf8")
    echannelname = channelname
    channelname = channelname.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    thumbnail = cursor.execute("SELECT tvg_logo FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
    if not thumbnail:
        thumbnail = cursor.execute("SELECT icon FROM channels WHERE id=?", (channelid, )).fetchone()
    if thumbnail:
        thumbnail = thumbnail[0]
    else:
        thumbnail = ''

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE channelid=?', (channelid, )).fetchall()

    conn.commit()
    conn.close()

    if plugin.get_setting('add.favourite.channel', str) == 'true':
        add_favourite_channel(channelname.encode("utf8"), channelid.encode("utf8"), thumbnail)

    return listing(programmes, scroll=True, channelname=echannelname)


@plugin.route('/tv_show/<title>')
def tv_show(title):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=? ORDER BY start, channelid, title', (title, )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/other/<title>')
def other(title):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE episode IS null AND title=? ORDER BY start, channelid, title', (title, )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


@plugin.route('/category/<title>')
def category(title):
    title = title.decode("utf8")

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    programmes = cursor.execute(
    'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE categories LIKE ? ORDER BY start, channelid, title', ("%"+title+"%", )).fetchall()

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
        'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=? AND date=? ORDER BY start, channelid, title', (title, date)).fetchall()
    else:
        programmes = cursor.execute(
        'SELECT uid, channelid , title , sub_title , start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", date , description , episode, categories FROM programmes WHERE title=? ORDER BY start, channelid, title', (title, )).fetchall()

    conn.commit()
    conn.close()

    return listing(programmes, scroll=True)


def listing(programmes, scroll=False, channelname=None):
    if channelname:
        channelname = unquote_plus(channelname.decode("utf8"))

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    streams = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams").fetchall()
    #streams = {x[3]:x for x in streams}
    streams = dict((x[3],x) for x in streams)

    channels = cursor.execute("SELECT * FROM channels").fetchall()
    #channels = {x[1]:x for x in channels}
    channels = dict((x[1],x) for x in channels)

    items = []

    now = datetime.now()

    current = None

    i = 1
    for p in programmes:
        pchannelname = cchannelname = schannelname = ""
        uid, channelid , title , sub_title , start , stop , date , description , episode, categories = p

        if channelname:
            pchannelname = channelname

        stream = streams.get(channelid)
        channel = channels.get(channelid)
        if stream:
            cuid, schannelname, tvg_name, tvg_id, tvg_logo, groups, url = stream
            thumbnail = tvg_logo or channel[3]
            if not channelname:
                pchannelname = schannelname
        elif channel:
            uid, tvg_id, cchannelname, tvg_logo = channel
            url = ""
            thumbnail = tvg_logo
            if not channelname:
                pchannelname = cchannelname
        else:
            continue
        #log((channelname,pchannelname,cchannelname,schannelname))

        jobs = cursor.execute("SELECT uuid, type FROM jobs WHERE channelid=? AND channelname=? AND start=? AND stop=?", (channelid, pchannelname, start, stop)).fetchall()
        if jobs:
            types = []
            for uuid, type in jobs:
                types.append(type)
            recording = "[COLOR red]%s[/COLOR]" % ', '.join(types)
        else:
            recording = ""

        starttime = utc2local(start)
        endtime = utc2local(stop)

        if plugin.get_setting('show.categories', str) == 'true':
            categories_label = "[COLOR grey]%s[/COLOR]" % categories
        else:
            categories_label = ""

        if endtime < now:
            color = "orange"
            if plugin.get_setting('show.finished', str) == 'false':
                continue
        else:
            if current == None:
                current = i
            color = "yellow"
        i += 1

        if episode and not episode.startswith('M'):
            episode = " "+ episode + " "
        else:
            episode = " "

        if sub_title:
            stitle = "[COLOR %s]%s[/COLOR][COLOR grey]%s- %s[/COLOR]" % (color, title, episode, sub_title)
        else:
            stitle = "[COLOR %s]%s[/COLOR][COLOR grey]%s[/COLOR]" % (color, title, episode)

        if (plugin.get_setting('hide.channel.name', str) == "true") and thumbnail:
            channelname_label = ""
        else:
            channelname_label = unquote_plus(pchannelname)

        label = "%02d:%02d [COLOR grey]%s[/COLOR] %s %s %s%s %s" % (starttime.hour, starttime.minute, day(starttime), channelname_label, categories_label, CR, stitle, recording)

        context_items = []

        echannelid = channelid.encode("utf8")
        echannelname=pchannelname.encode("utf8")
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
                (plugin.url_for(record_once, programmeid=uid, channelid=echannelid, channelname=echannelname))))
                context_items.append((_("Watch Once"), 'XBMC.RunPlugin(%s)' %
                (plugin.url_for(watch_once, programmeid=uid, channelid=echannelid, channelname=echannelname))))
                context_items.append((_("Remind Once"), 'XBMC.RunPlugin(%s)' %
                (plugin.url_for(remind_once, programmeid=uid, channelid=echannelid, channelname=echannelname))))

        if url:
            context_items.append((_("Play Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel, channelname=echannelname))))
            if plugin.get_setting('external.player', str):
                context_items.append((_("Play Channel External"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external, channelname=echannelname))))

        context_items.append((echannelname, 'ActivateWindow(%s,%s,return)' % (xbmcgui.getCurrentWindowId(), plugin.url_for('channel', channelid=echannelid, channelname=echannelname))))
        context_items.append((etitle, 'ActivateWindow(%s,%s,return)' % (xbmcgui.getCurrentWindowId(), plugin.url_for('search_title', title=etitle))))
        if ecategories:
            context_items.append((ecategories, 'ActivateWindow(%s,%s,return)' % (xbmcgui.getCurrentWindowId(), plugin.url_for('search_categories', categories=ecategories))))

        if url:
            path = plugin.url_for(broadcast, programmeid=uid, channelname=echannelname)
        else:
            path = plugin.url_for('channel', channelid=echannelid, channelname=echannelname)

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

    if scroll and plugin.get_setting('scroll.now', str) == 'true':
        threading.Thread(target=focus,args=[current]).start()

    return items


def focus(i):

    #TODO find way to check this has worked (clist.getSelectedPosition returns -1)
    xbmc.sleep(int(plugin.get_setting('scroll.ms', str) or "0"))
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


@plugin.route('/remove_load_group/<channelgroup>')
def remove_load_group(channelgroup):
    load_groups = plugin.get_storage('load_groups')
    if channelgroup in load_groups:
        del load_groups[channelgroup]

    if xbmcgui.Dialog().yesno("IPTV Recorder","Reload xmltv data now?"):
        full_service()


@plugin.route('/add_load_group/<channelgroup>')
def add_load_group(channelgroup):
    load_groups = plugin.get_storage('load_groups')
    load_groups[channelgroup] = ""

    if xbmcgui.Dialog().yesno("IPTV Recorder","Reload xmltv data now?"):
        full_service()


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

    order_settings = plugin.get_setting('sort.channels.v2', str)
    if order_settings == '1':
        order_channels = " ORDER by name"
        order_favourites = " ORDER by channelname"
        order_stream = " ORDER by name"
    else:
        order_channels = " INNER JOIN streams ON streams.tvg_id = channels.id ORDER BY tv_number";
        order_favourites = " INNER JOIN streams ON streams.tvg_id = favourites.channelid ORDER BY tv_number";
        order_stream = " ORDER by tv_number"

    logos = {}
    channel_logos = {}
    if section == "EPG":
        channels = cursor.execute("SELECT channels.id, channels.name, channels.icon FROM channels" + order_channels).fetchall()
        streams = cursor.execute("SELECT tvg_id, tvg_logo FROM streams").fetchall()
        #logos = {x[0]:x[1] for x in streams}
        logos = dict((x[0],x[1]) for x in streams)

        collection = channels
        show_now_next = plugin.get_setting('show.now.next.all', str) == "true"
    elif section == "FAVOURITES":
        favourite_channels = cursor.execute("SELECT channelname, channelid, logo FROM favourites" + order_favourites).fetchall()
        streams = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams" + order_stream).fetchall()
        collection = favourite_channels
        show_now_next = plugin.get_setting('show.now.next.favourites', str) == "true"
    else:
        channels = cursor.execute("SELECT * FROM channels" + order_channels).fetchall()
        #channel_logos = {x[1]:x[3] for x in channels}
        channel_logos = dict((x[1],x[3]) for x in channels)
        if channelgroup == "All_Channels":
            streams = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams" + order_stream).fetchall()
            show_now_next = plugin.get_setting('show.now.next.all', str) == "true"
        else:
            streams = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams WHERE groups=?" + order_stream, (channelgroup, )).fetchall()
            show_now_next = plugin.get_setting('show.now.next.lists', str) == "true"
        collection = streams

    favourites = cursor.execute("SELECT channelname FROM favourites").fetchall()
    favourites = [x[0] for x in favourites]

    all_streams = cursor.execute("SELECT uid, name, tvg_name, tvg_id, tvg_logo, groups, url FROM streams" + order_stream).fetchall()
    #stream_urls = {x[3]:x[6] for x in all_streams if x}
    stream_urls = dict((x[3],x[6]) for x in all_streams if x)

    items = []

    now = datetime.utcnow()

    if show_now_next:
        now_titles = cursor.execute('SELECT channelid, title, start AS "start [TIMESTAMP]", description, categories FROM programmes WHERE start<? AND stop>?', (now, now)).fetchall()
        #now_titles = {x[0]:(x[1],x[2],x[3],x[4]) for x in now_titles}
        now_titles = dict((x[0],(x[1],x[2],x[3],x[4])) for x in now_titles)
        #TODO limit to one per channelid
        next_titles = cursor.execute('SELECT channelid, title, start AS "start [TIMESTAMP]", categories FROM programmes WHERE start>? ORDER BY start DESC', (now,)).fetchall()
        #next_titles = {x[0]:(x[1],x[2],x[3]) for x in next_titles}
        next_titles = dict((x[0],(x[1],x[2],x[3])) for x in next_titles)

    for stream_channel in collection:
        #log(stream_channel)

        url = ""
        if section == "EPG":
            id, name, icon = stream_channel
            channelname = name
            channelid = id
            url = stream_urls.get(channelid)
            thumbnail = logos.get(channelid) or icon or get_icon_path('tv')
            logo = icon
        elif section == "FAVOURITES":
            channelname, channelid, thumbnail = stream_channel
            url = stream_urls.get(channelid)
            logo = thumbnail
            thumbnail = logo or get_icon_path('tv')
        else:
            uid, name, tvg_name, tvg_id, tvg_logo, groups, url = stream_channel
            channelname = name or tvg_name
            channelid = tvg_id
            #if not channelid:
                #continue
            thumbnail = tvg_logo or logos.get(channelid) or channel_logos.get(channelid) or get_icon_path('tv')
            logo = tvg_logo

            #channelname = channelname.encode("ascii")
            #channelname = channelname.decode("utf8")

        description = ""
        categories = ""

        if show_now_next:

            if channelid in now_titles:
                title = now_titles[channelid][0]
                local_start = utc2local(now_titles[channelid][1])
                description = now_titles[channelid][2]
                if plugin.get_setting('show.categories', str) == 'true':
                    categories = "[COLOR grey]%s[/COLOR]" % now_titles[channelid][3]
                else:
                    categories = ""
                now_title = "[COLOR yellow]%02d:%02d %s[/COLOR] %s" % (local_start.hour, local_start.minute, title, categories)
            else:
                now_title = ""

            if channelid in next_titles:
                title = next_titles[channelid][0]
                local_start = utc2local(next_titles[channelid][1])
                if plugin.get_setting('show.categories', str) == 'true':
                    next_categories = "[COLOR grey]%s[/COLOR]" % next_titles[channelid][2]
                else:
                    next_categories = ""
                next_title =  "[COLOR blue]%02d:%02d %s[/COLOR] %s" % (local_start.hour, local_start.minute, title, next_categories)
            else:
                next_title = ""

            if plugin.get_setting('show.now.next.hide.empty', str) == "true" and not now_title and not next_title:
                continue

            if (plugin.get_setting('hide.channel.name', str) == "true") and logo:
                label = "%s %s%s" % (now_title, CR, next_title)
            else:
                label = u"%s %s %s%s" % (channelname, now_title, CR, next_title)


        else:
            label = channelname

        context_items = []

        channelname_encoded = channelname.encode("utf8")
        if channelid:
            channelid_encoded = channelid.encode("utf8")

        if url:
            context_items.append((_("Add One Time Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_one_time, channelname=channelname_encoded))))
            context_items.append((_("Add Daily Time Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_daily_time, channelname=channelname_encoded))))
            context_items.append((_("Add Weekly Time Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_weekly_time, channelname=channelname_encoded))))
            context_items.append((_("Record and Play"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_and_play, channelname=channelname_encoded))))
            if channelid:
                context_items.append((_("Add Title Search Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search, channelid=channelid_encoded, channelname=channelname_encoded))))
                context_items.append((_("Add Plot Search Rule"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_always_search_plot, channelid=channelid_encoded, channelname=channelname_encoded))))
            context_items.append((_("Play Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel, channelname=channelname_encoded))))
            if plugin.get_setting('external.player', str):
                context_items.append((_("Play Channel External"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_channel_external, channelname=channelname_encoded))))

        if channelname not in favourites and channelid:
            context_items.append((_("Add Favourite Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_channel, channelname=channelname_encoded, channelid=channelid_encoded, thumbnail=thumbnail))))
        else:
            context_items.append((_("Remove Favourite Channel"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_channel, channelname=channelname_encoded))))

        if url and channelid:
            path = plugin.url_for(channel, channelid=channelid_encoded, channelname=channelname_encoded)
        else:
            path = sys.argv[0]

        items.append({
            'label': label,
            'path': path,
            'context_menu': context_items,
            'thumbnail': thumbnail,
            'info':{"plot":description, "genre":categories}
        })

    return items


@plugin.route('/groups')
def groups():
    items = []
    load_groups = plugin.get_storage('load_groups')

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    channelgroups = cursor.execute("SELECT DISTINCT groups FROM streams ORDER BY groups").fetchall()

    for channelgroup in [("All_Channels", )] + channelgroups:
        channelgroup = channelgroup[0]

        if not channelgroup:
            continue

        context_items = []
        if channelgroup not in load_groups:
            context_items.append((_("Load Group"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_load_group, channelgroup=channelgroup.encode("utf8")))))
        else:
            context_items.append((_("Do Not Load Group"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_load_group, channelgroup=channelgroup.encode("utf8")))))

        channel_name = channelgroup
        if channel_name == "All_Channels":
            channel_name = _("All Channels")
        items.append({
            'label': channel_name,
            'path': plugin.url_for(group, channelgroup=channelgroup.encode("utf8")),
            'thumbnail': get_icon_path('folder'),
            'context_menu': context_items,
        })

    return items


@plugin.route('/tv')
def tv():
    items = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    titles = cursor.execute('SELECT DISTINCT title FROM programmes WHERE episode IS NOT null AND episode IS NOT "MOVIE" AND start>? ORDER BY title', (datetime.utcnow(), )).fetchall()

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

    titles = cursor.execute('SELECT DISTINCT title, date FROM programmes WHERE episode IS "MOVIE" AND start>? ORDER BY title', (datetime.utcnow(), )).fetchall()

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

    titles = cursor.execute('SELECT DISTINCT title,episode FROM programmes WHERE episode IS null AND start>? ORDER BY title', (datetime.utcnow(), )).fetchall()

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


    titles = cursor.execute('SELECT DISTINCT categories FROM programmes WHERE start>? ORDER BY categories', (datetime.utcnow(), )).fetchall()

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

    rules = cursor.execute('SELECT uid, channelid, channelname, title, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]", description, type, name FROM rules ORDER by channelname, title, start, stop').fetchall()

    for uid, jchannelid, jchannelname, jtitle, jstart, jstop, jdescription, jtype, jname  in rules:

        if jtitle and '%' in jtitle:
            compare='LIKE'
        else:
            compare='='

        watch = False
        remind = False
        if jtype.startswith("WATCH"):
            jtype = jtype.replace("WATCH ","")
            watch = True
        elif jtype.startswith("REMIND"):
            jtype = jtype.replace("REMIND ","")
            remind = True

        if jtype == "ALWAYS":
            #TODO scrub [] from title

            programmes = cursor.execute(
            'SELECT uid, channelid , title , sub_title , date , description , episode, categories FROM programmes WHERE channelid=? AND title %s ?' % compare,
            (jchannelid, jtitle)).fetchall()

            for p in programmes:
                uid, channel , title , sub_title , date , description , episode, categories = p
                record_once(programmeid=uid, channelid=jchannelid.encode("utf8"), channelname=jchannelname.encode("utf8"), do_refresh=False, watch=watch, remind=remind)

        elif jtype == "DAILY":
            if jtitle:
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
                        record_once(programmeid=uid, channelid=jchannelid.encode("utf8"), channelname=jchannelname.encode("utf8"), do_refresh=False, watch=watch, remind=remind)
            else:
                tjstart = jstart.time()
                tjstop = jstop.time()

                utcnow = datetime.utcnow()
                start = utcnow.replace(hour=tjstart.hour, minute=tjstart.minute, second=0, microsecond=0)
                stop = utcnow.replace(hour=tjstop.hour, minute=tjstop.minute, second=0, microsecond=0)
                if stop < start:
                    stop = stop + timedelta(days=1)

                for days in range(0,2):
                    start = start + timedelta(days=days)
                    stop = stop + timedelta(days=days)
                    if stop > start:
                        if jchannelid:
                            jchannelid = jchannelid.encode("utf8")
                        record_once_time(jchannelid, jchannelname.encode("utf8"), start, stop, do_refresh=False, watch=watch, remind=remind, title=jname)

        elif jtype == "WEEKLY":
            if jtitle:
                tjstart = jstart.time()
                tjstop = jstop.time()
                tjstart_day = jstart.weekday()

                programmes = cursor.execute(
                'SELECT uid, start AS "start [TIMESTAMP]", stop AS "stop [TIMESTAMP]" FROM programmes WHERE channelid=? AND title %s ?' % compare,
                (jchannelid, jtitle)).fetchall()

                for p in programmes:
                    uid, start, stop = p
                    tstart_day = start.weekday()
                    tstart = start.time()
                    tstop = stop.time()
                    if tjstart_day == tstart_day and tjstart == tstart and tjstop == tstop:
                        record_once(programmeid=uid, channelid=jchannelid.encode("utf8"), channelname=jchannelname.encode("utf8"), do_refresh=False, watch=watch, remind=remind)
            else:
                tjstart = jstart.time()
                tjstop = jstop.time()

                utcnow = datetime.utcnow()
                start = utcnow.replace(hour=tjstart.hour, minute=tjstart.minute, second=0, microsecond=0)
                while (start < utcnow):
                    start = start + timedelta(weeks=1)
                stop = utcnow.replace(hour=tjstop.hour, minute=tjstop.minute, second=0, microsecond=0)
                if stop < start:
                    stop = stop + timedelta(days=1)

                for weeks in range(0,2):
                    start = start + timedelta(weeks=weeks)
                    stop = stop + timedelta(weeks=weeks)
                    if stop > start:
                        #log((jchannelid,jchannelname))
                        if jchannelid:
                            jchannelid = jchannelid.encode("utf8")
                        record_once_time(jchannelid, jchannelname.encode("utf8"), start, stop, do_refresh=False, watch=watch, remind=remind, title=jname)

        elif jtype == "SEARCH":
            programmes = cursor.execute("SELECT uid FROM programmes WHERE channelid=? AND title LIKE ?", (jchannelid, "%"+jtitle+"%")).fetchall()
            for p in programmes:
                uid = p[0]
                record_once(programmeid=uid, channelid=jchannelid.encode("utf8"), channelname=jchannelname.encode("utf8"), do_refresh=False, watch=watch, remind=remind)

        elif jtype == "PLOT":
            programmes = cursor.execute("SELECT uid FROM programmes WHERE channelid=? AND description LIKE ?", (jchannelid, "%"+jdescription+"%")).fetchall()
            for p in programmes:
                uid = p[0]
                record_once(programmeid=uid, channelid=jchannelid.encode("utf8"), channelname=jchannelname.encode("utf8"), do_refresh=False, watch=watch, remind=remind)

    refresh()


@plugin.route('/delete_recording/<label>/<path>')
def delete_recording(label, path):
    label = label.decode("utf8")
    if not (xbmcgui.Dialog().yesno("IPTV Recorder", "[COLOR red]" + _("Delete Recording?") + "[/COLOR]", label)):
        return
    xbmcvfs.delete(path)
    length = int(len('.' + plugin.get_setting('ffmpeg.ext', str)))
    xbmcvfs.delete(path[:-length]+'.json')
    refresh()


@plugin.route('/delete_all_recordings')
def delete_all_recordings():
    result = xbmcgui.Dialog().yesno("IPTV Recorder", "[COLOR red]" + _("Delete All Recordings?") + "[/COLOR]")
    if not result:
        return

    dir = plugin.get_setting('recordings', str)
    dirs, files = find(dir)
    for file in sorted(files):
        if file.endswith('.' + plugin.get_setting('ffmpeg.ext', str)):
            success = xbmcvfs.delete(file)
            if success:
                length = int(len('.' + plugin.get_setting('ffmpeg.ext', str)))
                json_file = file[:-length]+'.json'
                xbmcvfs.delete(json_file)

    rmdirs(dir)
    refresh()


def find_files(root):
    dirs, files = xbmcvfs.listdir(root)
    found_files = []
    for dir in dirs:
        path = os.path.join(xbmc.translatePath(root), dir)
        found_files = found_files + find_files(path)
    file_list = []
    for file in files:
        if file.endswith('.' + plugin.get_setting('ffmpeg.ext', str)):
            file = os.path.join(xbmc.translatePath(root), file)
            file_list.append(file)
    return found_files + file_list


@plugin.route('/recordings')
def recordings():
    dir = plugin.get_setting('recordings', str)
    found_files = find_files(dir)

    items = []
    starts = []

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    for path in found_files:
        thumbnail = None
        try:
            json_file = path[:-3]+'.json'
            info = json.loads(xbmcvfs.File(json_file).read())
            programme = info["programme"]

            channelid = programme.get('channelid', None)
            title = programme['title']
            sub_title = programme['sub_title'] or ''
            episode = programme['episode']
            date = programme.get('date', '')
            if date is None:
                date = ''
            else:
                date = "(%s) " % programme.get('date', '')

            start = programme['start']
            starts.append(start)

            stream_found = cursor.execute("SELECT tvg_logo FROM streams WHERE tvg_id=?", (channelid, )).fetchone()
            if stream_found:
                thumbnail = stream_found[0]

            if episode and episode != "MOVIE":
                label = "%s%s [COLOR grey]%s[/COLOR] %s" % (date, title, episode, sub_title)
            elif episode == "MOVIE":
                label = "%s%s" % (date, title)
            else:
                label = "%s%s %s" % (date, title, sub_title)

            description = programme['description']
        except:
            label = os.path.splitext(os.path.basename(path))[0]
            description = ""
            starts.append("0")
            label = unquote_plus(label)
            label = label.decode("utf8")

        context_items = []

        context_items.append((_("Delete Recording"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_recording, label=label.encode("utf8"), path=path))))
        context_items.append((_("Delete All Recordings"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_recordings))))
        if plugin.get_setting('external.player', str):
            context_items.append((_("External Player"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_external, path=path))))
        #context_items.append((_("Convert to mp4"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(convert, path=path))))

        items.append({
            'thumbnail': thumbnail,
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
    return sorted(items, key=lambda k: k['label'].lower())


def xml2utc(xml):
    if len(xml) == 14:
        xml = xml + " +0000"
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

def find_xml_bytes_encoding(data_bytes):
    data_test_decoding = data_bytes.decode('utf-8', errors='ignore')
    index_end_first_line = data_test_decoding.find('\n')
    match = None
    if index_end_first_line != -1:
        first_line = data_test_decoding[:index_end_first_line]
        match = re.search('<\?xml.*?encoding=["\'](.*?)["\']', first_line, flags=(re.I|re.DOTALL))

    if match:
        encoding = match.group(1)
    else:
        # Improve performance by limiting the detection of the encoding
        # to the first 50k characters if the XML file is bigger
        if len(data_bytes) > 50000:
            chardet_encoding = chardet.detect(data_bytes[:50000])
        else:
            chardet_encoding = chardet.detect(data_bytes)
        encoding = chardet_encoding['encoding']

    return encoding

@plugin.route('/xmltv')
def xmltv():
    load_groups = plugin.get_storage('load_groups')
    load_channels = {}

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
    conn.execute('CREATE TABLE IF NOT EXISTS rules(uid INTEGER PRIMARY KEY ASC, channelid TEXT, channelname TEXT, title TEXT, sub_title TEXT, start TIMESTAMP, stop TIMESTAMP, date TEXT, description TEXT, episode TEXT, categories TEXT, type TEXT, name TEXT)')
    try: conn.execute('ALTER TABLE rules ADD COLUMN name TEXT')
    except: pass
    #TODO check primary key
    conn.execute('CREATE TABLE IF NOT EXISTS streams(uid INTEGER PRIMARY KEY ASC, name TEXT, tvg_name TEXT, tvg_id TEXT, tvg_logo TEXT, groups TEXT, url TEXT, tv_number INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS favourites(channelname TEXT, channelid TEXT, logo TEXT, PRIMARY KEY(channelname))')
    conn.execute('CREATE TABLE IF NOT EXISTS jobs(uid INTEGER PRIMARY KEY ASC, uuid TEXT, channelid TEXT, channelname TEXT, title TEXT, start TIMESTAMP, stop TIMESTAMP, type TEXT)')

    shifts = {}

    for x in ["1","2"]:

        dialog.update(0, message=_("Finding streams"))
        mode = plugin.get_setting('external.m3u.'+x, str)
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
            path = plugin.get_setting('external.m3u.file.'+x, str)
        else:
            path = plugin.get_setting('external.m3u.url.'+x, str)

        if path:

            m3uFile = 'special://profile/addon_data/plugin.video.iptv.recorder/channels'+x+'.m3u'

            xbmcvfs.copy(path, m3uFile)
            f = open(xbmc.translatePath(m3uFile),'rb')
            data = f.read()
            if "m3u8" in path.lower():
                data = data.decode('utf8')
                #log("m3u8")
            else:
                encoding = chardet.detect(data)
                log(encoding)
                data = data.decode(encoding['encoding'])

            settings_shift = float(plugin.get_setting('external.m3u.shift.'+x, str))
            global_shift = settings_shift

            header = re.search('#EXTM3U(.*)', data)
            if header:
                tvg_shift = re.search('tvg-shift="(.*?)"', header.group(1))
                if tvg_shift:
                    tvg_shift = tvg_shift.group(1)
                    if tvg_shift:
                        global_shift = float(tvg_shift) + settings_shift

            channels = re.findall('#EXTINF:(.*?)(?:\r\n|\r|\n)(.*?)(?:\r\n|\r|\n|$)', data, flags=(re.I | re.DOTALL))
            total = len(channels)
            i = 0
            for channel in channels:

                name = None
                if ',' in re.sub('tvg-[a-z]+"[^"]*"','',channel[0], flags=re.I):
                    name = channel[0].rsplit(',', 1)[-1].strip()
                    #name = name.encode("utf8")

                tvg_name = re.search('tvg-name="(.*?)"', channel[0], flags=re.I)
                if tvg_name:
                    tvg_name = tvg_name.group(1) or None
                #else:
                    #tvg_name = name

                tvg_id = re.search('tvg-id="(.*?)"', channel[0], flags=re.I)
                if tvg_id:
                    tvg_id = tvg_id.group(1) or None

                tvg_logo = re.search('tvg-logo="(.*?)"', channel[0], flags=re.I)
                if tvg_logo:
                    tvg_logo = tvg_logo.group(1) or None

                shifts[tvg_id] = global_shift
                tvg_shift = re.search('tvg-shift="(.*?)"', channel[0], flags=re.I)
                if tvg_shift:
                    tvg_shift = tvg_shift.group(1)
                    if tvg_shift and tvg_id:
                        shifts[tvg_id] = float(tvg_shift) + settings_shift

                url = channel[1]
                search = plugin.get_setting('m3u.regex.search', str)
                replace = plugin.get_setting('m3u.regex.replace', str)
                if search:
                    url = re.sub(search, replace, url)

                groups = re.search('group-title="(.*?)"', channel[0], flags=re.I)
                if groups:
                    groups = groups.group(1) or None

                conn.execute("INSERT OR IGNORE INTO streams(name, tvg_name, tvg_id, tvg_logo, groups, url, tv_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [name, tvg_name, tvg_id, tvg_logo, groups, url.strip(), i])

                i += 1
                percent = 0 + int(100.0 * i / total)
                dialog.update(percent, message=_("Finding streams"))

    for x in ["1","2"]:

        mode = plugin.get_setting('external.xmltv.'+x, str)
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
            path = plugin.get_setting('external.xmltv.file.'+x, str)
        else:
            path = plugin.get_setting('external.xmltv.url.'+x, str)

        if path:

            tmp = os.path.join(profilePath, 'xmltv'+x+'.tmp')
            xml = os.path.join(profilePath, 'xmltv'+x+'.xml')
            dialog.update(0, message=_("Copying xmltv file"))
            xbmcvfs.copy(path, tmp)

            f = xbmcvfs.File(tmp, "rb")
            data_bytes = bytes(f.readBytes())
            f.close()
            magic = data_bytes[:3]
            if magic == "\x1f\x8b\x08":
                dialog.update(0, message=_("Unzipping xmltv file"))
                compressedFile = StringIO()
                compressedFile.write(data_bytes)
                compressedFile.seek(0)
                decompressedFile = gzip.GzipFile(fileobj=compressedFile, mode='rb')
                data_bytes = decompressedFile.read()
                f = xbmcvfs.File(xml, "wb")
                f.write(bytearray(data_bytes))
                f.close()
            else:
                xbmcvfs.copy(tmp, xml)

            f = xbmcvfs.File(xml, 'rb')
            data_bytes = bytes(f.readBytes())
            f.close()

            encoding = find_xml_bytes_encoding(data_bytes)
            data = data_bytes.decode(encoding)

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

    '''
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
    '''
    if len(load_groups.keys()) == 0:
        load_all = True
    else:
        load_all = False

    channels = conn.execute("SELECT tvg_id, groups FROM streams").fetchall()
    for tvg_id, groups in channels:
        if groups in load_groups:
            load_channels[tvg_id] = ""

    for x in ["1","2"]:

        mode = plugin.get_setting('external.xmltv.'+x, str)
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
            path = plugin.get_setting('external.xmltv.file.'+x, str)
        else:
            path = plugin.get_setting('external.xmltv.url.'+x, str)

        if path:

            xml = os.path.join(profilePath, 'xmltv'+x+'.xml')

            f = xbmcvfs.File(xml, 'rb')
            data_bytes = bytes(f.readBytes())
            f.close()

            encoding = find_xml_bytes_encoding(data_bytes)
            data = data_bytes.decode(encoding)

            htmlparser = HTMLParser()

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
                        if load_all == False and channel not in load_channels:
                            continue

                    if channel in shifts:
                        shift = shifts[channel]
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
                    search = plugin.get_setting('xmltv.title.regex.search', str)
                    replace = plugin.get_setting('xmltv.title.regex.replace', str)
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
                    else:
                        date = start

                    cats = re.findall('<category.*?>(.*?)</category>', m, flags=(re.I|re.DOTALL))
                    if cats:
                        categories = htmlparser.unescape((', '.join(cats)))
                    else:
                        categories = ''
                    cats = categories.lower()
                    film_movie = ("movie" in cats) or ("film" in cats)

                    #TODO other systems
                    episode = re.findall('<episode-num system="(.*?)">(.*?)<', m, flags=(re.I|re.DOTALL))
                    #episode = {x[0]:x[1] for x in episode}
                    episode = dict((x[0],x[1]) for x in episode)

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


@plugin.route('/search_index')
def search_index():
    items = []
    context_items = []

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

    return items


@plugin.route('/browse_index')
def browse_index():
    items = []
    context_items = []

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

    return items


@plugin.route('/maintenance_index')
def maintenance_index():
    items = []
    context_items = []

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

    if plugin.get_setting('debug', str) == "true":
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
        if xbmc.getCondVisibility('system.platform.android'):
            items.append(
            {
                'label': _("Delete ffmpeg"),
                'path': plugin.url_for('delete_ffmpeg'),
                'thumbnail':get_icon_path('settings'),
                'context_menu': context_items,
            })

    return items

@plugin.route('/select_groups')
def select_groups():
    load_groups = plugin.get_storage('load_groups')
    load_groups.clear()

    conn = sqlite3.connect(xbmc.translatePath('%sxmltv.db' % plugin.addon.getAddonInfo('profile')), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    channelgroups = cursor.execute("SELECT DISTINCT groups FROM streams ORDER BY groups").fetchall()
    channelgroups = [x[0] for x in channelgroups]

    selection = xbmcgui.Dialog().multiselect('Do Not Load Groups',channelgroups)
    if selection:
        for index in selection:
            group = channelgroups[index]
            load_groups[group] = ""

    load_groups.sync()

    if xbmcgui.Dialog().yesno("IPTV Recorder","Reload xmltv data now?"):
        full_service()


@plugin.route('/estuary')
def estuary():
    xbmc.startServer(xbmc.SERVER_WEBSERVER, True,True)
    try:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","id":1,"params":{"setting":"lookandfeel.skin","value":"skin.estouchy"}}')
    except:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","id":1,"params":{"setting":"lookandfeel.skin","value":"skin.confluence"}}')
    xbmc.executebuiltin( 'XBMC.ReloadSkin()' )

    from_path = xbmc.translatePath('special://xbmc/addons/skin.estuary')
    to_path = xbmc.translatePath('special://home/addons/skin.estuary.iptv.recorder')
    #log((from_path,to_path))
    if os.path.exists(to_path):
        #TODO warning
        shutil.rmtree(to_path)
        time.sleep(1)
    shutil.copytree(from_path, to_path)

    filename = xbmc.translatePath('special://home/addons/skin.estuary.iptv.recorder/addon.xml')
    with open(filename,'r') as f:
        text = f.read().decode('utf-8')
    text = text.replace('skin.estuary','skin.estuary.iptv.recorder').replace('Estuary','Estuary (IPTV Recorder)')
    with open(filename,'w') as f:
        write_in_file(f, text)

    files = glob.glob(os.path.join(to_path,'language','*','*.po'))
    for filename in files:
        with open(filename,'r') as f:
            text = f.read().decode('utf-8')
        text = text.replace('skin.estuary','skin.estuary.iptv.recorder')
        with open(filename,'w') as f:
            write_in_file(f, text)

    filename = xbmc.translatePath('special://home/addons/skin.estuary.iptv.recorder/xml/DialogPVRInfo.xml')
    with open(filename,'r') as f:
        text = f.read().decode('utf-8')
    text = text.replace('<control type="grouplist" id="9000">',
    '''<control type="grouplist" id="9000">
					<include content="InfoDialogButton">
						<param name="width" value="275" />
						<param name="id" value="666" />
						<param name="icon" value="icons/infodialogs/record.png" />
						<param name="label" value="IPTV Recorder" />
						<param name="onclick_1" value="Action(close)" />
						<param name="onclick_2" value="RunScript(plugin.video.iptv.recorder,$ESCINFO[ListItem.ChannelName],$ESCINFO[ListItem.Title],$ESCINFO[ListItem.Date],$ESCINFO[ListItem.Duration],$ESCINFO[ListItem.Plot])" />
						<param name="visible" value="System.hasAddon(plugin.video.iptv.recorder)" />
					</include>
					<include content="InfoDialogButton">
						<param name="width" value="275" />
						<param name="id" value="667" />
						<param name="icon" value="icons/infodialogs/record.png" />
						<param name="label" value="Recordings" />
						<param name="onclick_1" value="Action(close)" />
						<param name="onclick_2" value="ActivateWindow(10025,&quot;plugin://plugin.video.iptv.recorder/recordings&quot;,return)" />
						<param name="visible" value="System.hasAddon(plugin.video.iptv.recorder)" />
					</include>''')
    with open(filename,'w') as f:
        write_in_file(f, text)

    xbmc.executebuiltin("UpdateLocalAddons")
    time.sleep(1)

    try:
        params = '"method":"Addons.SetAddonEnabled","params":{"addonid":"skin.estuary.iptv.recorder","enabled":true}'
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", %s, "id": 1}' % params)
        xbmc.executebuiltin("ActivateWindow(10040,addons://user/xbmc.gui.skin,return)")
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","id":1,"params":{"setting":"lookandfeel.skin","value":"skin.estuary.iptv.recorder"}}')
        xbmc.executebuiltin('SendClick(11)')
        time.sleep(1)
        xbmc.executebuiltin( 'XBMC.ReloadSkin()' )
    except:
        d.ok("IPTV Recorder","Kodi web interface wasn't enabled. Restart Kodi and Enable Skin in My Addons.")
        xbmc.executebuiltin("ActivateWindow(10040,addons://user/xbmc.gui.skin,return)")
    xbmcgui.Dialog().notification("IPTV Recorder", "Estuary (IPTV Recorder) created")
    plugin.set_setting('show.skin','false')


def get_free_space_mb(dirname):
    """Return folder/drive free space (in megabytes)."""
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(dirname), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / 1024 / 1024
    else:
        try:
            st = os.statvfs(dirname)
            return st.f_bavail * st.f_frsize / 1024 / 1024
        except:
            #log(dirname)
            return


@plugin.route('/')
def index():
    items = []
    context_items = []



    if plugin.get_setting('show.skin', bool):
        items.append(
        {
            'label': "[COLOR yellow]NEW! Create Estuary (IPTV Recorder) Skin[/COLOR]",
            'path': plugin.url_for('estuary'),
            'thumbnail':get_icon_path('popular'),
            'context_menu': context_items,
        })

    items.append(
    {
        'label': _("Favourite Channels"),
        'path': plugin.url_for('favourite_channels'),
        'thumbnail':get_icon_path('favourites'),
        'context_menu': context_items,
    })

    context_items = []
    context_items.append((_("Select Groups To Load"), 'XBMC.RunPlugin(%s)' % (plugin.url_for(select_groups))))
    items.append(
    {
        'label': _("Channel Groups"),
        'path': plugin.url_for('groups'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    context_items = []

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
        'path': plugin.get_setting('recordings', str),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Browse"),
        'path': plugin.url_for('browse_index'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Search"),
        'path': plugin.url_for('search_index'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Maintenance"),
        'path': plugin.url_for('maintenance_index'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': _("Full EPG"),
        'path': plugin.url_for('epg'),
        'thumbnail':get_icon_path('folder'),
        'context_menu': context_items,
    })

    free = get_free_space_mb(xbmc.translatePath(plugin.get_setting('recordings', str)))
    if free:
        items.append(
        {
            'label': "[COLOR dimgray]%d MB Free[/COLOR]" % free,
            'path': plugin.url_for('recordings'),
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

            view_mode = int(plugin.get_setting('view.mode', str) or "0")

            if view_mode:
                plugin.set_view_mode(view_mode)
