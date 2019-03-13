import xbmc,xbmcgui,xbmcaddon,xbmcvfs,xbmcplugin
import sys
import time,datetime
import sqlite3
import pytz
import tzlocal
import re
import urllib

def log(x):
    xbmc.log(repr(x),xbmc.LOGERROR)

def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

def escape( str ):
    str = str.replace("&", "&amp;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    str = str.replace("\"", "&quot;")
    return str

def unescape( str ):
    str = str.replace("&lt;","<")
    str = str.replace("&gt;",">")
    str = str.replace("&quot;","\"")
    str = str.replace("&amp;","&")
    return str

window   = xbmcgui.getCurrentWindowId()

channel = xbmc.getInfoLabel('ListItem.Label')
#log(channel)
channel = channel.decode("utf8")
channel = channel.encode("utf8")
channel = urllib.quote_plus(channel)
#log(("channel",channel))

conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/plugin.video.iptv.recorder/xmltv.db'), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
cursor = conn.cursor()
try:
    channel_id = cursor.execute('SELECT tvg_id FROM streams WHERE name=?',(channel,)).fetchone()[0]
    #log(("channel_id",channel_id))

    d = xbmcgui.Dialog()
    select = d.select("IPTV Recorder",["Add Timed Recording","Add Daily Timed Recording","Record and Play"])

    if select != -1:
        if select == 0:
            cmd = "ActivateWindow(videos,plugin://plugin.video.iptv.recorder/record_one_time/%s/%s,return)" % (urllib.quote_plus(channel_id.encode("utf8")),channel)
            result = xbmc.executebuiltin(cmd)
        elif select == 1:
            cmd = "ActivateWindow(videos,plugin://plugin.video.iptv.recorder/record_daily_time/%s/%s,return)" % (urllib.quote_plus(channel_id.encode("utf8")),channel)
            result = xbmc.executebuiltin(cmd)
        elif select == 2:
            cmd = "ActivateWindow(videos,plugin://plugin.video.iptv.recorder/record_and_play/%s/%s,return)" % (urllib.quote_plus(channel_id.encode("utf8")),channel)
            result = xbmc.executebuiltin(cmd)

except:
    xbmcgui.Dialog().notification("IPTV Recorder","channel not found",xbmcgui.NOTIFICATION_WARNING)

