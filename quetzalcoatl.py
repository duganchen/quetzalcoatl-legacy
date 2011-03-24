#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# I'm aware of an inefficiency: expanding a node for the first time
# and causing a fetch will cause the view's columns to be resized to the
# contents twice.

import sip

sip.setapi("QDate", 2)
sip.setapi("QDateTime", 2)
sip.setapi("QTextStream", 2)
sip.setapi("QTime", 2)
sip.setapi("QVariant", 2)
sip.setapi("QString", 2)
sip.setapi("QUrl", 2)

import sys
import os
import types
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QAbstractItemModel, QObject
from mpd import MPDClient, MPDError
from PyKDE4 import kdecore, kdeui
from PyQt4.QtCore import QSize, Qt, QModelIndex, QTimer, pyqtSignal
from PyQt4.QtGui import QIcon, QTreeView
from PyKDE4.kdeui import KIcon
import socket
from sys import maxint
import posixpath


# The root menu of my iPod video 5.5G is:
# Playlists
# Artists
# Albums
# Compilations
# Songs
# Podcasts
# Genres
# Composers
# Audiobooks

class Song(dict):
    """ A song. """
    @property
    def title(self):
        if 'title' in self:
            return self['title']
        return os.path.splitext(os.path.basename(self["file"]))[0]
    
    @property
    def key(self):
        """ Returns the sorting key. """
        if 'track' in self:
            return self['track']
        return self.title.lower()

class AlbumSong(Song):
    
    """ A song. """
    
    def __lt__(self, other):
        return self.key < other.key
    
    def __le__(self, other):
        return self.key <= other.key
    
    def __eq__(self, other):
        return self.key == other.key
    
    def __ne__(self, other):
        return self.key != other.key
    
    def __gt__(self, other):
        return self.key > other.key
    
    def __ge__(self, other):
        return self.key >= other.key

class RandomSong(Song):
    
    """ A song. Not in an album. """
    
    def __lt__(self, other):
        return self.title.lower() < other.title.lower()
    
    def __le__(self, other):
        return self.title.lower() <= other.title.lower()
    
    def __eq__(self, other):
        return self.title.lower() == other.title.lower()
    
    def __ne__(self, other):
        return self.title.lower() != other.title.lower()
    
    def __gt__(self, other):
        return self.title.lower() > other.title.lower()
    
    def __ge__(self, other):
        return self.title.lower() >= other.title.lower()

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

        self.__sanitizers = {}
        self.__sanitizers['songid'] = int
        self.__sanitizers['playlistlength'] = int
        self.__sanitizers['playlist'] = self.__sanitize_playlist
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
        self.__sanitizers['song'] = int
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
    def __sanitize_playlist(cls, value):
        """
        lsinfo() and status() can both return a playlist key.
        """
        try:
            posixpath.splitext(value)
            return value
        except:
            return int(value)

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
        try:
            return int(value)
        except:
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

                if 'track' in dictionary:
                    try:
                        int(dictionary['track'])
                    except:
                        del dictionary['track']
    
    def __getattr__(self, attr):
        attribute = getattr(self.__client, attr)
        if hasattr(attribute, "__call__"):
            return lambda * args: self.__command(attribute, *args)
        return attribute


class TreeNode(list):
    
    """
    A node for the tree in the left side of the GUI.
    """
    
    def __init__(self, controller):
        """
        Creates a TreeNode.
        """
        #self.__children = []
        self.__parent = None
        self.__icon = None
        self.__controller = controller
        controller.node = self
        self.__song = None
        self.__isFetched = False

    def append(self, child):
        """ Appends a child to the node. """
        child.parent = self
        super(TreeNode, self).append(child)
    
    @property
    def parent(self):
        """ Returns the parent. """
        return self.__parent
    
    @parent.setter
    def parent(self, node):
        """ Sets the parent to the specified node. """
        self.__parent = node
    
    def data(self, index, role):
        """
        Returns the data for the specified column and display role.
        """
        
        if index.column() == 0  and role == Qt.DisplayRole:
            return self.__controller.label.decode("utf-8")
        
        if index.column() == 0 and role == Qt.DecorationRole:
            return self.__controller.icon
        
        if index.column() == 1 and role == Qt.DisplayRole:
            return self.__controller.track
        
        return None
    
    def row(self, x):
        """ Returns the(row) of child node x. """
        return self.index(x)
    
    @property
    def icon(self):
        """
        Returns the icon, in the form of a scaled QPixmap.
        """
        return self.__icon
    
    @icon.setter
    def icon(self, value):
        """ Sets the icon. """
        self.__icon = value
    
    @property
    def song(self):
        """
        Returns the node's song.
        
        Returns none if the node doesn't have a song
        (i.e. if it's a directory).
        """
        return self.__controller.song
    
    @property
    def isFetched(self):
        """ Returns whether the node is fetched. """
        return self.__isFetched
    
    @isFetched.setter
    def isFetched(self, value):
        self.__isFetched = value
    
    def fetch(self):
        """
        Fetches and returns data.
        """
        return self.__controller.fetch()

class TreeModel(QtCore.QAbstractItemModel):

    """
    The main model class used by Quetzalcoatl.    
    """
    
    # Data changed. View resized columns to contents.
    changed = pyqtSignal(QModelIndex)
    
    # http://benjamin-meyer.blogspot.com/2006/10/dynamic-models.html
    
    def __init__(self, controller, parent=None):
        """ Initializes the model. """
        super(TreeModel, self).__init__(parent)
        self.__root = TreeNode(controller)
        self.__root.isFetched = False

    def node(self, index):
        """ Returns the node for the given index. """
        if index.isValid():
            return index.internalPointer()
        return self.__root
    
    def rowCount(self, parent):
        """ Returns the number of rows. """
        return len(self.node(parent))
    
    def columnCount(self, parent):
        """ Returns the number of columns. """
        return 2

    def hasChildren(self, parent=QModelIndex()):
        
        """ Returns whether a given index has children. """
        
        node = self.node(parent)
        if not parent.isValid():
            return len(node) > 0
        
        return node.song is None

    def canFetchMore(self, parent):
        
        """
        Returns whether a given parent index
        is ready to fetch.
        """
   
        node = self.node(parent)
        return not node.isFetched

    def fetchMore(self, parent):
        
        """
        Given an index, populates it with children.
        """
        
        if parent.isValid():
            parentIndex = parent
            node = parent.internalPointer()
        else:
            parentIndex = QModelIndex()
            node = self.__root
        
        rows = node.fetch()
        
        self.beginInsertRows(parentIndex, 0, len(rows) - 1)
        
        for row in rows:
            node.append(row)
        
        node.isFetched = True
        self.endInsertRows()
        self.changed.emit(parent)

    def data(self, index, role=Qt.DisplayRole):
        
        """ Returns data for the given index and role. """
        
        if not index.isValid():
            return None
        node = self.node(index)
        return node.data(index, role)
    
    def headerData(self, section, orientation, role = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section == 0:
                return "Name"
            if section == 1:
                return "Track"
        return None

    def flags(self, index):
        
        """ Returns the behavior flags for the given index. """
        
        flags = QtCore.Qt.ItemIsEnabled
        if index.isValid():
            node = self.node(index)
            if node.song is not None:
                flags = flags | QtCore.Qt.ItemIsSelectable
                flags = flags | QtCore.Qt.ItemIsDragEnabled
        return flags
    
    def parent(self, index):
        
        """ Given an index, returns its parent. """
        
        if not index.isValid():
            return QModelIndex()
        
        node = index.internalPointer()
        if node.parent is None or node.parent == self.__root:
            return QModelIndex()
        
        grandparent = node.parent.parent
        if grandparent is None:
            return QModelIndex()
        
        try:
            i = grandparent.index(node.parent)
            return self.createIndex(i, 0, node.parent)
        except:
            return QModelIndex()

    def index(self, row, column, parent=QModelIndex()):
        
        """ returns an index for the given parameters. """
        
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        node = self.node(parent)
        return self.createIndex(row, column, node[row])

class TreeView(QTreeView):
    def __init__(self, parent = None):
        super(TreeView, self).__init__(parent)
        self.expanded.connect(self.resizeColumnsToContents)
        self.collapsed.connect(self.resizeColumnsToContents)
    
    def resizeColumnsToContents(self, QModelIndex):
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)


class NodeController(object):
    
    """
    Provides tree node functions for labels, icons, and fetching.
    """
    
    # Icons are looked up by name and by mbid.
    icons = {}
    icons["audio-x-generic"] = QIcon(KIcon("audio-x-generic"))
    icons["folder-documents"] = QIcon(KIcon("folder-documents"))
    icons["server-database"] = QIcon(KIcon("server-database"))
    icons["drive-harddisk"] = QIcon(KIcon("drive-harddisk"))
    icons["folder-sound"] = QIcon(KIcon("folder-sound"))
    icons["media-optical-audio"] = QIcon(KIcon("media-optical-audio"))
    icons['.ac3'] = QIcon(KIcon('audio-x-ac3'))
    icons['.flac'] = QIcon(KIcon('audio-x-flac'))
    icons['.ogg'] = QIcon(KIcon('audio-x-flac+ogg'))
    icons['.ra'] = QIcon(KIcon('audio-ac3'))
    icons['.mid'] = QIcon(KIcon('audio-midi'))
    icons['.wav'] = QIcon(KIcon('audio-x-wav'))
    
    def __init__(self, client):
        """ Creates a controller for the specified client. """
        self.__client = client
    
    @property
    def client(self):
        """ Returns the client. """
        return self.__client
    
    def fetch(self):
        """ Returns rows fetched from the node. """
        return []
    
    @property
    def icon(self):
        """ Returns the node's icon. """
        return None
    
    @property
    def label(self):
        """ Returns the node's label. """
        return ""
    
    @property
    def song(self):
        """ Returns the song (None for directories). """
        return None
    
    @song.setter
    def song(self):
        return None
    
    @property
    def track(self):
        """ Returns the track. Or None. """
        return None


class RootController(NodeController):
    
    """
    The controller for the navigation root.
    """
    
    def fetch(self):
        nodes = []
        nodes.append(TreeNode(PlaylistsController(self.client)))
        nodes.append(TreeNode(ArtistsController(self.client)))
        nodes.append(TreeNode(AlbumsController(self.client)))
        nodes.append(TreeNode(AlbumArtistsController(self.client)))
        nodes.append(TreeNode(SongsController(self.client)))
        nodes.append(TreeNode(GenresController(self.client)))
        nodes.append(TreeNode(ComposersController(self.client)))
        nodes.append(TreeNode(DirectoryController(self.client)))
        return nodes


class PlaylistsController(NodeController):
    
    """ Controller for the Playlists node. """
    
    def __init__(self, client):
        self.__client = client
    
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["folder-documents"]
    
    @property
    def label(self):
        return "Playlists"

class ArtistsController(NodeController):
    
    """ Controller for the Artists node. """
    
    def fetch(self):
        """ Fetches and returns artists. """
        f = lambda x: len(x.strip()) > 0
        artists = sorted(filter(f, self.client.list('artist')), key=str.lower)
        node = lambda artist: TreeNode(ArtistController(self.client, artist))
        return map(node, artists)

    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["server-database"]
    
    @property
    def label(self):
        return "Artists"

class AlbumsController(NodeController):
    
    """ Controller for the Albums node. """
    
    def fetch(self):
        """ Fetches and returns albums. """
        f = lambda x: len(x.strip()) > 0
        raw = self.client.list('album')
        cd = lambda cd: TreeNode(AlbumController(self.client, cd))
        return map(cd, sorted(filter(f, raw), key=str.lower))
    
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["server-database"]
    
    @property
    def label(self):
        return "Albums"

class AlbumArtistsController(NodeController):
    
    def fetch(self):
        raw = self.client.list('AlbumArtist')
        f = lambda x: len(x.strip()) > 0
        node = lambda x: TreeNode(AlbumArtistController(self.client, x))
        return map(node, sorted(filter(f, raw)))
    
    @property
    def icon(self):
        return self.icons['server-database']
    @property
    def label(self):
        return "Compilations"

class AlbumArtistController(NodeController):
    
    def __init__(self, client, albumArtist):
        super(AlbumArtistController, self).__init__(client)
        self.__artist = albumArtist
    
    def fetch(self):
        raw = self.client.find('albumartist', self.__artist)
        albums = set()
        for song in raw:
            if 'album' in song and len(song['album']) > 0:
                albums.add(song['album'])
        node = lambda album: TreeNode(CompilationAlbumController(self.client, self.__artist, album))
        return map(node, sorted(albums))
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    @property
    def label(self):
        return self.__artist

class CompilationAlbumController(NodeController):
    def __init__(self, client, artist, album):
        super(CompilationAlbumController, self).__init__(client)
        self.__artist = artist
        self.__album = album
    
    def fetch(self):
        f = lambda x: 'albumartist' in x and x['albumartist'] == self.__artist
        node = lambda x: TreeNode(AlbumSongController(self.client, x))
        raw = self.client.find('album', self.__album)
        return map(node, sorted(map(AlbumSong, filter(f, raw))))
    
    @property
    def icon(self):
        return self.icons['media-optical-audio']
    
    @property
    def label(self):
        return self.__album

class SongsController(NodeController):

    def fetch(self):
        raw = self.client.listallinfo()
        node = lambda x: TreeNode(SongController(self.client, x))
        f = lambda x: 'file' in x
        return map(node, sorted(map(RandomSong, filter(f, raw))))
    
    @property
    def icon(self):
        return self.icons['server-database']
    @property
    def label(self):
        return "Songs"

class AlbumController(NodeController):
    """ Albums > Twilight of the Thunder God """
    def __init__(self, client, album):
        """ Initializes the controller. """
        super(AlbumController, self).__init__(client)
        self.__album = album
    
    def fetch(self):
        """ Fetches and returns the album's songs """
        raw = self.client.find('album', self.__album)
        node = lambda song: TreeNode(AlbumSongController(self.client, song))
        return map(node, sorted(map(AlbumSong, raw)))
    
    @property
    def label(self):
        return self.__album
    
    @property
    def icon(self):
        return self.icons['media-optical-audio']

class GenresController(NodeController):
    
    """ Controller for the Genres node. """
    
    def fetch(self):
        """ Fetches the list of genres. """
        f = lambda x: len(x.strip()) > 0
        raw = self.client.list('genre')
        node = lambda genre: TreeNode(
                    GenreController(self.client, genre))
        return map(node, sorted(filter(f, raw)))
    
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons['server-database']
    
    @property
    def label(self):
        return 'Genres'

class GenreController(NodeController):
    
    def __init__(self, client, genre):
        super(GenreController, self).__init__(client)
        self.__genre = genre
    
    def fetch(self):
        nodes = [TreeNode(GenreSongsController(self.client, self.__genre))]
        nodes.append(TreeNode(GenreCompilationsController(self.client, self.__genre)))
        hasArtist = lambda x: 'artist' in x and len(x['artist']) > 0
        raw = self.client.find('genre', self.__genre)
        node = lambda x: TreeNode(GenreArtistController(self.client, self.__genre, x))
        artist = lambda x: x['artist']
        nodes.extend(map(node, sorted(set(map(artist, filter(hasArtist, raw))))))
        return nodes
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return self.__genre

class GenreSongsController(NodeController):
    def __init__(self, client, genre):
        super(GenreSongsController, self).__init__(client)
        self.__genre = genre
    
    def fetch(self):
        raw = self.client.find('genre', self.__genre)
        node = lambda x: TreeNode(SongController(self.client, x))
        return map(node, sorted(map(RandomSong, raw)))
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return "All Songs"

class GenreCompilationsController(NodeController):
    def __init__(self, client, genre):
        super(GenreCompilationsController, self).__init__(client)
        self.__genre = genre
    
    def fetch(self):
        raw = self.client.find('genre', self.__genre)
        f = lambda x: 'albumartist' in x and len(x['albumartist'].strip()) > 0
        m = lambda x: x['albumartist']
        node = lambda x: TreeNode(GenreCompilationArtistController(self.client, self.__genre, x))
        return map(node, sorted(set(map(m, filter(f, raw)))))
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return "Compilations"

class GenreCompilationArtistController(NodeController):
    def __init__(self, client, genre, artist):
        super(GenreCompilationArtistController, self).__init__(client)
        self.__genre = genre
        self.__artist = artist
    
    def fetch(self):
        raw = self.client.find('albumartist', self.__artist)
        isArtist = lambda x: 'albumartist' in x and x['albumartist'] == self.__artist
        isGenre = lambda x: 'genre' in x and x['genre'] == self.__genre
        f = lambda x: isGenre(x) and isArtist(x)
        node = lambda x: TreeNode(GenreCompilationAlbumController(self.client, self.__genre, self.__artist, x))
        m = lambda x: x['album']
        return map(node, sorted(set(map(m, filter(f, raw)))))
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return self.__artist

class GenreCompilationAlbumController(NodeController):
    def __init__(self, client, genre, artist, album):
        super(GenreCompilationAlbumController, self).__init__(client)
        self.__genre = genre
        self.__artist = artist
        self.__album = album
    
    def fetch(self):
        raw = self.client.find('album', self.__album)
        isGenre = lambda x: 'genre' in x and x['genre'] == self.__genre
        isArtist = lambda x: 'albumartist' in x and x['albumartist'] == self.__artist
        f = lambda x: isGenre(x) and isArtist(x)
        node = lambda x: TreeNode(AlbumSongController(self.client, x))
        return map(node, sorted(map(AlbumSong, filter(f, raw))))
    
    @property
    def icon(self):
        return self.icons['media-optical-audio']
    
    @property
    def label(self):
        return self.__album

class GenreArtistController(NodeController):
    def __init__(self, client, genre, artist):
        super(GenreArtistController, self).__init__(client)
        self.__genre = genre
        self.__artist = artist
    
    def fetch(self):
        f = lambda x: 'genre' in x and x['genre'] == self.__genre and 'album' in x and len(x['album'].strip()) > 0
        m = lambda x: x['album']
        raw = self.client.find('artist', self.__artist)
        node = lambda x: TreeNode(GenreArtistAlbumController(self.client, self.__genre, self.__artist, x))
        nodes = [TreeNode(GenreArtistSongsController(self.client, self.__genre, self.__artist))]
        nodes.extend(map(node, sorted(set(map(m, filter(f, raw))))))
        return nodes
        
    @property
    def label(self):
        return self.__artist
    
    @property
    def icon(self):
        return self.icons['folder-sound']

class GenreArtistSongsController(NodeController):
    def __init__(self, client, genre, artist):
        super(GenreArtistSongsController, self).__init__(client)
        self.__genre = genre
        self.__artist = artist
    
    def fetch(self):
        raw = self.client.find('artist', self.__artist)
        f = lambda x: 'genre' in x and x['genre'] == self.__genre
        node = lambda x: TreeNode(SongController(self.client, x))
        return map(node, map(RandomSong, filter(f, raw)))
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return "All Songs"

class GenreArtistAlbumController(NodeController):
    def __init__(self, client, genre, artist, album):
        super(GenreArtistAlbumController, self).__init__(client)
        self.__genre = genre
        self.__artist = artist
        self.__album = album
    
    def fetch(self):
        raw = self.client.find('album', self.__album)
        f = lambda x: 'genre' in x and x['genre'] == self.__genre and 'artist' in x and x['artist'] == self.__artist
        node = lambda x: TreeNode(AlbumSongController(self.client, x))
        return map(node, sorted(map(AlbumSong, filter(f, raw))))

    @property
    def icon(self):
        return self.icons['media-optical-audio']
    
    @property
    def label(self):
        return self.__album

class ComposersController(NodeController):
    
    """ Controller for the Composers node. """
    
    def fetch(self):
        raw = self.client.list('composer')
        f = lambda x: len(x.strip()) > 0
        node = lambda x: TreeNode(ComposerController(self.client, x))
        return map(node, sorted(filter(f, raw)))
    
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["server-database"]
    
    @property
    def label(self):
        return "Composers"

class ArtistController(NodeController):
    
    """ A controller for a node for an artist. """
    
    def __init__(self, client, artist):
        """ Initializes the node. """
        super(ArtistController, self).__init__(client)
        self.__artist = artist
    
    def fetch(self):
        """ Returns the artist's albums. """
        
        raw = self.client.list('album', self.__artist)
        f = lambda x: len(x.strip()) > 0
        node = lambda album: TreeNode(ArtistAlbumController(self.client,
                                                self.__artist, album))
        result = [TreeNode(ArtistSongsController(self.client, self.__artist))]
        result.extend(map(node, sorted(filter(f, raw), key=str.lower)))
        return result
    
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["folder-sound"]
    
    @property
    def label(self):
        """ Returns the label, display-ready. """
        return self.__artist


class ArtistAlbumController(NodeController):
    """ Artists
        > Amon Amarth
        > Twilight of the Thunder God
    """
    def __init__(self, client, artist, album):
        """ Initializes the controller. """
        super(ArtistAlbumController, self).__init__(client)
        self.__artist = artist
        self.__album = album
    
    def fetch(self):
        """ Fetches the songs. """
        f = lambda x: 'artist' in x and x['artist'] == self.__artist
        raw = self.client.find("album", self.__album)
        song = lambda song: TreeNode(AlbumSongController(self.client, song))
        return map(song, sorted(map(AlbumSong, filter(f, raw))))
        
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["media-optical-audio"]
    
    @property
    def label(self):
        """ Returns the label. """
        return self.__album

class ArtistSongsController(NodeController):
    """ Artists > Amon Amarth > All Songs """
    def __init__(self, client, artist):
        """ Initializes the controller. """
        super(ArtistSongsController, self).__init__(client)
        self.__artist = artist
    
    def fetch(self):
        """ Fetches the songs. """
        raw = self.client.find('artist', self.__artist)
        song = lambda song: TreeNode(SongController(self.client, song))
        return map(song, sorted(map(RandomSong, raw)))
        
    @property
    def icon(self):
        """ Returns the icon. """
        return self.icons["folder-sound"]
    
    @property
    def label(self):
        """ Returns the label. """
        return "All Songs"

class SongController(NodeController):
    """ A song. Left side. """
    def __init__(self, client, song):
        """ Initializes the controller. """
        super(SongController, self).__init__(client)
        self.__song = song
    
    @property
    def icon(self):
        """ Returns the icon. """
        
        extension = os.path.splitext(self.__song['file'])[1].lower()
        
        try:
            return self.icons[extension]
        except:
            return self.icons["audio-x-generic"]
    
    @property
    def label(self):
        """ Returns the label. """
        return self.__song.title
    
    @property
    def song(self):
        """ Returns the song. """
        return self.__song

class AlbumSongController(SongController):
    """ Tracks are only displayed in the context of albums. """
    
    @property
    def track(self):
        if 'track' in self.song:
            return self.song['track']
        return None

class ComposerController(NodeController):
    def __init__(self, client, composer):
        super(ComposerController, self).__init__(client)
        self.__composer = composer
    
    def fetch(self):
        raw = self.client.find('composer', self.__composer)
        f = lambda x: 'album' in x and len(x['album'].strip()) > 0
        node = lambda x: TreeNode(ComposerAlbumController(self.client, self.__composer, x))
        m = lambda x: x['album']
        nodes = [TreeNode(ComposerSongsController(self.client, self.__composer))]
        nodes.extend(map(node, sorted(set(map(m, filter(f, raw))))))
        return nodes
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return self.__composer

class ComposerSongsController(NodeController):
    def __init__(self, client, composer):
        super(ComposerSongsController, self).__init__(client)
        self.__composer = composer
    
    def fetch(self):
        raw = self.client.find('composer', self.__composer)
        node = lambda x: TreeNode(SongController(self.client, x))
        return map(node, sorted(map(AlbumSong, raw)))
    
    @property
    def icon(self):
        return self.icons['folder-sound']
    
    @property
    def label(self):
        return 'All Songs'

class ComposerAlbumController(NodeController):
    def __init__(self, client, composer, album):
        super(ComposerAlbumController, self).__init__(client)
        self.__composer = composer
        self.__album = album
    
    def fetch(self):
        raw = self.client.find('album', self.__album)
        f = lambda x: 'composer' in x and x['composer'] == self.__composer
        node = lambda x: TreeNode(AlbumSongController(self.client, x))
        return map(node, sorted(map(AlbumSong, filter(f, raw))))
    
    @property
    def icon(self):
        return self.icons['media-optical-audio']
    
    @property
    def label(self):
        return self.__album

class DirectoryController(NodeController):
    def __init__(self, client, info = None):
        
        super(DirectoryController, self).__init__(client)
        self.__info = info
        self.__song = None
        if info is not None and not 'directory' in info:
            self.__song = RandomSong(info)
    
    def fetch(self):
        if self.__info is None:
            raw = self.client.lsinfo()
        else:
            raw = self.client.lsinfo(self.__info['directory'])
        dirs = filter(lambda x: 'directory' in x, raw)
        dirs.sort(key=lambda x: x['directory'].lower())
        songs = filter(lambda x: 'file' in x, raw)
        songs = map(lambda x: RandomSong(x), songs)
        dirs.extend(songs)
        node = lambda x: TreeNode(DirectoryController(self.client, x))
        return map(node, dirs)
    
    @property
    def label(self):
        if self.__info is None:
            return 'Directories'
        if 'directory' in self.__info:
            return posixpath.basename(self.__info['directory'])
        return self.song.title
    
    @property
    def icon(self):
        
        if self.__info is None:
            return self.icons['drive-harddisk']
        
        if self.song is None:
            return self.icons['folder-sound']
        
        extension = os.path.splitext(self.song['file'])[1].lower()
        
        try:
            return self.icons[extension]
        except:
            return self.icons["audio-x-generic"]
        
    @property
    def song(self):
        return self.__song

class Client0(QObject):
    """
    The client wrapper class.
    """
    
    playlistlength = pyqtSignal(int)
    playlist = pyqtSignal(int)
    repeat = pyqtSignal(bool)
    consume = pyqtSignal(bool)
    random = pyqtSignal(bool)
    state = pyqtSignal(str)
    xfade = pyqtSignal(int)
    single = pyqtSignal(bool)
    error = pyqtSignal(str)
    isConnected = pyqtSignal(bool)
    time = pyqtSignal(TimeSpan, TimeSpan)
    songid = pyqtSignal(int)
    
    def __init__(self, parent=None):
        """
        Initializes the Client.
        """

        super(Client0, self).__init__(parent)
        self.__poller = None
        self.__timer = QTimer(self)
        self.__timer.setInterval(1000)
        self.__timer.timeout.connect(self.poll)
        self.__status = {}

    def __getattr__(self, attr):
        """
        Allows access to the client's methods.
        
        Do not use it to call the client's connect() and
        disconnect() methods.
        """

        attribute = getattr(self.__poller, attr)
        if not hasattr(attribute, "__call__"):
            return attribute
        return lambda * args: self.__wrapper(attribute, *args)
    
    def __wrapper(self, method, *args):
        """
        Executes a poller method, and handles exceptions.
        """
        return method(*args)
    
    def open(self, host, port):
        """
        Connects to the client.
        """
        self.__poller = SanitizedClient(MPDClient())
        self.__poller.connect(host, port)
        self.__status.clear()
        self.__timer.start()
        self.isConnected.emit(True)
    
    def close(self):
        """
        Closes the connection.
        """
        self.__poller.disconnect()
        self.__poller = None
        self.isConnected.emit(False)
    
    def poll(self):
        """ Polls the server. """
        status = self.__poller.status()
        
        if self.__updated(status, 'playlistlength'):
            self.__status['playlistlength'] = status['playlistlength']
            self.playlistlength.emit(status['playlistlength'])

        if self.__updated(status, 'playlist'):
            self.__status['playlist'] = status['playlist']
            self.playlist.emit(status['playlistlength'])
        
        if self.__updated(status, 'repeat'):
            self.__status['repeat'] = status['repeat']
            self.repeat.emit(status['repeat'])

        if self.__updated(status, 'consume'):
            self.__status['consume'] = status['consume']
            self.consume.emit(status['consume'])

        if self.__updated(status, 'random'):
            self.__status['random'] = status['random']
            self.random.emit(status['random'])

        if self.__updated(status, 'state'):
            self.__status['state'] = status['state']
            self.state.emit(status['state'])
        
        if self.__updated(status, 'xfade'):
            self.__status['xfade'] = status['xfade']
            self.random.emit(status['xfade'])
        
        if self.__updated(status, 'single'):
            self.__status['single'] = status['single']
            self.xfade.emit(status['xfade'])
        
        if self.__updated(status, 'time'):
            self.__status['time'] = status['time']
            elapsed, total = status['time']
            self.time.emit(elapsed, total)
        
        if self.__updated(status, 'songid'):
            self.__status['songid'] = status['songid']
            self.songid.emit(status['songid'])
    
    def __updated(self, status, key):
        """
        Determines whether to emit a signal.
        """
        
        if key not in status:
            return False

        if key not in self.__status:
            return True
        if status[key] != self.__status[key]:
            return True
        
        return False

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
        return int(status["time"][status["time"].row(":") + 1:])

    @classmethod
    def elapsed(cls, status):
        return int(status["time"][0:status["time"].row(":")])

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
    """
    Deprecated. To be replaced with the other Client class.
    """

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
    def cmd(cls, command, a=None, b=None, c=None):
        if c is not None:
            return getattr(cls.client, command)(str(a), str(b), str(c))
        if b is not None:
            return getattr(cls.client, command)(str(a), str(b))
        if a is not None:
            return getattr(cls.client, command)(str(a))
        return getattr(cls.client, command)()


class IdleThread(QtCore.QThread):
    """
    Deprecated. To be moved into the client class.
    """

    def __init__(self, parent=None):
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
    
    """
    Deprecated. To be moved into the Client class.
    """

    def __init__(self, parent=None):
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
        sortedList = sorted(playlists, key=self.sortingKey)
        self.emit(QtCore.SIGNAL("playlists"), sortedList)

    def sortingKey(self, element):
        return element["playlist"].strip().lower()


class Options(object):

    def __init__(self):
        self.config = kdecore.KSharedConfig.openConfig("quetzalcoatlrc")
        self.connectionGroup = self.config.group("Connection")

    @property
    def host(self):
        return self.connectionGroup.readEntry("host", "localhost")

    @host.setter
    def host(self, value):
        self.connectionGroup.writeEntry("host", value)

    @property
    def port(self):
        # get this working later
        # return self.connectionGroup.readEntry("port", 6600)[0]
        return 6600
        

    @port.setter
    def port(self, value):
        self.connectionGroup.writeEntry("port", value)

    @property
    def needPassword(self):
        #return self.connectionGroup.readEntry("needPassword", False).toBool()
        return True

    @needPassword.setter
    def needPassword(self, value):
        self.connectionGroup.writeEntry("needPassword", value)

    @property
    def password(self):
        return self.connectionGroup.readEntry("password", "")

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
            kdeui.KMessageBox.detailedError(self.parent(), \
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
        kdeui.KMessageBox.detailedError(self.parent(), \
        "Connection Lost", str(e), "Connection Lost")

    def disconnectFromClient(self):
        self.timer.stop()
        for connectable in self.connectables:
            connectable.clientDisconnect()
        try:
            Client.cmd("disconnect")
        except:
            pass
        Client.delete()
        self.idler.stop()

    def addConnectable(self, connectable, updateable=False):
        connectable.setConnector(self)
        self.connectables.append(connectable)
        if updateable:
            self.updateables.append(connectable)

    def updatePlaylists(self):
        try:
            if Client.exists():
                playlists = Client.cmd("listplaylists")
                sortedPlaylists = sorted(playlists, key=self.sortingKey)
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

        self.connect(self.pwCheck, QtCore.SIGNAL("stateChanged(int)"), \
        self.togglePassword)

        self.connect(self, QtCore.SIGNAL("okClicked()"), self, \
        QtCore.SLOT("accept()"))
        self.connect(self, QtCore.SIGNAL("cancelClicked()"), self, \
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
        self.connect(self.tabs, QtCore.SIGNAL("currentChanged(int)"), \
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
            #if "volume" in str(e):
            #    print str(e)
            pass

        QtGui.QDialog.accept(self)

    def defaults(self):
        self.host.setText("localhost")
        self.port.setText("6600")
        self.pwCheck.setChecked(False)
        self.password.setText("")
        self.password.setEnabled(False)


class Node(object):
    
    """
    The TreeNode class is to deprecate this.
    """
    
    def __init__(self, parent=None):
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
        return self.nodeParent.children.row(self)

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

    def __init__(self, fetcher, data=None, parent=None):
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

    def __init__(self, song, parent=None):
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

    def __init__(self, playlist, parent=None):
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
        for item in sorted(self.list(), key=str.lower):
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
        for item in sorted(self.list(self.type), key=str.lower):
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

    def __init__(self, client=None):
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
        node = FetchingNode(ArtistSongsFetcher(self.artist), "All Songs", \
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
        node = FetchingNode(ComposerSongsFetcher(self.composer), "All Songs", \
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

class DatabaseView(QtGui.QTreeView):

    def __init__(self, parent=None):
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
        self.connect(self, QtCore.SIGNAL("doubleClicked(QModelIndex)"), \
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

                    tags = [("artist", "Artists: "), ("album", "Album: "), \
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

    def __init__(self, parent=None):
        super(PlaylistsView, self).__init__(parent)
        self.actions = []
        delete = QtGui.QAction("Delete", self)
        self.actions.append(delete)
        self.connect(delete, QtCore.SIGNAL("triggered()"), self.deleteSlot)
        rename = QtGui.QAction("Rename", self)
        self.connect(rename, QtCore.SIGNAL("triggered()"), self.renameSlot)
        self.actions.append(rename)
        self.row = None
        self.setEditTriggers(QtGui.QAbstractItemView.SelectedClicked)

    def renameSlot(self):
        self.edit(self.row)

    def deleteSlot(self):
        self.model().delete(self.row)

    def contextMenuEvent(self, event):
        self.row = self.indexAt(event.pos())
        if not self.row.isValid():
            self.row = None
            return
        node = self.row.internalPointer()
        if not node.isLeaf():
            QtGui.QMenu.exec_(self.actions, event.globalPos())


class PlaylistsDelegate(QtGui.QStyledItemDelegate):

    def __init__(self, parent=None):
        super(PlaylistsDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        return PlaylistSaver.createLineEdit(parent, True)

    def setEditorData(self, editor, index):
        editor.setText(row.internalPointer().nodeData["playlist"])

    def setModelData(self, editor, model, index):
        name = unicode(editor.text()).strip()
        if model.root[index.row()].playlist() == name:
            return
        if PlaylistSaver.isOkay(name, self.parent()):
            model.rename(index, name)


class PlaylistModel(QtCore.QAbstractItemModel):

    NO_VERSION = -32768
    NO_SONGID = -32768

    def __init__(self, combinedTimeLabel, parent=None):
        super(PlaylistModel, self).__init__(parent)
        self.ids = []
        self.version = PlaylistModel.NO_VERSION
        self.songid = PlaylistModel.NO_SONGID
        self.selectedLength = combinedTimeLabel

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.ids)

    def columnCount(self, parent=QtCore.QModelIndex()):
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

    def data(self, index, role=QtCore.Qt.DisplayRole):
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
                    icon = kdeui.KIcon("audio-x-generic")
                    pixmap = icon.pixmap(QSize(32, 32))
                    scaled = pixmap.scaled(QSize(34, 34), Qt.IgnoreAspectRatio, Qt.FastTransformation)
                    return QtCore.QVariant(scaled)

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
                f = f | QtCore.Qt.ItemIsSelectable | \
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
                stream = QtCore.QDataStream(encodedData, \
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
                stream = QtCore.QDataStream(encodedData, \
                QtCore.QIODevice.ReadOnly)

                # If the model is empty, -1 is passed into row: >.<
                if row == -1:
                    insertAt = 0
                else:
                    insertAt = row
                while not stream.atEnd():
                    uri = stream.readString()
                    self.beginInsertRows(QtCore.QModelIndex(), insertAt, \
                    insertAt)
                    id = Client.cmd("addid", uri, insertAt)
                    self.ids.insert(insertAt, id)
                    self.endInsertRows()
                    insertAt = insertAt + 1
                self.emit(QtCore.SIGNAL("saveable"), True)
        except (MPDError, socket.error) as e:
            self.connector.setBroken(e)

        return True

    def row(self, row, column, parent):

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
        "dataChanged(QModelIndex, QModelIndex)"), \
        self.row(firstIndex, 0, QtCore.QModelIndex()), \
        self.row(lastIndex, 1, QtCore.QModelIndex()))

    def update(self, status):
        version = int(status["playlist"])
        size = int(status["playlistlength"])

        try:
            if version <> self.version:
                oldSize = len(self.ids)
                if size < oldSize:
                    self.beginRemoveRows(QtCore.QModelIndex(), size, \
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
                        "dataChanged(QModelIndex, QModelIndex)"), \
                       self.row(pos, 0, QtCore.QModelIndex()), \
                        self.row(pos, 1, QtCore.QModelIndex()))
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
                    i = self.ids.row(self.songid)
                    self.songid = PlaylistModel.NO_SONGID
                    self.emit(QtCore.SIGNAL(\
                    "dataChanged(QModelIndex, QModelIndex)"), \
                    self.row(i, 0, QtCore.QModelIndex()), \
                    self.row(i, 1, QtCore.QModelIndex()))
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
                oldIndex = self.ids.row(oldId)
                self.emit(QtCore.SIGNAL(\
                "dataChanged(QModelIndex, QModelIndex)"), \
                self.row(oldIndex, 0, QtCore.QModelIndex()), \
                self.row(oldIndex, 1, QtCore.QModelIndex()))
            except:
                pass

            try:
                newIndex = self.ids.row(self.songid)
                self.emit(QtCore.SIGNAL(\
                "dataChanged(QModelIndex, QModelIndex)"), \
                self.row(newIndex, 0, QtCore.QModelIndex()), \
                self.row(newIndex, 1, QtCore.QModelIndex()))
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
                self.beginRemoveRows(QtCore.QModelIndex(), run[0] - offset, \
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
        self.beginRemoveRows(QtCore.QModelIndex(), run[0] - offset, \
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

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and \
        role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "Name"
            if section == 1:
                return "Time"
        return None

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

    def __init__(self, parent=None):
        super(PlaylistView, self).__init__(parent)
        self.setEnabled(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.setSelectionBehavior(self.SelectRows)
        delete = QtGui.QAction("Delete", self)
        self.connect(delete, QtCore.SIGNAL("triggered()"), self.deleteSlot)
        self.row = None
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
            self.row = self.indexAt(event.pos())
        else:
            self.row = None
        if len(self.selectedIndexes()) > 0:
            display = True
        if display:
            QtGui.QMenu.exec_(self.actions, event.globalPos())

    def deleteSlot(self):
        rows = set()
        for index in self.selectedIndexes():
            rows.add(index.row())
        if self.row:
            rows.add(self.row.row())
        self.model().deleteRows(rows)

    def setModel(self, model):
        self.connect(self, QtCore.SIGNAL("doubleClicked(QModelIndex)"), \
        model.play)
        QtGui.QTreeView.setModel(self, model)
        self.connect(self.selectionModel(), \
        QtCore.SIGNAL("selectionChanged(QItemSelection, QItemSelection)"), \
        self.setLabel)

    def play(self):

        row = -1

        if len(self.selectedIndexes()) > 0:
            row = self.selectedIndexes()[0].row()
        else:
            try:
                # A candidate for refactoring, yes.
                row = self.model().ids.row(self.model().songid)
            except:
                if self.model().rowCount() > 0:
                    row = 0
        if row > -1:
            self.model().playRow(row)

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.ToolTip:

            index = self.indexAt(event.pos())

            if index.isValid():
                tags = [("artist", "Artists: "), ("album", "Album: "), \
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
        self.connect(self, QtCore.SIGNAL("triggered()"), \
        self.connector.toggleConnected)

    def clientConnect(self):
        self.setIcon(kdeui.KIcon("network-disconnect"))
        self.setText("Disconnect from MPD")

    def clientDisconnect(self):
        self.setIcon(kdeui.KIcon("network-connect"))
        self.setText("Connect to MPD")


class StopAction(QtGui.QAction):

    def __init__(self, parent):
        super(StopAction, self).__init__(kdeui.KIcon("media-playback-stop"), \
        "Stop", parent)
        self.setEnabled(False)
        self.connect(self, QtCore.SIGNAL("triggered()"), \
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
        super(PrevAction, self).__init__(kdeui.KIcon("media-skip-backward"), \
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
        super(NextAction, self).__init__(kdeui.KIcon("media-skip-forward"), \
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
        super(SaveAction, self).__init__(kdeui.KIcon("document-save"), \
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

    def __init__(self, parent=None):
        super(PlaylistSaver, self).__init__(parent)

        self.setCaption("Save Playlist")

        self.setButtons(self.ButtonCode(self.Ok | self.Cancel))
        body = QtGui.QWidget(self)
        layout = QtGui.QFormLayout(body)
        self.name = PlaylistSaver.createLineEdit(self)

        layout.addRow(self.tr("&Name"), self.name)
        self.setMainWidget(body)
        self.connect(self, QtCore.SIGNAL("okayClicked()"), self, \
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
    def createLineEdit(cls, parent, inDelegate=False):
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


class ArtLabel(QtGui.QLabel):
    
    """
    A QLabel that scales album art images properly.
    """

    def __init__(self, parent=None):
        
        """ Initializes the art label. """
        
        super(ArtLabel, self).__init__(parent)
        self.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
        self.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

    def resizeEvent(self, event):
        
        """ Handles resize events. """
        
        pixmap = QtGui.QPixmap("hamster.jpg")
        
        pixmapWidth = pixmap.width()
        pixmapHeight = pixmap.height()
        
        if pixmapHeight > 0:
            pixmapRatio = pixmapWidth / pixmapHeight
        else:
            pixmapRatio = pixmapWidth

        w = event.size().width()
        h = event.size().height()

        if h > 0:
            ratio = w / h
        else:
            ratio = w

        if pixmapRatio < ratio:
            self.setPixmap(pixmap.scaledToHeight(h, QtCore.Qt.SmoothTransformation))
        else:
            self.setPixmap(pixmap.scaledToWidth(w, QtCore.Qt.SmoothTransformation))


class UI(kdeui.KMainWindow):

    def __init__(self, client):
        QtGui.QMainWindow.__init__(self)
        self.__c = Client0(self)
        self.__c.open("localhost", 6600) 
        
        client = Client()
        
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

        toolBar.addAction(kdeui.KIcon("configure"), "Configure", \
        self.cfgDlg.exec_)

        connectAction = ConnectAction(self)
        self.connector.addConnectable(connectAction)
        toolBar.addAction(connectAction)

        stopAction = StopAction(self)
        self.connector.addConnectable(stopAction)
        toolBar.addAction(stopAction)

        self.playPauseAction = PlayPauseAction(self)
        self.connector.addConnectable(self.playPauseAction, \
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
        self.connect(self.slider, QtCore.SIGNAL("valueChanged(int)"), \
        self.setSongTime)
        self.connect(self.slider, QtCore.SIGNAL("sliderMoved(int)"), \
        self.setDragging)
        self.connect(self.slider, QtCore.SIGNAL("sliderReleased()"), \
        self.setNotDragging)
        layout.addWidget(self.slider)

        splitter = QtGui.QSplitter()
        layout.addWidget(splitter)
        self.tabs = kdeui.KTabWidget(splitter)
        self.tabs.setTabPosition(QtGui.QTabWidget.West)

        self.dbModels = []

        view = PlaylistsView()
        self.connector.addConnectable(view)
        self.playlistsDelegate = PlaylistsDelegate(self)
        view.setItemDelegate(self.playlistsDelegate)
        self.tabs.addTab(view, "Playlists")

        self.addTab(ArtistsFetcher(), AllUris(), "Artists")
        self.addTab(AlbumsFetcher(), AllUris(), "Albums")
        self.addTab(AllSongsFetcher(), OneUri(), "Songs")
        self.addTab(GenresFetcher(), AllUris(), "Genres")
        self.addTab(ComposersFetcher(), AllUris(), "Composers")
        
        client0 = Client0()
        client0.open("localhost", 6600)
        
        treeModel = TreeModel(RootController(client0))
        treeView = TreeView()
        treeView.setIconSize(QSize(34, 34))
        treeView.setModel(treeModel)
        treeModel.changed.connect(treeView.resizeColumnsToContents)
        self.tabs.addTab(treeView, "New")

        self.playlistModel = PlaylistModel(combinedTime, self)
        self.connector.addConnectable(self.playlistModel, \
        Connector.UPDATEABLE)
        playlistSplitter = QtGui.QSplitter(splitter)
        playlistSplitter.setOrientation(QtCore.Qt.Vertical)
        artLabel = ArtLabel(playlistSplitter)
        artLabel.setPixmap(QtGui.QPixmap("hamster.jpg"))
        self.playlistView = PlaylistView(playlistSplitter)
        self.connector.addConnectable(self.playlistView)
        self.playlistView.setModel(self.playlistModel)
        self.connect(self.playlistModel, QtCore.SIGNAL("playing"), \
        self.setPlaying)
        self.connect(self.playlistModel, QtCore.SIGNAL("saveable"), \
        saveAction.setEnabled)
        self.connect(self.playlistModel, QtCore.SIGNAL("stopped"), \
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
        view = DatabaseView()
        self.connector.addConnectable(view)
        self.tabs.addTab(view, label)

    def connectDBModels(self):
        for model in self.dbModels:
            self.connect(model, QtCore.SIGNAL("uris"), \
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
    aboutData = kdecore.KAboutData(appName, catalog, programName, version, \
    description, license, copyright, text, homePage, bugEmail)

    kdecore.KCmdLineArgs.init(sys.argv, aboutData)
    app = kdeui.KApplication()
    client = MPDClient()
    main = UI(client)
    main.show()
    sys.exit(app.exec_())
