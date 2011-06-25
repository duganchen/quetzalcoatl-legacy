#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# I'm aware of an inefficiency: expanding a node for the first time
# and causing a fetch will cause the view's columns to be resized to the
# contents twice.

# track should be changed. It doubles as length.

from sip import setapi

setapi("QDate", 2)
setapi("QDateTime", 2)
setapi("QTextStream", 2)
setapi("QTime", 2)
setapi("QVariant", 2)
setapi("QString", 2)
setapi("QUrl", 2)

from sys import argv, exit
from PyQt4.QtCore import QAbstractItemModel, QObject
from PyKDE4 import kdecore, kdeui
from PyQt4.QtCore import QSize, Qt, QModelIndex, QTimer, pyqtSignal
from PyKDE4.kdeui import KIcon
from PyQt4.QtGui import QIcon, QTreeView, QMainWindow, QVBoxLayout, QWidget
from PyQt4.QtGui import QSplitter
from posixpath import basename, splitext
from mpd import MPDClient, MPDError
from socket import error

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

class Item(object):
    """ A model item. """

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

    def __init__(self, parent=None):
        """
        Creates an Item with the most
        boring default settings possible.
        """
        self.__parent_item = parent
        self.__child_items = []
        self.__can_fetch_more = False
        self.__icon = None
        self.__has_children = False
        self.__flags = Qt.NoItemFlags
        self.__column_data = {}

    def append_row(self, child):
        """ Adds a child item. """
        child.parent = self
        self.__child_items.append(child)

    def child(self, row):
        """
        Returns the child at the specified row,
        or None if the row is invalid.
        """ 
        try:
            return self.__child_items[row]
        except IndexError:
            return None

    @property
    def row_count(self):
        """ Returns the number of children. """
        return len(self.__child_items)
    
    def data(self, index, role=Qt.DisplayRole):
        """
        Returns data for the item's display role..
        
        Default implementation returns nothing.
        """
        
        return None
    
    @property
    def row(self):
        """ Returns this item's row in its parent. """
        
        if self.__parent_item:
            try:
                return self.__parent_item.__child_items.index(self)
            except ValueError:
                return -1
        return 0
    
    @property
    def parent(self):
        """ Returns the parent item. """
        return self.__parent_item
    
    @parent.setter
    def parent(self, value):
        """ Sets the parent item. """
        self.__parent_item = value
    
    def remove_row(self, row):
        """
        Removes the item at the specified row.
        Does not emit signals.
        """
        del self.__child_items[row]
    
    def remove_rows(self, row, count):
        """
        Removes the specified number of items,
        starting from the specified row.
        Does not emit signals.
        """
        del self.__child_items[row:row + count]
    
    @property
    def icon(self):
        """
        Returns the item's icon.
        """
        return self.__icon
    
    @icon.setter
    def icon(self, value):
        """ Sets the item's icon. """
        self.__icon = value
    
    @property
    def can_fetch_more(self):
        """
        Returns whether there are
        more rows to fetch.
        """
        return self.__can_fetch_more
    
    @can_fetch_more.setter
    def can_fetch_more(self, value):
        """
        Sets whether there are more rows to fetch.
        """
        self.__can_fetch_more = value
    
    @property
    def has_children(self):
        """ Returns whether the item has children. """
        return self.__has_children
    
    @has_children.setter
    def has_children(self, value):
        """ Sets whether the item has children. """
        self.__has_children = value
    
    @property
    def flags(self):
        """ Returns the item's flags. """
        return self.__flags
    
    @flags.setter
    def flags(self, value):
        """ Sets the items's flags. """
        self.__flags = value
    
    def fetch_more(self):
        """
        Fetches and returns a list of child items.
        Does not modify the item.
        Default implementation just returns an empty list.
        """

        return []

    @classmethod
    def title(cls, song):
        if 'title' in song:
            return song["title"]
        return splitext(basename(song["file"]))[0]

    @classmethod
    def random_key(cls, song):
        return cls.title(song).lower()

    @classmethod
    def album_key(cls, song):
        """
        Returns the sorting key for the song. In the context of its album.
        """
        return song['track'] if 'track' in song else cls.title(song).lower()

    @classmethod
    def time_str(cls, second_count):
        """
        Given an integer number of seconds, returns a formatted string
        representation.
        """
        seconds = second_count % 60
        minutes = second_count % 3600 / 60
        hours = second_count / 3600
        
        if hours == 0 and minutes == 0:
            return '0:{0:02}'.format(seconds)
        if hours == 0:
            return '{0:02}:{1:02}'.format(minutes, seconds)
        return '{0}:{1:02}:{1:02}'.format(hours, minutes, seconds)

    def launch(self):
        """
        Handles double clicks. Default implementation is a no-op.
        """
        pass

class RandomItem(Item):
    """
    For songs not sorted by album.
    """
    def __init__(self, song):
        super(RandomItem, self).__init__()
        self.flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
        self.icon = self.icons['audio-x-generic']
        self.has_children = False
        self.can_fetch_more = False
        self.__song = song
    
    def data(self, index):
        if index.column() == 0:
            return self.title(self.__song).decode('utf-8')
        return None

    def launch(self):
        """
        Reimplementation
        """
        print self.__song['file']

class AllSongsItem(Item):
    """
    The navigation node for all songs.
    """
    
    def __init__(self, client):
        super(AllSongsItem, self).__init__()
        self.flags = Qt.ItemIsEnabled
        self.icon = self.icons['server-database']
        self.has_children = True
        self.can_fetch_more = True
        self.__client = client
    
    def data(self, index):
        if index.column() == 0:
            return 'Songs'

        return None

    def fetch_more(self):
        songs = (x for x in self.__client.listallinfo() if 'file' in x)
        return [RandomItem(x) for x in sorted(songs, key=self.random_key)]

class ItemModel(QAbstractItemModel):
    
    """ The Quetzalcoatl item model. """

    def __init__(self, root, parent_index=None):
        """ Initializes the model with default values. """
        
        super(ItemModel, self).__init__(parent_index)
        
        self.__root = root
        self.__root.has_children = True
        self.__headers = ['0', '1']

    def data(self, index, role=Qt.DisplayRole):
        """ reimplementation """
        
        item = self.itemFromIndex(index)
        
        if role == Qt.DecorationRole and index.column() == 0:
            return item.icon
        
        if role == Qt.DisplayRole:
            return item.data(index)
        
        return None

    def flags(self, index):
        """ reimplementation """
        
        item = self.itemFromIndex(index)
        if item != self.__root:
            return item.flags
        return Qt.NoItemFlags

    def index(self, row, column, parent_index=QModelIndex()):
        """ reimplementation """
        
        if not self.hasIndex(row, column, parent_index):
            return QModelIndex()
        
        parent = self.itemFromIndex(parent_index)
        child = parent.child(row)

        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()
        
    def parent(self, index):
        """ reimplementation """
        
        if not index.isValid():
            return QModelIndex()
        
        child = index.internalPointer()
        parent = child.parent
        
        if parent == self.__root:
            return QModelIndex()
        
        return self.createIndex(parent.row, 0, parent)
        
    def rowCount(self, parent_index=QModelIndex()):
        
        """ reimplementation """
        
        if parent_index.column() > 0:
            return 0

        parent = self.itemFromIndex(parent_index)
        return parent.row_count
        
    def columnCount(self, parent_index=QModelIndex()):
        
        """ reimplementation """
        
        return len(self.__headers)
    
    def itemFromIndex(self, index):
        """ Returns the item at the specified index. """
        if not index.isValid():
            return self.__root
        return index.internalPointer()
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        
        """ reimplementation """
        
        if self.__header_is_valid(section, orientation, role):
            return self.__headers[section]
        return None
    
    def setHeaderData(self, section, orientation, value, role=Qt.EditRole):
        """ reimplementation """
        if self.__header_is_valid(section, orientation, role):
            self.__headers[section] = value
            self.headerDataChanged.emit(orientation, section, section)
            return True
        return False
    
    def __header_is_valid(self, section, orientation, role):
        
        """
        Returns whether the parameters refer to a
        valid header.
        """
        
        if section > len(self.__headers) - 1:
            return False
        if orientation != Qt.Horizontal:
            return False
        if role != Qt.DisplayRole:
            return False
        return True
    
    def canFetchMore(self, parent_index):
        """ reimplementation """
        
        parent = self.itemFromIndex(parent_index)
        return parent.can_fetch_more
    
    def fetchMore(self, parent_index):
        
        """ reimplementation """
        
        parent = self.itemFromIndex(parent_index)
        rows = parent.fetch_more()
        if len(rows) == 0:
            return
        self.beginInsertRows(parent_index, parent.row_count,
                             parent.row_count + len(rows))
        for row in rows:
            parent.append_row(row)
        self.endInsertRows()
        parent.can_fetch_more = False
    
    def hasChildren(self, parent_index=QModelIndex()):
        """ reimplementation """
          
        parent = self.itemFromIndex(parent_index)
        return parent.has_children
        
    def launch(self, index):
        """
        Handles double clicks.

        Defers to the item under the cursor.
        """
        self.itemFromIndex(index).launch()

class ItemView(QTreeView):
    
    """ A Quetzalcoatl item view """
    
    def __init__(self, parent=None):
        """
        Initializes to default values.
        """
        
        super(ItemView, self).__init__(parent)
        
        # The icon size chosen accomodates both
        # last.fm icons and Oxygen icons.
        self.setIconSize(QSize(34, 34))
        
        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True)

        self.expanded.connect(self.resizeColumnsToContents)
        self.collapsed.connect(self.resizeColumnsToContents)
        
    def resizeColumnsToContents(self):
        """
        Resizes columns to match their contents.
        """
        if self.model():
            for i in xrange(self.model().columnCount()):
                self.resizeColumnToContents(i) 
    
    def resizeEvent(self, event):
        """ On resize, auto-sizes all columns. """
        super(ItemView, self).resizeEvent(event)
        self.resizeColumnsToContents()

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
        self.__sanitizers['uptime'] = int
        self.__sanitizers['db_update'] = int
        self.__sanitizers['playtime'] = int
        self.__sanitizers['db_playtime'] = int
        self.__sanitizers['repeat'] = bool
        self.__sanitizers['consume'] = bool
        self.__sanitizers['random'] = bool
        self.__sanitizers['single'] = bool
        self.__sanitizers['track'] = self.__sanitized_track
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
    def __sanitize_time(cls, value):
        """
        Returns the sanitized value of time.
        
        value might be in one of two formats:
            'time': '2:151' (elapsed:total)
            'time': '151' (total only)
        """
        
        if ':' in value:
            tokens = value.split(':')
            return tuple([int(x) for x in tokens])
        return int(value)
    
    @classmethod
    def __sanitize_playlist(cls, value):
        """
        lsinfo() and status() can both return a playlist key.
        """
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
            return lambda *args: self.__command(attribute, *args)
        return attribute

class Client(QObject):
    """
    Encapsulates instantiating the clients.
    """

    is_connected_changed = pyqtSignal(bool)
    playlist = pyqtSignal(list, int)

    def __init__(self, parent=None):
        super(Client, self).__init__(parent)
        self.__is_connected = False
        self.__poller = None

    def open(self, host, port):
        if self.__poller is None:
            client = MPDClient()
            try:
                client.connect(host, port)
                self.__poller = SanitizedClient(client)
                self.is_connected = True
            except Exception as e:
                self.is_connected = False

    def close(self):
        if self.__poller is not None:
            try:
                self.__poller.disconnect()
            except:
                pass
            self.__poller = None

    def __getattr__(self, attr):
        """
        Allows access to the client's methods.

        Assumes that the there is a connection.
        """

        attribute = getattr(self.__poller, attr)
        if hasattr(attribute, "__call__"):
            return lambda *args: self.__wrapper(attribute, *args)
        return attribute

    def __wrapper(self, method, *args):
        try:
            return method(*args)
        except Exception as e:
            print str(e)
            self.is_connected = False

    @property
    def is_connected(self):
        return self.__is_connected

    @is_connected.setter
    def is_connected(self, value):
        if value != self.__is_connected:
            self.is_connected_changed.emit(value)
        self.__is_connected = value

class Poller(QObject):

    """
    The class that polls for updates.
    """

    playlist_changed = pyqtSignal(list, int)
    repeat_changed = pyqtSignal(bool)
    random_changed = pyqtSignal(bool)
    state_changed = pyqtSignal(str)

    def __init__(self, client, parent=None):
        super(Poller, self).__init__(parent)
        self.__client = client

        self.__status = {}
        self.set_is_connected(False)
    
    def set_is_connected(self, is_connected):
        """
        Responds to the client changing connection state.
        """
        if not is_connected:
            self.status = {}

            self.status['playlist'] = 0
            self.playlist.emit([], 0)

            self.status['repeat'] = False 
            self.repeat_changed.emit(False)

            self.status['random'] = False
            self.random_changed.emit(False)

            self.status['state'] = 'stop'
            self.state_changed.emit('stop')

    def poll(self):

        """
        Polls for updates.

        Connects and disconnects if necessary.
        """

        if not self.__client.is_connected:
            self.__client.open('localhost', 6600)

        status = self.__client.status()

        if self.client.is_connected:
            if status['playlist'] != self.__status['playlist']:
                playlist = self.__poller.playlistinfo()
                version = status['playlist']
                self.playlist.emit(playlist, version)
                self.__status['playlist'] = status['playlist']
        if self.client.is_connected:
            if status['repeat'] != self.status['repeat']:
                self.repeat_changed.emit(status['repeat'])
                self.__status['repeat'] = status['repeat']
            if status['random'] != self.status['random']:
                self.random_changed.emit(status['random'])
                self.__status['random'] = status['random']
            if status['state'] != self.status['state']:
                self.random_changed.emit(status['state'])
                self.__status['state'] = status['state']

class UI(kdeui.KMainWindow):

    def __init__(self, client):
        QMainWindow.__init__(self)
        self.setWindowIcon(kdeui.KIcon("multimedia-player"))
        self.resize(800, 600)
        self.setWindowTitle('Quetzalcoatl')
        centralWidget = QWidget(self)
        self.setCentralWidget(centralWidget)
        layout = QVBoxLayout()
        centralWidget.setLayout(layout)
        splitter = QSplitter()
        layout.addWidget(splitter)
        client = Client()
        client.open("localhost", 6600)
        root = Item()
        root.append_row(AllSongsItem(client))
        root.append_row(AllSongsItem(client))
        root.has_children = True
        item_view = ItemView()
        splitter.addWidget(item_view)
        item_model = ItemModel(root)
        item_view.setModel(item_model)
        item_view.doubleClicked.connect(item_model.launch)
        item_view.setHeaderHidden(True)

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

    kdecore.KCmdLineArgs.init(argv, aboutData)
    app = kdeui.KApplication()
    main = UI(None)
    main.show()
    exit(app.exec_())
