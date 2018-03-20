from xbmcswift2 import Plugin
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import random
import urllib
import sqlite3
import time
import threading
import json
import os,os.path
import stat
import subprocess
from datetime import datetime,timedelta
import uuid

from struct import *
from collections import namedtuple


plugin = Plugin()
big_list_view = False



def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')

def log(v):
    xbmc.log(repr(v),xbmc.LOGERROR)


def get_icon_path(icon_name):
    if plugin.get_setting('user.icons') == "true":
        user_icon = "special://profile/addon_data/%s/icons/%s.png" % (addon_id(),icon_name)
        if xbmcvfs.exists(user_icon):
            return user_icon
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(),icon_name)

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

def delete(path):
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        xbmcvfs.delete(path+file)
    for dir in dirs:
        delete(path + dir + '/')
    xbmcvfs.rmdir(path)



@plugin.route('/play/<channelid>')
def play(channelid):
    rpc = '{"jsonrpc":"2.0","method":"Player.Open","id":305,"params":{"item":{"channelid":%s}}}' % channelid
    r = requests.post('http://localhost:8080/jsonrpc',data=rpc)
    log(r)
    log(r.content)

@plugin.route('/play_name/<channelname>')
def play_name(channelname):
    channel_urls = plugin.get_storage("channel_urls")
    url = channel_urls.get(channelname)
    if url:
        cmd = ["ffplay",url]
        subprocess.Popen(cmd)


def utc2local (utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset

def str2dt(string_date):
    format ='%Y-%m-%d %H:%M:%S'
    try:
        res = datetime.strptime(string_date, format)
    except TypeError:
        res = datetime(*(time.strptime(string_date, format)[0:6]))
    return utc2local(res)

def total_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6

@plugin.route('/record_once/<channelname>/<title>/<starttime>/<endtime>')
def record_once(channelname,title,starttime,endtime):
    channel_urls = plugin.get_storage("channel_urls")
    url = channel_urls.get(channelname)

    starttime = str2dt(starttime)
    endtime = str2dt(endtime)
    length = endtime - starttime
    seconds = total_seconds(length)
    log((starttime,endtime,length))
    filename = "%s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,title,starttime,endtime)
    filename = urllib.quote_plus(filename)+'.ts'
    path = os.path.join(xbmc.translatePath(r'c:\temp'),filename)

    cmd = ["ffmpeg","-y","-i",url,"-t",str(seconds),"-c","copy",path]
    log(cmd)
    #subprocess.Popen(cmd,shell=False)
    directory = "special://profile/addon_data/plugin.video.iptv.recorder/jobs/"
    xbmcvfs.mkdirs(directory)
    job = str(uuid.uuid1())
    py = directory + job + ".py"
    f = xbmcvfs.File(py,'wb')
    f.write("import subprocess\n")
    f.write("cmd = %s\n" % repr(cmd))
    f.write("subprocess.Popen(cmd,shell=True)\n")
    f.close()
    #pytask = "\"c:\\python27.64\\pythonw\" \"%s\"" % xbmc.translatePath(py)
    st = "%02d:%02d" % (starttime.hour,starttime.minute)
    cmd = ["schtasks","/create","/tn",job,"/sc","once","/st",st,"/tr",r"c:\python27.64\pythonw.exe %s" % xbmc.translatePath(py)]
    log(cmd)
    subprocess.Popen(cmd,shell=True)

@plugin.route('/record_once/<channelname>/<title>/<starttime>/<endtime>')
def record_daily(channelname,title,starttime,endtime):
    pass

@plugin.route('/record_whenever/<channelname>/<title>')
def record_always(channelname,title):
    pass

@plugin.route('/broadcast/<channelname>/<title>/<starttime>/<endtime>')
def broadcast(channelname,title,starttime,endtime):
    #log((channelname,title,starttime,endtime))
    items = []
    #TODO format dates
    items.append({
        'label': "Record Once - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,title,starttime,endtime),
        'path': plugin.url_for(record_once,channelname=channelname,title=title,starttime=starttime,endtime=endtime)
    })
    items.append({
        'label': "Record Daily - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,title,starttime,endtime),
        'path': plugin.url_for(record_daily,channelname=channelname,title=title,starttime=starttime,endtime=endtime)
    })
    items.append({
        'label': "Record Always - %s - %s" % (channelname,title),
        'path': plugin.url_for(record_always,channelname=channelname,title=title)
    })
    if False:
        items.append({
            'label': "Watch Once - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,title,starttime,endtime),
            'path': plugin.url_for(record_once,channelname=channelname,title=title,starttime=starttime,endtime=endtime)
        })
        items.append({
            'label': "Watch Daily - %s - %s[CR][COLOR grey]%s - %s[/COLOR]" % (channelname,title,starttime,endtime),
            'path': plugin.url_for(record_daily,channelname=channelname,title=title,starttime=starttime,endtime=endtime)
        })
        items.append({
            'label': "Watch Always - %s - %s" % (channelname,title),
            'path': plugin.url_for(record_always,channelname=channelname,title=title)
        })
    return items



@plugin.route('/channel/<channelname>/<channelid>')
def channel(channelname,channelid):
    rpc = '{"jsonrpc":"2.0","method":"PVR.GetBroadcasts","id":306,"params":{"channelid":%s,"properties":["title","plot","plotoutline","starttime","endtime","runtime","progress","progresspercentage","genre","episodename","episodenum","episodepart","firstaired","hastimer","isactive","parentalrating","wasactive","thumbnail","rating"]}}' % channelid
    r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
    content = r.content
    j = json.loads(content)
    log(j)
    broadcasts = j.get('result').get('broadcasts')
    if not broadcasts:
        return
    items = []
    for b in broadcasts:
        starttime = b.get('starttime')
        endtime = b.get('endtime')
        title = b.get('title')
        broadcastid=str(b.get('broadcastid'))
        #log(starttime)
        start = str2dt(starttime) # +  timedelta(seconds=-time.timezone) #TODO check summer time
        #log(start)
        label = "%02d:%02d %s" % (start.hour,start.minute,b.get('label'))
        context_items = []
        context_items.append(("Play RPC" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play,channelid=channelid))))
        context_items.append(("Play ffplay" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_name,channelname=channelname))))
        items.append({
            'label': label,
            'path': plugin.url_for(broadcast,channelname=channelname,title=title.encode("utf8"),starttime=starttime,endtime=endtime),
            'context_menu': context_items,
        })
    return items


@plugin.route('/group/<channelgroupid>')
def group(channelgroupid):
    channel_urls = plugin.get_storage("channel_urls")
    rpc = '{"jsonrpc":"2.0","method":"PVR.GetChannels","id":312,"params":{"channelgroupid":%s,"properties":["thumbnail","channeltype","hidden","locked","channel","lastplayed","broadcastnow","broadcastnext"]}}' % channelgroupid
    r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
    content = r.content
    j = json.loads(content)
    #log(j)
    channels = j.get('result').get('channels')
    items = []
    for c in channels:
        #log(c)
        label = c.get('label')
        channelname = c.get('channel')
        channelid = str(c.get('channelid'))
        #log((name,cid))
        context_items = []
        context_items.append(("Play RPC" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play,channelid=channelid))))
        context_items.append(("Play ffplay" , 'XBMC.RunPlugin(%s)' % (plugin.url_for(play_name,channelname=channelname))))
        items.append({
            'label': channelname,
            'path': plugin.url_for(channel,channelname=channelname,channelid=channelid),
            'context_menu': context_items,
            #'path': channel_urls[channelname],
            #'is_playable': True,
            #'info_type': 'Video',
            #'info':{"mediatype": "movie", "title": channelname}
        })
    return items

@plugin.route('/groups')
def groups():
    rpc = '{"jsonrpc":"2.0","method":"PVR.GetChannelGroups","id":311,"params":{"channeltype":"tv"}}'
    r = requests.get('http://localhost:8080/jsonrpc?request='+urllib.quote_plus(rpc))
    content = r.content
    j = json.loads(content)
    #log(j)
    channelgroups = j.get('result').get('channelgroups')
    items = []
    for channelgroup in channelgroups:
        log(channelgroup)
        items.append({
            'label': channelgroup.get('label'),
            'path': plugin.url_for(group,channelgroupid=str(channelgroup.get('channelgroupid')))

        })
    return items

@plugin.route('/m3u')
def m3u():
    m3uUrl = xbmcaddon.Addon('pvr.iptvsimple').getSetting('m3uUrl')
    #log(m3uUrl)
    m3uFile = 'special://profile/addon_data/plugin.video.iptv.recorder/channels.m3u'
    xbmcvfs.copy(m3uUrl,m3uFile)
    f = xbmcvfs.File(m3uFile)
    data = f.read()
    #log(data)
    channel_urls = plugin.get_storage("channel_urls")
    channel_urls.clear()
    channels = re.findall('#EXTINF:(.*?)\n(.*?)\n',data,flags=(re.I|re.DOTALL))
    for channel in channels:
        #log(channel)
        match = re.search('tvg-name="(.*?)"',channel[0])
        if match:
            name = match.group(1)
        else:
            name = channel[0].rsplit(',',1)[-1]
        url = channel[1]
        #log((name,url))
        channel_urls[name] = url
    channel_urls.sync()

@plugin.route('/service')
def service():
    log("SERVICE")

@plugin.route('/')
def index():
    items = []
    context_items = []

    items.append(
    {
        'label': "Channel Groups",
        'path': plugin.url_for('groups'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Load Channel m3u",
        'path': plugin.url_for('m3u'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Service",
        'path': plugin.url_for('service'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    return items

if __name__ == '__main__':
    plugin.run()
