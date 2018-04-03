# IPTV Recorder
## plugin.video.iptv.recorder

Kodi addon for recording streams from the IPTV Simple Client pvr plugin or xmltv/m3u files.

Adding recording from the IPTV Simple Client is possible and has been done but it is too hard for most people to build for their devices.

This addon is an easily extensible python addon that should work with any device.

You will need a version of ffmpeg for your device. 

https://ffmpeg.org/

Android builds are here: https://github.com/WritingMinds/ffmpeg-android/releases/latest

On Android this addon will copy ffmpeg to the /data/data folder so it can run.

### Quick Start

* Install this addon via my repo. 
https://github.com/primaeval/repository.primaeval/raw/master/zips/repository.primaeval/repository.primaeval-0.0.2.zip
* Download ffmpeg for your device
* Point to the ffmpeg exe in Settings.
* Make sure IPTV Simple Client is enabled and works or point to your xmltv/m3u in Settings\Data.
* Go into the addon \ Channel Groups and find a program to Record.

### TODO

* cron jobs on Linux.
