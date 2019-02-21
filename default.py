import xbmc,xbmcgui,xbmcaddon,xbmcvfs,xbmcplugin
import sys
import time,datetime
import sqlite3
import pytz
import tzlocal
import re

def log(x):
    xbmc.log(repr(x),xbmc.LOGERROR)

def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]", '', label, flags=re.I)
    label = re.sub(r"\[/?COLOR.*?\]", '', label, flags=re.I)
    return label

channel = remove_formatting(sys.argv[1]).strip()
title = sys.argv[2]
date = sys.argv[3]
duration = sys.argv[4]
plot = sys.argv[5]

dateshort_format = xbmc.getRegion('dateshort')
time_format = xbmc.getRegion('time')
format = "%s %s" % (dateshort_format, time_format.replace(':%S',''))

start_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(date, format)))
timezone = tzlocal.get_localzone()
start_time = timezone.localize(start_time)
utc = pytz.timezone('utc')
start_time = start_time.astimezone(utc)
start_time = start_time.replace(tzinfo=None)

conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/plugin.video.iptv.recorder/xmltv.db'), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
cursor = conn.cursor()
try:
    channel_id = cursor.execute('SELECT tvg_id FROM streams WHERE name=?',(channel,)).fetchone()[0]
    program_id = cursor.execute('SELECT uid FROM programmes WHERE channelid=? AND start=?',(channel_id,start_time)).fetchone()[0]

    if program_id:
        xbmc.executebuiltin("ActivateWindow(videos,plugin://plugin.video.iptv.recorder/broadcast/%s/%s,return)" % (program_id,channel))
    else:
        xbmcgui.Dialog().notification("IPTV Recorder","program not found",xbmcgui.NOTIFICATION_WARNING)
except:
    xbmcgui.Dialog().notification("IPTV Recorder","program not found",xbmcgui.NOTIFICATION_WARNING)
