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
channel = urllib.quote(channel)
#log(("channel",channel))

try:

    d = xbmcgui.Dialog()
    select = d.select("IPTV Recorder",["Add Timed Recording","Add Daily Timed Recording","Record and Play"])

    if select != -1:
        if select == 0:
            cmd = "ActivateWindow(videos,plugin://plugin.video.iptv.recorder/record_one_time/%s,return)" % (channel)
            result = xbmc.executebuiltin(cmd)
        elif select == 1:
            cmd = "ActivateWindow(videos,plugin://plugin.video.iptv.recorder/record_daily_time/%s,return)" % (channel)
            result = xbmc.executebuiltin(cmd)
        elif select == 2:
            cmd = "ActivateWindow(videos,plugin://plugin.video.iptv.recorder/record_and_play/%s,return)" % (channel)
            result = xbmc.executebuiltin(cmd)

except:
    xbmcgui.Dialog().notification("IPTV Recorder","channel not found",xbmcgui.NOTIFICATION_WARNING)

