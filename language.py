#! /usr/bin/python
from __future__ import unicode_literals

__strings = {}

if __name__ == "__main__":
    import polib
    import traceback
    po = polib.pofile('resources/language/English/strings.po')

    try:
        import os
        import re
        import subprocess

        strings = []
        regex_to_found = re.compile("_\([\"'](.*?)[\"']\)", re.IGNORECASE)
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(".py"):
                    with open(os.path.join(root, file), "r", encoding="utf-8") as file_content:
                        for line in file_content:
                            strings_found = regex_to_found.findall(line)
                            if strings_found:
                                strings.extend(strings_found)

        translated = [m.msgid.lower().replace("'", "\\'") for m in po]
        missing = set([s for s in strings if s.lower() not in translated])
        if missing:
            ids_range = range(30000, 31000)
            ids_reserved = [int(m.msgctxt[1:]) for m in po]
            ids_available = [x for x in ids_range if x not in ids_reserved]
            print("New text to translate found : %s" % missing)
            for text in missing:
                id = ids_available.pop(0)
                entry = polib.POEntry(
                    msgid=text,
                    msgstr=u'',
                    msgctxt="#{0}".format(id)
                )
                po.append(entry)
            po.save('resources/language/English/strings.po')
    except:
        traceback.print_exc()
        pass

    content = []
    with open(__file__, "r") as me:
        content = me.readlines()
        content = content[:content.index("#GENERATED\n")+1]

    with open(__file__, 'w') as f:
        f.writelines(content)
        for m in po:
            line = "__strings['{0}'] = {1}\n".format(m.msgid.lower().replace("'", "\\'"), m.msgctxt.replace('#', '').strip())
            f.write(line)
else:
    from kodi_six import xbmc, xbmcaddon
    __language__ = xbmcaddon.Addon().getLocalizedString

    def get_string(t):
        id = __strings.get(t.lower())
        if id:
            return __language__(id)
        xbmc.log("missing translation for " + t.lower())
        return t
    #setattr(__builtin__, '_', get_string)

#GENERATED
__strings['delete all recordings?'] = 30000
__strings['play channel'] = 30001
__strings['delete job'] = 30002
__strings['finished'] = 30003
__strings['record once'] = 30004
__strings['play channel external'] = 30005
__strings['external player'] = 30006
__strings['title search (% is wildcard)?'] = 30007
__strings['delete all jobs'] = 30008
__strings['search plot'] = 30009
__strings['add favourite channel'] = 30010
__strings['delete all rules'] = 30011
__strings['recording rules'] = 30012
__strings['favourite channels'] = 30013
__strings['delete all recordings'] = 30014
__strings['full epg'] = 30015
__strings['search title'] = 30016
__strings['xmltv'] = 30017
__strings['delete search'] = 30018
__strings['cancel record?'] = 30019
__strings['delete recording?'] = 30020
__strings['new'] = 30021
__strings['remove favourite channel'] = 30022
__strings['recording jobs'] = 30023
__strings['plot search (% is wildcard)?'] = 30024
__strings['add title search rule'] = 30025
__strings['add plot search rule'] = 30026
__strings['delete all rules?'] = 30027
__strings['recordings folder'] = 30028
__strings['ffmpeg exe not found!'] = 30029
__strings['tomorrow'] = 30030
__strings['today'] = 30031
__strings['delete rule'] = 30032
__strings['channel groups'] = 30033
__strings['loading data...'] = 30034
__strings['cancel record'] = 30035
__strings['service'] = 30036
__strings['delete recording'] = 30037
__strings['yesterday'] = 30038
__strings['delete all jobs?'] = 30039
__strings['recordings'] = 30040
__strings['record always'] = 30041
__strings['record daily'] = 30042
__strings['creating database'] = 30043
__strings['copying xmltv file'] = 30044
__strings['unzipping xmltv file'] = 30045
__strings['finding channels'] = 30046
__strings['finding programmes'] = 30047
__strings['finding streams'] = 30048
__strings['nuke'] = 30049
__strings['finished loading data'] = 30050
__strings['watch daily'] = 30051
__strings['delete everything and start again?'] = 30052
__strings['watch once'] = 30053
__strings['reload data'] = 30054
__strings['search categories'] = 30055
__strings['watch always'] = 30056
__strings['monday'] = 30057
__strings['tuesday'] = 30058
__strings['wednesday'] = 30059
__strings['thursday'] = 30060
__strings['friday'] = 30061
__strings['saturday'] = 30062
__strings['sunday'] = 30063
__strings['remind daily'] = 30064
__strings['rules'] = 30065
__strings['jobs'] = 30066
__strings['remind once'] = 30067
__strings['remind always'] = 30068
__strings['cancel watch'] = 30069
__strings['cancel remind'] = 30070
__strings['% is wildcard'] = 30071
__strings['search'] = 30072
__strings['tv shows'] = 30073
__strings['movies'] = 30074
__strings['do not load group'] = 30075
__strings['delete ffmpeg'] = 30076
__strings['add daily time rule'] = 30077
__strings['add weekly time rule'] = 30078
__strings['record and play'] = 30079
__strings['watch weekly'] = 30080
__strings['other'] = 30081
__strings['select groups to load'] = 30082
__strings['record weekly'] = 30083
__strings['maintenance'] = 30084
__strings['load group'] = 30085
__strings['browse'] = 30086
__strings['add one time rule'] = 30087
__strings['categories'] = 30088
__strings['remind weekly'] = 30089
__strings['convert to mp4'] = 30090
__strings['all channels'] = 30091
