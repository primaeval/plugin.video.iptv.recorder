from xbmcswift2 import Plugin
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import random
import urllib
import sqlite3
import time,datetime
import threading
import json

import os,os.path

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

'''
    unsigned int    iClientIndex;                              /*!< @brief (required) the index of this timer given by the client. PVR_TIMER_NO_CLIENT_INDEX indicates that the index was not yet set by the client, for example for new timers created by
                                                                    Kodi and passed the first time to the client. A valid index must be greater than PVR_TIMER_NO_CLIENT_INDEX. */
    unsigned int    iParentClientIndex;                        /*!< @brief (optional) for timers scheduled by a repeating timer, the index of the repeating timer that scheduled this timer (it's PVR_TIMER.iClientIndex value). Use PVR_TIMER_NO_PARENT
                                                                    to indicate that this timer was no scheduled by a repeating timer. */
    int             iClientChannelUid;                         /*!< @brief (optional) unique identifier of the channel to record on. PVR_TIMER_ANY_CHANNEL will denote "any channel", not a specific one. PVR_CHANNEL_INVALID_UID denotes that channel uid is not available.*/
    time_t          startTime;                                 /*!< @brief (optional) start time of the recording in UTC. Instant timers that are sent to the add-on by Kodi will have this value set to 0.*/
    time_t          endTime;                                   /*!< @brief (optional) end time of the recording in UTC. */
    bool            bStartAnyTime;                             /*!< @brief (optional) for EPG based (not Manual) timers indicates startTime does not apply. Default = false */
    bool            bEndAnyTime;                               /*!< @brief (optional) for EPG based (not Manual) timers indicates endTime does not apply. Default = false */
    PVR_TIMER_STATE state;                                     /*!< @brief (required) the state of this timer */
    unsigned int    iTimerType;                                /*!< @brief (required) the type of this timer. It is private to the addon and can be freely defined by the addon. The value must be greater than PVR_TIMER_TYPE_NONE.
                                                                    Kodi does not interpret this value (except for checking for PVR_TIMER_TYPE_NONE), but will pass the right id to the addon with every PVR_TIMER instance, thus the addon easily can determine
                                                                    the timer type. */
    char            strTitle[PVR_ADDON_NAME_STRING_LENGTH];    /*!< @brief (required) a title for this timer */
    char            strEpgSearchString[PVR_ADDON_NAME_STRING_LENGTH]; /*!< @brief (optional) a string used to search epg data for repeating epg-based timers. Format is backend-dependent, for example regexp */
    bool            bFullTextEpgSearch;                        /*!< @brief (optional) indicates, whether strEpgSearchString is to match against the epg episode title only or also against "other" epg data (backend-dependent) */
    char            strDirectory[PVR_ADDON_URL_STRING_LENGTH]; /*!< @brief (optional) the (relative) directory where the recording will be stored in */
    char            strSummary[PVR_ADDON_DESC_STRING_LENGTH];  /*!< @brief (optional) the summary for this timer */
    int             iPriority;                                 /*!< @brief (optional) the priority of this timer */
    int             iLifetime;                                 /*!< @brief (optional) lifetime of recordings created by this timer. > 0 days after which recordings will be deleted by the backend, < 0 addon defined integer list reference, == 0 disabled */
    int             iMaxRecordings;                            /*!< @brief (optional) maximum number of recordings this timer shall create. > 0 number of recordings, < 0 addon defined integer list reference, == 0 disabled */
    unsigned int    iRecordingGroup;                           /*!< @brief (optional) integer ref to addon/backend defined list of recording groups*/
    time_t          firstDay;                                  /*!< @brief (optional) the first day this timer is active, for repeating timers */
    unsigned int    iWeekdays;                                 /*!< @brief (optional) week days, for repeating timers */
    unsigned int    iPreventDuplicateEpisodes;                 /*!< @brief (optional) 1 if backend should only record new episodes in case of a repeating epg-based timer, 0 if all episodes shall be recorded (no duplicate detection). Actual algorithm for
                                                                    duplicate detection is defined by the backend. Addons may define own values for different duplicate detection algorithms, thus this is not just a bool.*/
    unsigned int    iEpgUid;                                   /*!< @brief (optional) EPG event id associated with this timer. Event ids must be unique for a channel. Valid ids must be greater than EPG_TAG_INVALID_UID. */
    unsigned int    iMarginStart;                              /*!< @brief (optional) if set, the backend starts the recording iMarginStart minutes before startTime. */
    unsigned int    iMarginEnd;                                /*!< @brief (optional) if set, the backend ends the recording iMarginEnd minutes after endTime. */
    int             iGenreType;                                /*!< @brief (optional) genre type */
    int             iGenreSubType;                             /*!< @brief (optional) genre sub type */
    char            strSeriesLink[PVR_ADDON_URL_STRING_LENGTH]; /*!< @brief (optional) series link for this timer. If set for an epg-based timer rule, matching events will be found by checking strSeriesLink instead of strTitle (and bFullTextEpgSearch) */


'''
#I I i I I i i i I 1024s 1024s i 1024s 1024s i i i I i I I I I I i i 1024s
@plugin.route('/service')
def service():
    log("XXX")
    path = "special://temp/timers/"
    dirs, files = xbmcvfs.listdir(path)
    i = 1000
    for file in files:
        f = xbmcvfs.File(path+file,'rb')
        timer = f.read()
        #log(timer)
        #log(len(timer))
        #log(timer)
        f.close()
        fmt = '@I I iqqbbiI  1024s1024sb1024s1024s iiiIqII IIIii1024s 4x'

        #log(calcsize(fmt))
        Timer = namedtuple('Timer', 'iClientIndex iParentClientIndex iClientChannelUid startTime endTime bStartAnyTime bEndAnyTime state iTimerType strTitle strEpgSearchString bFullTextEpgSearch strDirectory strSummary iPriority iLifetime iMaxRecordings iRecordingGroup firstDay iWeekdays iPreventDuplicateEpisodes iEpgUid iMarginStart iMarginEnd iGenreType iGenreSubType strSeriesLink')
        t = Timer._make(unpack(fmt, timer))
        #print t
        #for k,v in t._asdict().iteritems():
        #    print k + ":" + repr(v)
        t = t._replace(iClientIndex = i)
        data = pack(fmt, *t)
        #log(data)
        f = xbmcvfs.File(path+file,'wb')
        f.write(data)
        f.close()
        i += 1
        startTime = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=t.startTime)
        endTime = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=t.endTime)
        #log(start)

        #AlarmClock(name,command,time[,silent,loop])
        dt = startTime - datetime.datetime.now()
        alarmTime = ((dt.days * 86400) + dt.seconds) / 60
        alarmTime = 1
        name = "alarm %s" % i
        pluginUrl = "plugin://plugin.video.iptv.recorder/record/%s" % i
        xbmc.executebuiltin('AlarmClock(%s,RunPlugin(%s),%s)' % (name,pluginUrl,alarmTime))


@plugin.route('/record/<id>')
def record(id):
    log("ZZZ record %s" % id)

@plugin.route('/')
def index():
    items = []
    context_items = []

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
