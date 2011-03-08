#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import types
from PyQt4 import QtCore, QtGui
from mpd import MPDClient, MPDError
from PyKDE4 import kdecore, kdeui
import socket


### Two classes to use to refactor.

class TimeSpan(object):
    """
    A span of time
    """
    
    def __init__(self, second_count):
        """
        Creates a timespan with the specified # of seconds.
        """
        self.second_count = int(second_count)
    
    def __str__(self):

        """
        Returns a string representation of the timespan,
        in a music player-friendly format.
        """

        seconds = self.second_count % 60
        minutes = self.second_count % 3600 / 60
        hours = self.second_count / 3600
        
        value = None
        if hours == 0 and minutes == 0:
            value = '0:{0:02}'.format(seconds)
        elif hours == 0:
            value = '{0:02}:{1:02}'.format(minutes, seconds)
        else:
            value = '{0}:{1:02}:{1:02}'.format(hours, minutes, seconds)
        return value
    
    def __repr__(self):
        
        """
        Returns the number of seconds.
        """

        return repr(self.second_count)
    
    def __lt__(self, other):
        
        """ a < b """

        return self.second_count < other.second_count
    
    def __le__(self, other):

        """ a <= b """

        return self.second_count <= other.second_count
    
    def __eq__(self, other):

        """ a == b """
        
        return self.second_count == other.second_count
    
    def __ne__(self, other):

        """ a != b """

        return self.second_count != other.second_count
    
    def __gt__(self, other):

        """ a > b """

        return self.second_count > other.second_count
    
    def __ge__(self, other):

        """ a >= b """

        return self.second_count >= other.second_count
    
    def __hash__(self):

        """ Returns the hash code. """

        return hash(self.second_count)

class SanitizedClient(object):

    """
    Decorates an MPDClient, sanitizing its outputs into
    the appropriate types.
    """

    def __init__(self, client):

        """
        Creates a SanitizedClient that wraps the
        specified client.
        """

        self.__mutex = QtCore.QMutex()

        self.__sanitizers = {}
        self.__sanitizers['songid'] = int
        self.__sanitizers['playlistlength'] = int
        self.__sanitizers['playlist'] = int
        self.__sanitizers['song'] = int
        self.__sanitizers['songs'] = int
        self.__sanitizers['xfade'] = int
        self.__sanitizers['volume'] = int
        self.__sanitizers['nextsong'] = int
        self.__sanitizers['nextsongid'] = int
        self.__sanitizers['bitrate'] = int
        self.__sanitizers['id'] = int
        self.__sanitizers['pos'] = int
        self.__sanitizers['artists'] = int
        self.__sanitizers['albums'] = int
        self.__sanitizers['songs'] = int
        self.__sanitizers['cpos'] = int
        self.__sanitizers['outputid'] = int
        self.__sanitizers['outputenabled'] = int
        self.__sanitizers['uptime'] = TimeSpan
        self.__sanitizers['db_update'] = TimeSpan
        self.__sanitizers['playtime'] = TimeSpan
        self.__sanitizers['db_playtime'] = TimeSpan
        self.__sanitizers['repeat'] = bool
        self.__sanitizers['consume'] = bool
        self.__sanitizers['random'] = bool
        self.__sanitizers['single'] = bool
        self.__sanitizers['track'] = self.__sanitized_track
        self.__sanitizers['audio'] = self.__sanitize_audio
        self.__sanitizers['time'] = self.__sanitize_time
        self.__sanitizers['title'] = self.__sanitize_tag
        self.__sanitizers['author'] = self.__sanitize_tag
        self.__sanitizers['album'] = self.__sanitize_tag
        self.__sanitizers['genre'] = self.__sanitize_tag
        self.__sanitizers['album'] = self.__sanitize_tag
        self.__sanitizers['composer'] = self.__sanitize_tag
        self.__sanitizers['mixrampdb'] = float
        self.__client = client
    
    @classmethod
    def __sanitize_audio(cls, value):
        """
        Sanitize the audio value.
        
        Example: 'audio': '44100:24:2'
        """
        return tuple(int(x) for x in value.split(':'))

    @classmethod
    def __sanitize_time(cls, value):
        """
        Returns the sanitized value of time.
        
        value might be in one of two formats:
            'time': '2:151' (elapsed:total)
            'time': '151' (total only)
        """
        
        if ':' in value:
            tokens = value.split(':')
            return tuple([TimeSpan(int(x)) for x in tokens])
        return TimeSpan(value)

    @classmethod
    def __sanitize_tag(cls, value):

        """
        Sanitizes a tag value, which may be a list.
        """

        if type(value) == list:
            value = ", ".join(set(value))
        return value
    
    @classmethod
    def __sanitized_track(cls, value):
        """
        Given a string value for a 'track' key, returns the
        int value (if possible).
        """
        end = 0
        result = value
        stripped = value.lstrip()
        for index, character in enumerate(stripped):
            end = index
            if not character.isdigit():
                break
        try:
            result = int(stripped[:end])
        except ValueError:
            pass
        return result

    def __command(self, method, *args):

        """
        Given an MPDClient method attribute
        and its arguments, executes it and
        sanitizes the output to the appropriate
        types.
        """

        QtCore.QMutexLocker(self.__mutex)

        result = method(*args)
        if type(result) == dict:
            self.__sanitize_dict(result)
        if type(result) == list:
            for item in result:
                if type(item) == dict:
                    self.__sanitize_dict(item)
        return result

    def __sanitize_dict(self, dictionary):
        """
        Given a dictionary returned by MPD, sanitizes
        its values to the appropriate types.
        """
        for key, value in dictionary.items():
            if key in self.__sanitizers:
                dictionary[key] = self.__sanitizers[key](value)
    
    def __getattr__(self, attr):
        attribute = getattr(self.__client, attr)
        if hasattr(attribute, "__call__"):
            return lambda *args: self.__command(attribute, *args)
        return attribute



### Production code begins here


class Parser(object):

    """
    The whole point of the SanitizedClient class is to
    deprecate this one.
    """

    @classmethod
    def isValid(cls, song):
        return "file" in song and len(song["file"].strip()) > 0

    @classmethod
    def hasKey(cls, song, key):
        return cls.isValid(song) and key in song

    @classmethod
    def valueList(cls, song, key):
        # Because tags may contain multiple values.
        # Assumes the key is there.
        values = set()

        if not cls.hasKey(song, key):
            return values

        if type(song[key]) == types.ListType:
            values = set()
            for value in song[key]:
                if len(value.strip()) > 0:
                    values.add(value)
        else:
            if len(song[key].strip()) > 0:
                values.add(song[key])
        return values

    @classmethod
    def match(cls, song, key, value):
        if not cls.hasKey(song, key):
            return False
        return value in cls.valueList(song, key)

    @classmethod
    def title(cls, song):
        if cls.hasKey(song, "title"):
            return song["title"]
        return os.path.splitext(os.path.basename(song["file"]))[0]

    @classmethod
    def length(cls, song):
        return cls.prettyTime(int(song["time"]))

    @classmethod
    def track(cls, song):
        # The "track" key is a freeform string and may or may not exist.
        # "1/12" and "1" are both common. We also check for malformed tags.

        NO_TRACK = 32768
        trackNo = 0

        if "track" in song:
            track = song["track"].strip()
            if len(track) > 0:
                found = False
                index = 0
                for i in xrange(len(track)):
                    if not track[i].isdigit():
                        index = i
                        found = True
                        break
                if found:
                    if len(track[0: index].strip()) > 0:
                        trackNo = int(track[0:index])
                    else:
                        trackNo = cls.NO_TRACK
                else:
                    trackNo = int(track)
            else:
                trackNo = NO_TRACK
        else:
            trackNo = NO_TRACK

        return trackNo

    @classmethod
    def total(cls, status):
        return int(status["time"][status["time"].index(":") + 1:])

    @classmethod
    def elapsed(cls, status):
        return int(status["time"][0:status["time"].index(":")])

    @classmethod
    def prettyTime(cls, time):
        seconds = time % 60
        minutes = (time % 3600) // 60
        hours = time // 3600

        pretty = str(seconds)
        if seconds < 10:
            pretty = "0" + pretty
        pretty = str(minutes) + ":" + pretty
        if time > 3600:
            if minutes < 10:
                pretty = "0" + pretty
            pretty = str(hours) + ":" + pretty
        return pretty

    @classmethod
    def prettyStatusTime(cls, status):
        return cls.prettyTime(cls.elapsed(status)) + "/" \
        + cls.prettyTime(cls.total(status))

    @classmethod
    def parsedValue(cls, song, key):
        # For the tooltips
        first = True
        valueString = ""
        for value in cls.valueList(song, key):
            if first:
                first = False
            else:
                valueString = valueString + ", "
            valueString = valueString + value.strip().decode("utf-8")
        return valueString


class Client(object):

    client = None

    @classmethod
    def create(cls):
        cls.client = MPDClient()

    @classmethod
    def delete(cls):
        cls.client = None

    @classmethod
    def exists(cls):
        return not cls.client is None

    @classmethod
    def cmd(cls, command, a = None, b = None, c = None):
        if c is not None:
            return getattr(cls.client, command)(str(a), str(b), str(c))
        if b is not None:
            return getattr(cls.client, command)(str(a), str(b))
        if a is not None:
            return getattr(cls.client, command)(str(a))
        return getattr(cls.client, command)()


class IdleThread(QtCore.QThread):

    def __init__(self, parent = None):
        super(IdleThread, self).__init__(parent)
        self.mpdClient = None

    @property
    def client(self):
        return self.mpdClient

    @client.setter
    def client(self, value):
        self.mpdClient = value

    def run(self):
        while (Client.exists()):
            playlists = None
            try:
                self.mpdClient.idle("stored_playlist")
                self.emit(QtCore.SIGNAL("playlists"),
                    self.mpdClient.listplaylists())
            except:
                pass


class Idler(QtCore.QObject):

    def __init__(self, parent = None):
        super(Idler, self).__init__(parent)
        self.options = Options()
        self.idleClient = None
        self.idleThread = None

    def start(self):
        self.idleClient = MPDClient()
        self.idleClient.connect(str(self.options.host), self.options.port)
        self.idleThread = IdleThread()
        if self.options.needPassword:
            self.idleClient.password(str(self.options.password))
        self.idleThread.client = self.idleClient
        self.connect(self.idleThread, QtCore.SIGNAL("playlists"),
            self.setPlaylistsChanged)
        self.idleThread.start()

    def stop(self):
        try:
            self.idleClient.noidle()
            self.idleClient.disconnect()
        except:
            pass

    def setPlaylistsChanged(self, playlists):
        sortedList = sorted(playlists, key = self.sortingKey)
        self.emit(QtCore.SIGNAL("playlists"), sortedList)

    def sortingKey(self, element):
        return element["playlist"].strip().lower()


class Options(object):

    def __init__(self):
        self.config = kdecore.KSharedConfig.openConfig("quetzalcoatlrc")
        self.connectionGroup = self.config.group("Connection")

    @property
    def host(self):
        return self.connectionGroup.readEntry("host", "localhost").toString()

    @host.setter
    def host(self, value):
        self.connectionGroup.writeEntry("host", value)

    @property
    def port(self):
        return self.connectionGroup.readEntry("port", 6600).toInt()[0]

    @port.setter
    def port(self, value):
        self.connectionGroup.writeEntry("port", value)

    @property
    def needPassword(self):
        return self.connectionGroup.readEntry("needPassword", False).toBool()

    @needPassword.setter
    def needPassword(self, value):
        self.connectionGroup.writeEntry("needPassword", value)

    @property
    def password(self):
        return self.connectionGroup.readEntry("password", "").toString()

    @password.setter
    def password(self, value):
        self.connectionGroup.writeEntry("password", value)

    def save(self):
        self.config.sync()


class Connector(QtCore.QObject):
    SECOND = 1000
    NOT_UPDATEABLE = False
    UPDATEABLE = True

    def __init__(self, parent):
        super(Connector, self).__init__(parent)
        self.connectables = []
        self.timer = QtCore.QTimer()
        self.connect(self.timer, QtCore.SIGNAL("timeout()"), self.update)
        self.idler = Idler()
        self.updateables = []
        self.options = Options()

    def toggleConnected(self):
        if Client.exists():
            self.disconnectFromClient()
        else:
            self.connectToClient()

    def connectToClient(self):
        Client.create()
        connected = False
        try:
            Client.cmd("connect", self.options.host, self.options.port)
            if self.options.needPassword:
                Client.cmd("password", self.options.password)
            connected = True
        except (MPDError, socket.error) as e:
            Client.delete()
            kdeui.KMessageBox.detailedError(self.parent(),\
            "Cannot connect to MPD", str(e), "Cannot Connect")

        if connected:
            for connectable in self.connectables:
                connectable.clientConnect()
            self.update()
            self.updatePlaylists()
            self.timer.start(Connector.SECOND)
            self.idler.start()

    def update(self):
        try:
            for updateable in self.updateables:
                if Client.exists():
                    updateable.update(Client.cmd("status"))
        except (MPDError, socket.error) as e:
            self.setBroken(e)

    def setBroken(self, e):
        self.disconnectFromClient()
        kdeui.KMessageBox.detailedError(self.parent(),\
        "Connection Lost", str(e), "Connection Lost")

    def disconnectFromClient(self):
        self.timer.stop()
        for connectable in self.connectables:
            connectable.clientDisconnect()
        self.playlistModel.clientDisconnect()
        try:
            Client.cmd("disconnect")
        except:
            pass
        Client.delete()
        self.idler.stop()

    def addConnectable(self, connectable, updateable = False):
        connectable.setConnector(self)
        self.connectables.append(connectable)
        if updateable:
            self.updateables.append(connectable)

    def updatePlaylists(self):
        try:
            if Client.exists():
                playlists = Client.cmd("listplaylists")
                sortedPlaylists = sorted(playlists, key = self.sortingKey)
                self.playlistModel.setPlaylists(sortedPlaylists)
        except (MPDError, socket.error) as e:
            self.setBroken(e)

    def addPlaylistModel(self, model):
        model.setConnector(self)
        self.playlistModel = model
        self.connect(self.idler, QtCore.SIGNAL("playlists"),
        self.playlistModel.setPlaylists)

    def sortingKey(self, element):
        return element["playlist"].strip().lower()


class Configurer(kdeui.KDialog):

    PLAYBACK_OPTIONS = 1

    def __init__(self, parent):
        super(Configurer, self).__init__(parent)
        self.options = Options()

        self.setWindowIcon(kdeui.KIcon("configure"))
        self.setCaption("Configure")
        self.tabs = kdeui.KTabWidget(self)
        connectionWidget = QtGui.QWidget()
        self.setMainWidget(self.tabs)
        self.tabs.addTab(connectionWidget, "Connection")
        layout = QtGui.QFormLayout(connectionWidget)

        self.setButtons(self.ButtonCode(\
        self.Cancel | self.Ok | self.Default))

        # http://forums.asp.net/p/1178692/1992103.aspx#1992103
        hostRx = QtCore.QRegExp("^[a-zA-Z0-9]+([a-zA-Z0-9\-\.]+)?\.(com|org|"
        "net|mil|edu|COM|ORG|NET|MIL|EDU)$")
        hostValidator = QtGui.QRegExpValidator(hostRx, self)
        self.host = kdeui.KLineEdit(self.options.host)
        self.host.setValidator(hostValidator)

        layout.addRow(self.tr("&Host:"), self.host)

        self.port = kdeui.KIntSpinBox(0, 65535, 1, self.options.port, self)
        layout.addRow(self.tr("&Port:"), self.port)
        self.pwCheck = QtGui.QCheckBox()
        layout.addRow(self.tr("&Use Password:"), self.pwCheck)
        self.password = kdeui.KLineEdit(self.options.password)
        self.password.setPasswordMode(True)
        layout.addRow(self.tr("Pass&word:"), self.password)

        self.connect(self.pwCheck, QtCore.SIGNAL("stateChanged(int)"),\
        self.togglePassword)

        self.connect(self, QtCore.SIGNAL("okClicked()"), self,\
        QtCore.SLOT("accept()"))
        self.connect(self, QtCore.SIGNAL("cancelClicked()"), self,\
        QtCore.SLOT("reject()"))
        self.connect(self, QtCore.SIGNAL("defaultClicked()"), self.defaults)

        playbackWidget = QtGui.QWidget()
        self.tabs.addTab(playbackWidget, "Playback")
        layout = QtGui.QFormLayout(playbackWidget)
        self.fade = kdeui.KIntSpinBox()
        self.fade.setMinimum(0)
        self.fade.setMaximum(20)
        layout.addRow("&Crossfade (in seconds)", self.fade)
        self.volume = kdeui.KIntSpinBox()
        self.volume.setMinimum(0)
        self.volume.setMaximum(100)
        layout.addRow("&Volume", self.volume)
        self.connect(self.tabs, QtCore.SIGNAL("currentChanged(int)"),\
        self.changeTabs)

    def changeTabs(self, index):
        if index == Configurer.PLAYBACK_OPTIONS:
            self.setup()

    def exec_(self):

        self.host.setText(self.options.host)
        self.port.setValue(self.options.port)
        self.pwCheck.setChecked(self.options.needPassword)
        self.password.setText(self.options.password)
        self.togglePassword()

        try:
            status = Client.cmd("status")
            self.fade.setEnabled(True)
            self.fade.setValue(int(status["xfade"]))
            self.volume.setEnabled(True)
            self.volume.setValue(int(status["volume"]))
        except:
            # If the client is not connected
            self.fade.setValue(0)
            self.fade.setEnabled(False)
            self.volume.setValue(0)
            self.volume.setEnabled(False)

        kdeui.KDialog.exec_(self)

    def togglePassword(self):
        self.password.setEnabled(self.pwCheck.isChecked())
        if not self.password.isEnabled():
            self.password.clear()

    def accept(self):
        self.options.port = self.port.value()
        self.options.host = self.host.text()
        self.options.password = self.password.text()
        self.options.needPassword = self.pwCheck.isChecked()
        self.options.save()

        try:
            if self.fade.isEnabled():
                Client.cmd("crossfade", self.fade.value())
        except:
            pass
        try:
            if self.volume.isEnabled():
                Client.cmd("volume", self.volume.value())
        except Exception as e:
            # Setting the volume doesn't work on my development system,
            # which uses OSS4.
            if "volume" in str(e):
                print str(e)

        QtGui.QDialog.accept(self)

    def defaults(self):
        self.host.setText("localhost")
        self.port.setText("6600")
        self.pwCheck.setChecked(False)
        self.password.setText("")
        self.password.setEnabled(False)


class Node(object):

    def __init__(self, parent = None):
        self.nodeParent = parent
        self.children = []
        self.isALeaf = False
        self.fetched = True

    def childCount(self):
        return len(self.children)

    def setFetched(self, isFetched):
        self.fetched = isFetched

    def isFetched(self):
        return self.fetched

    def setLeaf(self, isLeaf):
        self.isALeaf = isLeaf

    def isLeaf(self):
        return self.isALeaf

    def setParent(self, parent):
        self.nodeParent = parent

    def parent(self):
        return self.nodeParent

    def row(self):
        return self.nodeParent.children.index(self)

    def __getitem__(self, i):
        return self.children[i]

    def setChildren(self, children):
        self.children = children

    def clear(self):
        del self.children[:]

    def data(self, column):
        raise NotImplementedError

    def preFetch(self):
        raise NotImplementedError

    def postFetch(self):
        raise NotImplementedError

    def insertCount(self):
        raise NotImplementedError

    # These two are to get values from SongNodes
    def time(self):
        raise NotImplementedError

    def track(self):
        raise NotImplementedError


    # These only work for the immediate parents of song nodes.
    def uri(self, row):
        return self.children[row].myUri()

    def uris(self):
        return [child.myUri() for child in self.children]

    # And this only work for song nodes
    def myUri(self):
        raise NotImplementedError


class FetchingNode(Node):

    def __init__(self, fetcher, data = None, parent = None):
        super(FetchingNode, self).__init__(parent)
        fetcher.setNode(self)
        self.fetcher = fetcher
        self.preFetched = []
        self.nodeData = data

    def preFetch(self):
        self.fetcher.preFetch()

    def insertCount(self):
        return len(self.preFetched)

    def postFetch(self):
        self.setChildren(self.preFetched)

    def addNode(self, node):
        self.preFetched.append(node)

    def clientConnect(self):
        self.setFetched(False)

    def clientDisconnect(self):
        self.clear()
        self.setFetched(True)

    def data(self):
        if self.nodeData:
            return QtCore.QVariant(self.nodeData.decode("utf-8"))
        return QtCore.QVariant()

    # The next four only work for playlists.
    def modified(self):
        return self.nodeData["last-modified"]

    def setModified(self, modified):
        self.nodeData["last-modified"] = modified

    def playlist(self):
        return self.nodeData["playlist"]

    def setPlaylist(self, name):
        self.nodeData["playlist"] = name


class SongNode(Node):

    def __init__(self, song, parent = None):
        super(SongNode, self).__init__(parent)
        self.song = song
        self.setLeaf(True)

    def data(self):
        stripped = Parser.title(self.song).strip()
        return QtCore.QVariant(stripped.decode("utf-8"))

    def myUri(self):
        return self.song["file"]

    # For the tooltips
    def value(self, key):
        # We assume that the song contains the key.
        return Parser.parsedValue(self.song, key)

    # Again, for the tooltips
    def hasKey(self, key):
        return Parser.hasKey(self.song, key)


class PlaylistNode(FetchingNode):

    def __init__(self, playlist, parent = None):
        fetcher = PlaylistSongsFetcher(playlist["playlist"])
        fetcher.setNode(self)
        super(PlaylistNode, self).__init__(fetcher, playlist, parent)
        self.setFetched(False)

    def data(self):
        return QtCore.QVariant(self.playlist().decode("utf-8"))


class Fetcher(QtCore.QObject):

    def __init__(self):
        super(Fetcher, self).__init__()
        self.myNode = None

    def setNode(self, node):
        self.myNode = node

    def addNode(self, node):
        self.myNode.addNode(node)

    def preFetch(self):
        raise NotImplementedError

    def node(self):
        return self.myNode


class MenuFetcher(Fetcher):

    def __init__(self):
        super(MenuFetcher, self).__init__()

    def preFetch(self):
        for item in sorted(self.list(), key = str.lower):
            self.addNode(self.createNode(item))

    def list(self):
        raise NotImplementedError

    def createNode(self, data):
        raise NotImplementedError


class ListFetcher(Fetcher):

    def __init__(self, type):
        super(ListFetcher, self).__init__()
        self.type = type

    def preFetch(self):
        for item in sorted(self.list(self.type), key = str.lower):
            self.addNode(self.createNode(item))

    def list(self, type):
        tags = []
        for tag in Client.cmd("list", type):
            if len(tag.strip()) > 0:
                tags.append(tag)
        return tags

    def createNode(self, data):
        raise NotImplementedError


class GenresFetcher(ListFetcher):

    def __init__(self):
        super(GenresFetcher, self).__init__("genre")

    def preFetch(self):
        node = FetchingNode(ArtistsFetcher(), "All Artists", self.node())
        node.setFetched(False)
        self.addNode(node)

        super(GenresFetcher, self).preFetch()

    def createNode(self, data):
        fetcher = GenreArtistsFetcher(data)
        node = FetchingNode(fetcher, data, self.node())
        node.setFetched(False)
        return node


class GenreArtistsFetcher(MenuFetcher):

    def __init__(self, genre):
        super(GenreArtistsFetcher, self).__init__()
        self.genre = genre

    def preFetch(self):
        node = FetchingNode(GenreSongsFetcher(self.genre), "All", self.node())
        node.setFetched(False)
        self.addNode(node)
        super(GenreArtistsFetcher, self).preFetch()

    def list(self):
        artists = set()
        for song in Client.cmd("find", "genre", self.genre):
            artists = artists | Parser.valueList(song, "artist")
        return artists

    def createNode(self, data):
        fetcher = GenreArtistAlbumsFetcher(self.genre, data)
        node = FetchingNode(fetcher, data, self.node())
        node.setFetched(False)
        return node


class GenreArtistAlbumsFetcher(MenuFetcher):

    def __init__(self, genre, artist):
        super(GenreArtistAlbumsFetcher, self).__init__()
        self.genre = genre
        self.artist = artist

    def preFetch(self):
        songsFetcher = GenreArtistSongsFetcher(self.genre, self.artist)
        node = FetchingNode(songsFetcher, "All Songs", self.node())
        node.setFetched(False)
        self.addNode(node)
        super(GenreArtistAlbumsFetcher, self).preFetch()

    def list(self):
        albums = set()
        for song in Client.cmd("find", "genre", self.genre):
            if Parser.match(song, "artist", self.artist):
                albums = albums | Parser.valueList(song, "album")
        return albums

    def createNode(self, data):
        fetcher = GenreArtistAlbumSongsFetcher(self.genre, self.artist, data)
        node = FetchingNode(fetcher, data, self.node())
        node.setFetched(False)
        return node


class SongsFetcher(Fetcher):

    def __init__(self, client = None):
        super(SongsFetcher, self).__init__()

    def cmp(self, a, b):
        return cmp(Parser.title(a).lower(), Parser.title(b).lower())

    def createNode(self, song):
        return SongNode(song, self.node())

    def songs(self):
        raise NotImplementedError


class AllSongsFetcher(SongsFetcher):

    def __init__(self):
        super(AllSongsFetcher, self).__init__()

    def preFetch(self):
        songList = self.songs()
        songList.sort(self.cmp)
        for song in songList:
            self.addNode(self.createNode(song))

    def songs(self):
        songList = []
        for song in Client.cmd("listallinfo"):
            if Parser.isValid(song):
                songList.append(song)
        return songList


class AlbumFetcher(AllSongsFetcher):

    def __init__(self):
        super(AlbumFetcher, self).__init__()

    def cmp(self, a, b):

        trackOfA = Parser.track(a)
        trackOfB = Parser.track(b)

        if trackOfA <> trackOfB:
            return cmp(trackOfA, trackOfB)

        return super(AlbumFetcher, self).cmp(a, b)


class GenreArtistAlbumSongsFetcher(AlbumFetcher):

    def __init__(self, genre, artist, album):
        super(GenreArtistAlbumSongsFetcher, self).__init__()
        self.genre = genre
        self.artist = artist
        self.album = album

    def songs(self):
        songList = []
        for song in Client.cmd("find", "genre", self.genre):
            if Parser.match(song, "artist", self.artist):
                if Parser.match(song, "album", self.album):
                    songList.append(song)
        return songList


class ArtistsFetcher(ListFetcher):

    def __init__(self):
        super(ArtistsFetcher, self).__init__("artist")

    def preFetch(self):
        node = FetchingNode(AlbumsFetcher(), "All Albums", self.node())
        node.setFetched(False)
        self.addNode(node)
        super(ArtistsFetcher, self).preFetch()

    def createNode(self, data):
        fetcher = ArtistAlbumsFetcher(data)
        node = FetchingNode(fetcher, data, self.node())
        node.setFetched(False)
        return node


class AlbumsFetcher(ListFetcher):

    def __init__(self):
        super(AlbumsFetcher, self).__init__("album")

    def preFetch(self):
        node = FetchingNode(AllSongsFetcher(), "All Songs", self.node())
        node.setFetched(False)
        self.addNode(node)
        super(AlbumsFetcher, self).preFetch()

    def createNode(self, data):
        node = FetchingNode(AlbumSongsFetcher(data), data, self.node())
        node.setFetched(False)
        return node


class AlbumSongsFetcher(AlbumFetcher):

    def __init__(self, album):
        super(AlbumSongsFetcher, self).__init__()
        self.album = album

    def songs(self):
        songList = []
        for song in Client.cmd("find", "album", self.album):
            if Parser.isValid(song):
                songList.append(song)
        return songList


class ArtistAlbumsFetcher(MenuFetcher):

    def __init__(self, artist):
        super(ArtistAlbumsFetcher, self).__init__()
        self.artist = artist

    def preFetch(self):
        node = FetchingNode(ArtistSongsFetcher(self.artist), "All Songs",\
        self.node())
        node.setFetched(False)
        self.addNode(node)
        super(ArtistAlbumsFetcher, self).preFetch()

    def list(self):
        albums = []
        for album in Client.cmd("list", "album", self.artist):
            if len(album.strip()) > 0:
                albums.append(album)
        return albums

    def createNode(self, data):
        fetcher = ArtistAlbumSongsFetcher(self.artist, data)
        node = FetchingNode(fetcher, data, self.node())
        node.setFetched(False)
        return node


class ArtistAlbumSongsFetcher(AlbumFetcher):

    def __init__(self, artist, album):
        super(ArtistAlbumSongsFetcher, self).__init__()
        self.artist = artist
        self.album = album

    def songs(self):
        songList = []
        for song in Client.cmd("find", "artist", self.artist):
            if Parser.match(song, "album", self.album):
                songList.append(song)
        return songList


class ComposersFetcher(ListFetcher):

    def __init__(self):
        super(ComposersFetcher, self).__init__("composer")

    def preFetch(self):
        node = FetchingNode(AlbumsFetcher(), "All Albums", self.node())
        node.setFetched(False)
        self.addNode(node)
        super(ComposersFetcher, self).preFetch()

    def createNode(self, data):
        node = FetchingNode(ComposerAlbumsFetcher(data), data, self.node())
        node.setFetched(False)
        return node


class ComposerAlbumsFetcher(MenuFetcher):

    def __init__(self, composer):
        super(ComposerAlbumsFetcher, self).__init__()
        self.composer = composer

    def preFetch(self):
        node = FetchingNode(ComposerSongsFetcher(self.composer), "All Songs",\
        self.node())
        node.setFetched(False)
        self.addNode(node)
        super(ComposerAlbumsFetcher, self).preFetch()

    def list(self):
        albums = set()
        for song in Client.cmd("find", "composer", self.composer):
            albums = albums | Parser.valueList(song, "album")
        return albums

    def createNode(self, data):
        fetcher = ComposerAlbumSongsFetcher(self.composer, data)
        node = FetchingNode(fetcher, data, self.node())
        node.setFetched(False)
        return node


class ComposerAlbumSongsFetcher(AlbumFetcher):

    def __init__(self, composer, album):
        super(ComposerAlbumSongsFetcher, self).__init__()
        self.composer = composer
        self.album = album

    def songs(self):
        songList = []
        for song in Client.cmd("find", "composer", self.composer):
            if Parser.match(song, "album", self.album):
                songList.append(song)
        return songList


class GenreSongsFetcher(AllSongsFetcher):

    def __init__(self, genre):
        super(GenreSongsFetcher, self).__init__()
        self.genre = genre

    def songs(self):
        songList = []
        for song in Client.cmd("find", "genre", self.genre):
            songList.append(song)
        return songList


class ArtistSongsFetcher(AllSongsFetcher):

    def __init__(self, artist):
        super(ArtistSongsFetcher, self).__init__()
        self.artist = artist

    def songs(self):
        songList = []
        for song in Client.cmd("find", "artist", self.artist):
            songList.append(song)
        return songList


class ComposerSongsFetcher(AllSongsFetcher):

    def __init__(self, composer):
        super(ComposerSongsFetcher, self).__init__()
        self.composer = composer

    def songs(self):
        songList = []
        for song in Client.cmd("find", "composer", self.composer):
            songList.append(song)
        return songList


class GenreArtistSongsFetcher(AllSongsFetcher):

    def __init__(self, genre, artist):
        super(GenreArtistSongsFetcher, self).__init__()
        self.genre = genre
        self.artist = artist

    def songs(self):
        songList = []
        for song in Client.cmd("find", "artist", self.artist):
            if "genre" in song and song["genre"] == self.genre:
                songList.append(song)
        return songList


class PlaylistSongsFetcher(SongsFetcher):

    def __init__(self, playlist):
        super(PlaylistSongsFetcher, self).__init__()
        self.playlist = playlist

    def preFetch(self):
        for song in Client.cmd("listplaylistinfo", self.playlist):
            self.addNode(self.createNode(song))

    def setPlaylist(self, playlist):
        self.playlist = playlist


class AllUris(object):

    def fetchUris(self, node):
        return (node.myUri(), node.parent().uris())


class OneUri(object):

    def fetchUris(self, node):
        return (node.myUri(), [node.myUri()])


#http://benjamin-meyer.blogspot.com/2006/10/dynamic-models.html

class DatabaseModel(QtCore.QAbstractItemModel):

    def __init__(self, root, uriFetcher, parent = None):
        super(DatabaseModel, self).__init__(parent)
        self.root = root
        self.uriFetcher = uriFetcher

        # We do not fetch yet.
        self.root.setFetched(True)

    def setConnector(self, connector):
        self.connector = connector

    def node(self, index):
        if index.isValid():
            return index.internalPointer()
        return self.root

    def rowCount(self, parent):
        return self.node(parent).childCount()

    def columnCount(self, parent):
        return 1

    def hasChildren(self, parent):
        node = self.node(parent)
        if not parent.isValid():
            return node.childCount() > 0
        return not node.isLeaf()

    def canFetchMore(self, parent):
        return not self.node(parent).isFetched()

    def fetchMore(self, parent):
        try:
            node = self.node(parent)
            node.setFetched(True)
            node.preFetch()
            self.beginInsertRows(parent, 0, node.insertCount() - 1)
            node.postFetch()
            self.endInsertRows()
        except (MPDError, socket.error) as e:
            self.emit(QtCore.SIGNAL("broken"), str(e))
            self.connector.setBroken(e)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        node = self.node(index)
        if node.parent() is None:
            return QtCore.QModelIndex()
        if node.parent() == self.root:
            return QtCore.QModelIndex()
        if not node.parent().parent():
            return QtCore.QModelIndex()
        return self.createIndex(node.parent().row(), 0, node.parent())

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        parentNode = self.node(parent)
        return self.createIndex(row, column, parentNode[row])

    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled
        if self.node(index).isLeaf():
            flags = flags | QtCore.Qt.ItemIsSelectable
            flags = flags | QtCore.Qt.ItemIsDragEnabled
        return flags

    def clientConnect(self):
        self.root.clientConnect()
        self.root.setLeaf(False)
        self.reset()

    def clientDisconnect(self):
        self.beginRemoveRows(QtCore.QModelIndex(), 0,\
        self.root.childCount() - 1)
        self.root.clientDisconnect()
        self.endRemoveRows()
        self.root.setLeaf(True)

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()

        if role == QtCore.Qt.DisplayRole:
            return self.node(index).data()

        if self.node(index).isLeaf():
            if role == QtCore.Qt.DecorationRole:
                # My C++ knowledge helped me solve this.
                icon = QtGui.QIcon(kdeui.KIcon("audio-x-generic"))
                return QtCore.QVariant(icon)
        else:
            if role == QtCore.Qt.FontRole:
                font = QtGui.QFont()
                font.setBold(True)
                return QtCore.QVariant(font)
            if role == QtCore.Qt.DecorationRole:
                icon = QtGui.QIcon(kdeui.KIcon("folder-sound"))
                return QtCore.QVariant(icon)


        return QtCore.QVariant()

    # Respond to doubleclick
    def sendUris(self, index):
        node = self.node(index)
        if node.isLeaf():
            uriToPlay, uris = self.uriFetcher.fetchUris(self.node(index))
            self.emit(QtCore.SIGNAL("uris"), uriToPlay, uris)

    def mimeData(self, indexes):
        encodedData = QtCore.QByteArray()
        stream = QtCore.QDataStream(encodedData, QtCore.QIODevice.WriteOnly)
        for index in indexes:
            if index.isValid():
                stream.writeString(self.node(index).myUri())

        mimeData = QtCore.QMimeData()
        mimeData.setData("application/x-quetzalcoatl-uris", encodedData)
        return mimeData


class PlaylistsModel(DatabaseModel):

    def __init__(self, uriFetcher, parent = None):

        # It doesn't matter which fetcher we choose, because we never use
        # it.
        super(PlaylistsModel, self).__init__(FetchingNode(AllSongsFetcher()),\
        uriFetcher, parent)

    def clientConnect(self):
        # We do NOT fetch on connection. Instead, we do that when updating.
        pass

    def setConnector(self, connector):
        self.connector = connector

    def setPlaylists(self, playlists):
        oldSize = self.root.childCount()
        newSize = len(playlists)

        # First we trim to size
        if newSize < oldSize:
            self.beginRemoveRows(QtCore.QModelIndex(), newSize,\
            oldSize - 1)
            del self.root.children[newSize:oldSize]
            self.endRemoveRows()

        # Then we add what we need to
        if oldSize < newSize:
            self.beginInsertRows(QtCore.QModelIndex(), oldSize, newSize - 1)
            for i in xrange(oldSize, newSize):
                self.root.children.append(PlaylistNode(playlists[i],\
                self.root))
            self.endInsertRows()

        # Then we check what's changed.
        for i in xrange(newSize):
            namesMatch = self.root[i].playlist() == playlists[i]["playlist"]
            datesMatch = self.root[i].modified() == \
            playlists[i]["last-modified"]

            index = None
            if not namesMatch or not datesMatch:
                index = self.createIndex(i, 0, self.root[i])
            if not namesMatch:
                self.root[i].setPlaylist(playlists[i]["playlist"])
                self.root[i].setModified(playlists[i]["last-modified"])
                self.root[i].fetcher.playlist = playlists[i]["playlist"]
                self.emit(QtCore.SIGNAL(\
                "dataChanged(QModelIndex, QModelIndex"), index, index)
            if index:
                self.root[i].setFetched(False)
                self.emit(QtCore.SIGNAL("isExpanded"), index, False)

    def flags(self, index):
        flags = super(PlaylistsModel, self).flags(index)
        if index.isValid() and not self.node(index).isLeaf():
            flags = flags | QtCore.Qt.ItemIsEditable
        return flags

    def rename(self, index, name):
        try:
            Client.cmd("rename", self.root[index.row()].playlist(), name)
            #self.connector.updatePlaylists()
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def delete(self, index):
        try:
            Client.cmd("rm", self.root[index.row()].playlist())
            #self.connector.updatePlaylists()
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)


class DatabaseView(QtGui.QTreeView):

    def __init__(self, parent = None):
        super(DatabaseView, self).__init__(parent)

        self.setHeaderHidden(True)
        self.setUniformRowHeights(True)
        self.setDragEnabled(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.setEnabled(False)

    def setConnector(self, connector):
        pass

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setEnabled(False)

    def setModel(self, model):
        self.connect(self, QtCore.SIGNAL("doubleClicked(QModelIndex)"),\
        model.sendUris)

        # Used only in the Playlists Model.
        self.connect(model, QtCore.SIGNAL("isExpanded"), self.setExpanded)
        QtGui.QTreeView.setModel(self, model)

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.ToolTip:
            index = self.indexAt(event.pos())
            if index.isValid():
                node = index.internalPointer()
                if node.isLeaf():

                    tags = [("artist", "Artists: "), ("album", "Album: "),\
                    ("genre", "Genre: "), ("composer", "Composer: ")]

                    text = ""
                    first = True
                    for tag, header in tags:
                        if node.hasKey(tag):
                            if first:
                                first = False
                            else:
                                text = text + "\n"
                            text = text + header + node.value(tag)
                    if len(text) > 0:
                        QtGui.QToolTip.showText(event.globalPos(), text)
        return QtGui.QAbstractItemView.viewportEvent(self, event)


class PlaylistsView(DatabaseView):

    def __init__(self, parent = None):
        super(PlaylistsView, self).__init__(parent)
        self.actions = []
        delete = QtGui.QAction("Delete", self)
        self.actions.append(delete)
        self.connect(delete, QtCore.SIGNAL("triggered()"), self.deleteSlot)
        rename = QtGui.QAction("Rename", self)
        self.connect(rename, QtCore.SIGNAL("triggered()"), self.renameSlot)
        self.actions.append(rename)
        self.index = None
        self.setEditTriggers(QtGui.QAbstractItemView.SelectedClicked)

    def renameSlot(self):
        self.edit(self.index)

    def deleteSlot(self):
        self.model().delete(self.index)

    def contextMenuEvent(self, event):
        self.index = self.indexAt(event.pos())
        if not self.index.isValid():
            self.index = None
            return
        node = self.index.internalPointer()
        if not node.isLeaf():
            QtGui.QMenu.exec_(self.actions, event.globalPos())


class PlaylistsDelegate(QtGui.QStyledItemDelegate):

    def __init__(self, parent = None):
        super(PlaylistsDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        return PlaylistSaver.createLineEdit(parent, True)

    def setEditorData(self, editor, index):
        editor.setText(index.internalPointer().nodeData["playlist"])

    def setModelData(self, editor, model, index):
        name = unicode(editor.text()).strip()
        if model.root[index.row()].playlist() == name:
            return
        if PlaylistSaver.isOkay(name, self.parent()):
            model.rename(index, name)


class PlaylistModel(QtCore.QAbstractItemModel):

    NO_VERSION = -32768
    NO_SONGID = -32768

    def __init__(self, combinedTimeLabel, parent = None):
        super(PlaylistModel, self).__init__(parent)
        self.ids = []
        self.version = PlaylistModel.NO_VERSION
        self.songid = PlaylistModel.NO_SONGID
        self.selectedLength = combinedTimeLabel

    def rowCount(self, parent = QtCore.QModelIndex()):
        return len(self.ids)

    def columnCount(self, parent = QtCore.QModelIndex()):
        return 2

    def setConnector(self, connector):
        self.connector = connector

    def clientConnect(self):
        pass

    def clientDisconnect(self):
        self.version = PlaylistModel.NO_VERSION
        self.songid = PlaylistModel.NO_SONGID
        size = len(self.ids)
        if size > 0:
            self.beginRemoveRows(QtCore.QModelIndex(), 0, size - 1)
            del self.ids[:]
            self.endRemoveRows()

    def data(self, index, role = QtCore.Qt.DisplayRole):
        try:
            if not index.isValid():
                return QtCore.QVariant()

            if role == QtCore.Qt.DisplayRole:
                song = Client.cmd("playlistid", self.ids[index.row()])[0]
                if index.column() == 0:
                    return QtCore.QVariant(Parser.title(song).decode("utf-8"))
                if index.column() == 1:
                    return QtCore.QVariant(Parser.length(song))

            if role == QtCore.Qt.DecorationRole:
                if index.column() == 0:
                    icon = QtGui.QIcon(kdeui.KIcon("audio-x-generic"))
                    return QtCore.QVariant(icon)

            if role == QtCore.Qt.FontRole:
                if self.ids[index.row()] == self.songid:
                    font = QtGui.QFont()
                    font.setBold(True)
                    return QtCore.QVariant(font)
            
            return QtCore.QVariant()
        except (MPDError, socket.error) as e:
            return QtCore.QVariant()

    def flags(self, index):
        f = QtCore.Qt.NoItemFlags
        if index.isValid():
            f = f | QtCore.Qt.ItemIsEnabled
            if index.column() == 0:
                f = f | QtCore.Qt.ItemIsSelectable |\
                QtCore.Qt.ItemIsDragEnabled
        else:
            f = f | QtCore.Qt.ItemIsDropEnabled
        return f

    def mimeData(self, indexes):
        encodedData = QtCore.QByteArray()
        stream = QtCore.QDataStream(encodedData, QtCore.QIODevice.WriteOnly)
        for index in indexes:
            if index.isValid():
                stream.writeUInt16(index.row())

        mimeData = QtCore.QMimeData()
        mimeData.setData("application/x-quetzalcoatl-rows", encodedData)
        return mimeData

    def mimeTypes(self):
        types = QtCore.QStringList()
        types << "application/x-quetzalcoatl-rows"
        types << "application/x-quetzalcoatl-uris"
        return types

    def dropMimeData(self, data, action, row, column, parent):
        try:

            if len(self.ids) > 0 and row < 0:
                return False

            if data.hasFormat("application/x-quetzalcoatl-rows"):
                encodedData = data.data("application/x-quetzalcoatl-rows")
                stream = QtCore.QDataStream(encodedData,\
                QtCore.QIODevice.ReadOnly)
                srcIndexes = []
                while not stream.atEnd():
                    srcIndexes.append(stream.readUInt16())
                srcIndexes.sort()

                # You don't want to know how long this took.
                srcOffset = 0
                destOffset = 0
                for srcIndex in srcIndexes:
                    if srcIndex < row:
                        self.move(srcIndex - srcOffset, row - 1)
                        srcOffset = srcOffset + 1
                    else:
                        self.move(srcIndex, row + destOffset)
                        destOffset = destOffset + 1

            if data.hasFormat("application/x-quetzalcoatl-uris"):
                encodedData = data.data("application/x-quetzalcoatl-uris")
                stream = QtCore.QDataStream(encodedData,\
                QtCore.QIODevice.ReadOnly)

                # If the model is empty, -1 is passed into row: >.<
                if row == -1:
                    insertAt = 0
                else:
                    insertAt = row
                while not stream.atEnd():
                    uri = stream.readString()
                    self.beginInsertRows(QtCore.QModelIndex(), insertAt,\
                    insertAt)
                    id = Client.cmd("addid", uri, insertAt)
                    self.ids.insert(insertAt, id)
                    self.endInsertRows()
                    insertAt = insertAt + 1
                self.emit(QtCore.SIGNAL("saveable"), True)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

        return True

    def index(self, row, column, parent):

        # This is lifted from Esperenza's PlaylistModel class.
        if not parent.isValid():
            if row >= len(self.ids):
                return QtCore.QModelIndex()
            if row < 0:
                return QtCore.QModelIndex()
            return self.createIndex(row, column, -1)
        return QtCore.QModelIndex()

    def move(self, srcIndex, destIndex):
        # Exceptions are caught in the calling method.

        if srcIndex == destIndex:
            return

        id = self.ids[srcIndex]
        Client.cmd("moveid", id, destIndex)
        if srcIndex < destIndex:
            step = 1
            firstIndex = srcIndex
            lastIndex = destIndex
        else:
            step = -1
            firstIndex = destIndex
            lastIndex = srcIndex
        for i in xrange(srcIndex, destIndex, step):
            self.ids[i] = self.ids[i + step]
        self.ids[destIndex] = id
        self.emit(QtCore.SIGNAL(\
        "dataChanged(QModelIndex, QModelIndex)"),\
        self.index(firstIndex, 0, QtCore.QModelIndex()),\
        self.index(lastIndex, 1, QtCore.QModelIndex()))

    def update(self, status):
        version = int(status["playlist"])
        size = int(status["playlistlength"])

        try:
            if version <> self.version:
                oldSize = len(self.ids)
                if size < oldSize:
                    self.beginRemoveRows(QtCore.QModelIndex(), size,\
                    oldSize - 1)
                    del self.ids[size:oldSize]
                    self.endRemoveRows()
                changes = Client.cmd("plchangesposid", self.version)
                changes.sort(self.posCmp)
                for posid in changes:
                    pos = int(posid["cpos"])
                    id = int(posid["id"])
                    if pos < len(self.ids):
                        self.ids[pos] = id
                        self.emit(QtCore.SIGNAL(
                        "dataChanged(QModelIndex, QModelIndex)"),\
                       self.index(pos, 0, QtCore.QModelIndex()),\
                        self.index(pos, 1, QtCore.QModelIndex()))
                    else:
                        self.beginInsertRows(QtCore.QModelIndex(),
                        len(self.ids), len(self.ids))
                        self.ids.append(id)
                        self.endInsertRows()
                self.version = version
            if "songid" in status:
                songid = int(status["songid"])
                if songid <> self.songid:
                    self.setSongId(songid)
            else:
                try:
                    i = self.ids.index(self.songid)
                    self.songid = PlaylistModel.NO_SONGID
                    self.emit(QtCore.SIGNAL(\
                    "dataChanged(QModelIndex, QModelIndex)"),\
                    self.index(i, 0, QtCore.QModelIndex()),\
                    self.index(i, 1, QtCore.QModelIndex()))
                except:
                    pass
            self.emit(QtCore.SIGNAL("saveable"), size > 0)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def posCmp(self, a, b):
        return cmp(int(a["cpos"]), int(b["cpos"]))

    def setSongId(self, songid):
        if songid <> self.songid:
            oldId = self.songid
            self.songid = songid

            try:
                oldIndex = self.ids.index(oldId)
                self.emit(QtCore.SIGNAL(\
                "dataChanged(QModelIndex, QModelIndex)"),\
                self.index(oldIndex, 0, QtCore.QModelIndex()),\
                self.index(oldIndex, 1, QtCore.QModelIndex()))
            except:
                pass

            try:
                newIndex = self.ids.index(self.songid)
                self.emit(QtCore.SIGNAL(\
                "dataChanged(QModelIndex, QModelIndex)"),\
                self.index(newIndex, 0, QtCore.QModelIndex()),\
                self.index(newIndex, 1, QtCore.QModelIndex()))
            except:
                # If the id in question is not found, the playlist is
                # inconsistent. The poller and setVersion will take care of
                # it.
                pass

    def play(self, index):
        self.playRow(index.row())

    def playRow(self, row):
        # this is called by both self.play and PlaylistView.play
        try:
            id = self.ids[row]
            self.setSongId(id)
            Client.cmd("playid", id)
            self.emit(QtCore.SIGNAL("playing"))
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def deleteRows(self, rows):

        # We speed things up by looking for runs.

        run = []
        offset = 0

        for row in sorted(rows):
            if len(run) == 0:
                run = [row]

            elif row - run[-1] == 1:
                run.append(row)
            else:
                str(run[-1] - offset)
                self.beginRemoveRows(QtCore.QModelIndex(), run[0] - offset,\
                run[-1] - offset)
                for rowInRun in run:
                    id = self.ids[rowInRun - offset]
                    if id == self.songid:
                        self.emit(QtCore.SIGNAL("stopped"))
                    Client.cmd("deleteid", id)
                del self.ids[run[0] - offset: run[-1] - offset + 1]
                self.endRemoveRows()
                offset = offset + len(run)
                run = [row]
                print "We start a new run: " + str(run)
        str(run[-1] - offset)
        self.beginRemoveRows(QtCore.QModelIndex(), run[0] - offset,\
        run[-1] - offset)
        for rowInRun in run:
            id = self.ids[rowInRun - offset]
            if id == self.songid:
                self.emit(QtCore.SIGNAL("stopped"))
            Client.cmd("deleteid", id)
        del self.ids[run[0] - offset: run[-1] - offset + 1]
        self.endRemoveRows()

        self.emit(QtCore.SIGNAL("saveable"), len(self.ids) > 0)

    def setUris(self, uriToPlay, uris):
        try:
            self.beginRemoveRows(QtCore.QModelIndex(), 0, len(self.ids) - 1)
            Client.cmd("clear")
            del self.ids[:]
            self.endRemoveRows()

            rowToPlay = -1
            self.beginInsertRows(QtCore.QModelIndex(), 0, len(uris) - 1)
            for row in xrange(len(uris)):
                self.ids.append(Client.cmd("addid", uris[row]))
                if uris[row] == uriToPlay:
                    rowToPlay = row
            self.endInsertRows()
            self.playRow(rowToPlay)
            self.emit(QtCore.SIGNAL("saveable"), True)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def parent(self, index):
        return QtCore.QModelIndex()

    def headerData(self, section, orientation, role = QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and \
        role == QtCore.Qt.DisplayRole:
            if section == 0:
                return QtCore.QVariant("Name")
            if section == 1:
                return QtCore.QVariant("Time")
        return QtCore.QVariant()

    def hasChildren(self, parent):
        if parent.isValid():
            return False
        return True

    def song(self, index):
        try:
            return Client.cmd("playlistid", self.ids[index.row()])[0]
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def showCombinedTime(self, indexes):
        # We catch exceptions in the calling method

        if len(indexes) > 0:
            time = 0
            for index in indexes:
                song = Client.cmd("playlistid", self.ids[index.row()])[0]
                time = time + int(song["time"])
            self.selectedLength.setText(Parser.prettyTime(time))
        else:
            self.selectedLength.setText("")


class PlaylistView(QtGui.QTreeView):

    def __init__(self, parent = None):
        super(PlaylistView, self).__init__(parent)
        self.setEnabled(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.setSelectionBehavior(self.SelectRows)
        delete = QtGui.QAction("Delete", self)
        self.connect(delete, QtCore.SIGNAL("triggered()"), self.deleteSlot)
        self.index = None
        self.actions = [delete]

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setEnabled(False)

    def setConnector(self, connector):
        self.connector = connector

    def contextMenuEvent(self, event):
        display = False
        if self.indexAt(event.pos()).isValid():
            display = True
            self.index = self.indexAt(event.pos())
        else:
            self.index = None
        if len(self.selectedIndexes()) > 0:
            display = True
        if display:
            QtGui.QMenu.exec_(self.actions, event.globalPos())

    def deleteSlot(self):
        rows = set()
        for index in self.selectedIndexes():
            rows.add(index.row())
        if self.index:
            rows.add(self.index.row())
        self.model().deleteRows(rows)

    def setModel(self, model):
        self.connect(self, QtCore.SIGNAL("doubleClicked(QModelIndex)"),\
        model.play)
        QtGui.QTreeView.setModel(self, model)
        self.connect(self.selectionModel(),\
        QtCore.SIGNAL("selectionChanged(QItemSelection, QItemSelection)"),\
        self.setLabel)

    def play(self):

        row = -1

        if len(self.selectedIndexes()) > 0:
            row = self.selectedIndexes()[0].row()
        else:
            try:
                # A candidate for refactoring, yes.
                row = self.model().ids.index(self.model().songid)
            except:
                if self.model().rowCount() > 0:
                    row = 0
        if row > -1:
            self.model().playRow(row)

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.ToolTip:

            index = self.indexAt(event.pos())

            if index.isValid():
                tags = [("artist", "Artists: "), ("album", "Album: "),\
                ("genre", "Genre: "), ("composer", "Composer: ")]
                text = ""
                first = True
                song = self.model().song(index)
                for tag, header in tags:
                    if Parser.hasKey(song, tag):
                        if first:
                            first = False
                        else:
                            text = text + "\n"
                        text = text + header + Parser.parsedValue(song, tag)
                if len(text) > 0:
                    QtGui.QToolTip.showText(event.globalPos(), text)
        return QtGui.QTreeView.viewportEvent(self, event)

    def setLabel(self, selected, deselected):
        try:
            self.model().showCombinedTime(\
            self.selectionModel().selectedIndexes())
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)


class ConnectAction(QtGui.QAction):

    def __init__(self, parent):
        super(ConnectAction, self).__init__(parent)
        self.clientDisconnect()

    def setConnector(self, connector):
        self.connector = connector
        self.connect(self, QtCore.SIGNAL("triggered()"),\
        self.connector.toggleConnected)

    def clientConnect(self):
        self.setIcon(kdeui.KIcon("network-disconnect"))
        self.setText("Disconnect from MPD")

    def clientDisconnect(self):
        self.setIcon(kdeui.KIcon("network-connect"))
        self.setText("Connect to MPD")


class StopAction(QtGui.QAction):

    def __init__(self, parent):
        super(StopAction, self).__init__(kdeui.KIcon("media-playback-stop"),\
        "Stop", parent)
        self.setEnabled(False)
        self.connect(self, QtCore.SIGNAL("triggered()"),\
        self.parentWidget().stopPlaying)

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setEnabled(False)

    def setConnector(self, connector):
        pass


class PlayPauseAction(QtGui.QAction):
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2

    def __init__(self, parent):
        super(PlayPauseAction, self).__init__(\
        kdeui.KIcon("media-playback-start"), "Play", parent)
        self.connect(self, QtCore.SIGNAL("triggered()"), self.handle)
        self.state = PlayPauseAction.STOPPED
        self.setEnabled(False)

    def setConnector(self, connector):
        self.connector = connector

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setState(PlayPauseAction.STOPPED)
        self.setEnabled(False)

    def setState(self, state):
        if state <> self.state:
            if state == PlayPauseAction.PLAYING:
                self.setIcon(kdeui.KIcon("media-playback-pause"))
                self.setText("Pause")
            else:
                self.setIcon(kdeui.KIcon("media-playback-start"))
                self.setText("Play")
            self.state = state

    def handle(self):
        try:
            if self.state == PlayPauseAction.STOPPED:
                self.setState(PlayPauseAction.PLAYING)
                self.parentWidget().play()
            elif self.state == PlayPauseAction.PLAYING:
                self.setState(PlayPauseAction.PAUSED)
                Client.cmd("pause", 1)
            else:
                self.setState(PlayPauseAction.PLAYING)
                Client.cmd("pause", 0)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def update(self, status):

        if status["state"] == "stop":
            self.setState(PlayPauseAction.STOPPED)
            return

        if status["state"] == "play":
            self.setState(PlayPauseAction.PLAYING)
            return

        self.setState(PlayPauseAction.PAUSED)


class PrevAction(QtGui.QAction):

    def __init__(self, parent):
        super(PrevAction, self).__init__(kdeui.KIcon("media-skip-backward"),\
        "Previous", parent)
        self.connect(self, QtCore.SIGNAL("triggered()"), self.prev)
        self.setEnabled(False)

    def prev(self):
        try:
            Client.cmd("previous")
            self.parentWidget().forceUpdate()
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def setConnector(self, connector):
        self.connector = connector

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setEnabled(False)


class NextAction(QtGui.QAction):

    def __init__(self, parent):
        super(NextAction, self).__init__(kdeui.KIcon("media-skip-forward"),\
        "Next", parent)
        self.connect(self, QtCore.SIGNAL("triggered()"), self.next)
        self.setEnabled(False)

    def next(self):
        try:
            Client.cmd("next")
            self.parentWidget().forceUpdate()
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def setConnector(self, connector):
        self.connector = connector

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setEnabled(False)


class ShuffleAction(QtGui.QAction):

    def __init__(self, parent):
        super(ShuffleAction, self).__init__(\
        kdeui.KIcon("media-playlist-shuffle"), "Shuffle", parent)
        self.connect(self, QtCore.SIGNAL("toggled(bool)"), self.shuffle)
        self.setCheckable(True)
        self.setChecked(False)
        self.setEnabled(False)

    def shuffle(self, checked):
        try:
            Client.cmd("random", 1 if checked else 0)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def setConnector(self, connector):
        self.connector = connector

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setChecked(False)
        self.setEnabled(False)

    def update(self, status):
        self.setChecked(status["random"] == "1")


class RepeatAction(QtGui.QAction):

    def __init__(self, parent):
        super(RepeatAction, self).__init__(\
        kdeui.KIcon("media-playlist-repeat"), "Repeat", parent)
        self.connect(self, QtCore.SIGNAL("toggled(bool)"), self.repeat)
        self.setCheckable(True)
        self.setChecked(False)
        self.setEnabled(False)

    def repeat(self, checked):
        try:
            Client.cmd("repeat", 1 if checked else 0)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def setConnector(self, connector):
        self.connector = connector

    def clientConnect(self):
        self.setEnabled(True)

    def clientDisconnect(self):
        self.setChecked(False)
        self.setEnabled(False)

    def update(self, status):
        self.setChecked(status["repeat"] == "1")


class SaveAction(QtGui.QAction):

    def __init__(self, parent):
        super(SaveAction, self).__init__(kdeui.KIcon("document-save"),\
        "Save Playlist", parent)
        self.connect(self, QtCore.SIGNAL("triggered()"), self.save)
        self.setEnabled(False)
        self.playlistSaver = PlaylistSaver(parent)

    def save(self):
        self.playlistSaver.exec_()
        #if self.playlistSaver.result() == QtGui.QDialog.Accepted:
        #    self.parentWidget().updatePlaylists()
    def setConnector(self, connector):
        self.connector = connector
        self.playlistSaver.setConnector(connector)

    def clientConnect(self):
        pass

    def clientDisconnect(self):
        self.setEnabled(False)


class PlaylistSaver(kdeui.KDialog):

    def __init__(self, parent = None):
        super(PlaylistSaver, self).__init__(parent)

        self.setCaption("Save Playlist")

        self.setButtons(self.ButtonCode(self.Ok | self.Cancel))
        body = QtGui.QWidget(self)
        layout = QtGui.QFormLayout(body)
        self.name = PlaylistSaver.createLineEdit(self)

        layout.addRow(self.tr("&Name"), self.name)
        self.setMainWidget(body)
        self.connect(self, QtCore.SIGNAL("okayClicked()"), self,\
        QtCore.SLOT("accept()"))

    def setConnector(self, connector):
        self.connector = connector

    def accept(self):
        try:
            name = unicode(self.name.text()).strip()
            if PlaylistSaver.isOkay(name.encode("utf-8"), self):
                Client.cmd("save", name.encode("utf-8"))
                QtGui.QDialog.accept(self)
            else:
                QtGui.QDialog.reject(self)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    @classmethod
    def isOkay(cls, name, parent):
        # This is also called by the PlaylistDelegate.
        # Calling methods should check for exceptions.
        if len(name) == 0:
            return False

        if name[0] == ".":
            kdeui.KMessageBox.error(parent, "Playlist names may not begin "\
            "with a period.")
            return False

        matched = False
        for check in Client.cmd("listplaylists"):
            if check["playlist"] == name:
                matched = True
                break
        if matched:
            kdeui.KMessageBox.error(parent, "A playlist by that name "\
            "already exists.")
            return False

        return True

    @classmethod
    def createLineEdit(cls, parent, inDelegate = False):
        # Again, also called by the Playlists Delegate.
        # The inView parameter is there because the PlaylistsDelegate
        # needs a KLineEdit created differently.

        if inDelegate:
            lineEdit = kdeui.KLineEdit("", parent)
        else:
            lineEdit = kdeui.KLineEdit()
        rx = QtCore.QRegExp("^[^\/]+$")
        lineEdit.setValidator(QtGui.QRegExpValidator(rx, parent))
        # Plus dot, plus extension, makes 255.
        lineEdit.setMaxLength(251)
        return lineEdit


class UI(kdeui.KMainWindow):

    def __init__(self, client):
        QtGui.QMainWindow.__init__(self)
        self.setWindowIcon(kdeui.KIcon("multimedia-player"))

        self.isDragging = False

        self.resize(800, 600)
        self.setWindowTitle('Quetzalcoatl')

        self.status = self.statusBar()
        combinedTime = QtGui.QLabel()
        self.status.addPermanentWidget(combinedTime)

        self.connector = Connector(self)
        self.connector.addConnectable(self, Connector.UPDATEABLE)

        self.cfgDlg = Configurer(self)

        toolBar = self.toolBar("ToolBar")
        toolBar.setToolBarsEditable(False)
        toolBar.setToolBarsLocked(True)
        toolBar.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

        toolBar.addAction(kdeui.KIcon("configure"), "Configure",\
        self.cfgDlg.exec_)

        connectAction = ConnectAction(self)
        self.connector.addConnectable(connectAction)
        toolBar.addAction(connectAction)

        stopAction = StopAction(self)
        self.connector.addConnectable(stopAction)
        toolBar.addAction(stopAction)

        self.playPauseAction = PlayPauseAction(self)
        self.connector.addConnectable(self.playPauseAction,\
        Connector.UPDATEABLE)
        toolBar.addAction(self.playPauseAction)

        prevAction = PrevAction(self)
        self.connector.addConnectable(prevAction)
        toolBar.addAction(prevAction)

        nextAction = NextAction(self)
        self.connector.addConnectable(nextAction)
        toolBar.addAction(nextAction)

        toolBar.addSeparator()

        shuffleAction = ShuffleAction(self)
        self.connector.addConnectable(shuffleAction, Connector.UPDATEABLE)
        toolBar.addAction(shuffleAction)

        repeatAction = RepeatAction(self)
        self.connector.addConnectable(repeatAction, Connector.UPDATEABLE)
        toolBar.addAction(repeatAction)

        toolBar.addSeparator()

        saveAction = SaveAction(self)
        self.connector.addConnectable(saveAction)
        toolBar.addAction(saveAction)

        centralWidget = QtGui.QWidget(self)
        self.setCentralWidget(centralWidget)
        layout = QtGui.QVBoxLayout()
        centralWidget.setLayout(layout)

        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.setTracking(False)
        self.connect(self.slider, QtCore.SIGNAL("valueChanged(int)"),\
        self.setSongTime)
        self.connect(self.slider, QtCore.SIGNAL("sliderMoved(int)"),\
        self.setDragging)
        self.connect(self.slider, QtCore.SIGNAL("sliderReleased()"),\
        self.setNotDragging)
        layout.addWidget(self.slider)

        splitter = QtGui.QSplitter()
        layout.addWidget(splitter)
        self.tabs = kdeui.KTabWidget(splitter)
        self.tabs.setTabPosition(QtGui.QTabWidget.West)

        self.dbModels = []

        self.playlistsModel = PlaylistsModel(AllUris())
        self.connector.addPlaylistModel(self.playlistsModel)
        view = PlaylistsView()
        self.connector.addConnectable(view)
        view.setModel(self.playlistsModel)
        self.playlistsDelegate = PlaylistsDelegate(self)
        view.setItemDelegate(self.playlistsDelegate)
        self.tabs.addTab(view, "Playlists")
        self.dbModels.append(self.playlistsModel)

        self.addTab(ArtistsFetcher(), AllUris(), "Artists")
        self.addTab(AlbumsFetcher(), AllUris(), "Albums")
        self.addTab(AllSongsFetcher(), OneUri(), "Songs")
        self.addTab(GenresFetcher(), AllUris(), "Genres")
        self.addTab(ComposersFetcher(), AllUris(), "Composers")

        self.playlistModel = PlaylistModel(combinedTime, self)
        self.connector.addConnectable(self.playlistModel,\
        Connector.UPDATEABLE)
        playlistSplitter = QtGui.QSplitter(splitter)
        playlistSplitter.setOrientation(QtCore.Qt.Vertical)
        albumArt = QtGui.QLabel(playlistSplitter)
        QtGui.QLabel(splitter)
        self.playlistView = PlaylistView(playlistSplitter)
        self.connector.addConnectable(self.playlistView)
        self.playlistView.setModel(self.playlistModel)
        self.connect(self.playlistModel, QtCore.SIGNAL("playing"),\
        self.setPlaying)
        self.connect(self.playlistModel, QtCore.SIGNAL("saveable"),\
        saveAction.setEnabled)
        self.connect(self.playlistModel, QtCore.SIGNAL("stopped"),\
        self.stopPlaying)

        self.connectDBModels()

        self.connector.connectToClient()

    def setConnector(self, connector):
        pass

    def clientConnect(self):
        pass

    def clientDisconnect(self):
        self.status.showMessage("")
        self.resetSlider()

    def setSongTime(self, value):
        try:
            if not self.slider.isEnabled():
                return

            status = Client.cmd("status")
            if not "songid" in status:
                return
            if not "time" in status:
                return
            if value == Parser.elapsed(status):
                return
            Client.cmd("seekid", status["songid"], value)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def update(self, status):

        if "time" in status:
            self.status.showMessage(Parser.prettyStatusTime(status))

            if not self.isDragging:
                self.disconnect(self.slider,
                QtCore.SIGNAL("valueChanged(int)"), self.setSongTime)
                self.setSlider(status)
                self.connect(self.slider, QtCore.SIGNAL("valueChanged(int)"),
                self.setSongTime)
        else:
            self.status.showMessage("")
            self.resetSlider()

    def resetSlider(self):
        if self.slider.isEnabled():
            self.slider.setEnabled(False)
            self.slider.setMaximum(0)
            self.slider.setValue(0)

    def setSlider(self, status):
        self.slider.setMaximum(Parser.total(status))
        self.slider.setValue(Parser.elapsed(status))
        self.slider.setEnabled(True)

    def closeEvent(self, event):
        self.connector.disconnectFromClient()

    def stopPlaying(self):
        try:
            self.resetSlider()
            self.status.showMessage("")
            self.playPauseAction.setState(PlayPauseAction.STOPPED)
            Client.cmd("stop")
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

    def forceUpdate(self):
        self.connector.update()

    def play(self):
        self.playlistView.play()

    def setPlaying(self):
        self.playPauseAction.setState(PlayPauseAction.PLAYING)
        self.connector.update()

    def sendUris(self, row, uris):
        self.playlistModel.setUris(row, uris)

    def addTab(self, fetcher, uriFetcher, label):
        model = DatabaseModel(FetchingNode(fetcher), uriFetcher)
        self.connector.addConnectable(model)
        view = DatabaseView()
        self.connector.addConnectable(view)
        view.setModel(model)
        self.tabs.addTab(view, label)
        self.dbModels.append(model)

    def connectDBModels(self):
        for model in self.dbModels:
            self.connect(model, QtCore.SIGNAL("uris"),\
            self.playlistModel.setUris)
        self.connect(self.playlistsModel, QtCore.SIGNAL("uris"),\
        self.playlistModel.setUris)

    def setDragging(self, value):
        self.isDragging = True

    def setNotDragging(self):
        self.isDragging = False

if __name__ == "__main__":

    appName = "Quetzalcoatl"
    catalog = ""
    programName = kdecore.ki18n("Quetzalcoatl")
    version = "1.0"
    description = kdecore.ki18n("mpd client")
    license = kdecore.KAboutData.License_GPL
    copyright = kdecore.ki18n("(c) 2009 Dugan Chen")
    text = kdecore.ki18n("none")
    homePage = "www.duganchen.ca"
    bugEmail = "see homepage"
    aboutData = kdecore.KAboutData(appName, catalog, programName, version,\
    description, license, copyright, text, homePage, bugEmail)

    kdecore.KCmdLineArgs.init(sys.argv, aboutData)
    app = kdeui.KApplication()
    client = MPDClient()
    main = UI(client)
    main.show()
    sys.exit(app.exec_())
