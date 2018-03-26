#! /usr/bin/python

__strings = {}

if __name__ == "__main__":
    import polib
    po = polib.pofile('resources/language/English/strings.po')

    try:
        import re
        import subprocess
        r = subprocess.check_output(["grep", "-hnr", "_([\'\"]", "."])
        strings = re.compile("_\([\"'](.*?)[\"']\)", re.IGNORECASE).findall(r)
        translated = [m.msgid.lower().replace("'", "\\'") for m in po]
        missing = set([s for s in strings if s.lower() not in translated])
        if missing:
            ids_range = range(30000, 31000)
            ids_reserved = [int(m.msgctxt[1:]) for m in po]
            ids_available = [x for x in ids_range if x not in ids_reserved]
            print "warning: missing translation for", missing
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
    import xbmc, xbmcaddon
    __language__ = xbmcaddon.Addon().getLocalizedString

    def get_string(t):
        id = __strings.get(t.lower())
        if id:
            return __language__(id)
        xbmc.log("missing translation for " + t.lower())
        return t
    #setattr(__builtin__, '_', get_string)

#GENERATED
__strings['delete job'] = 30000
