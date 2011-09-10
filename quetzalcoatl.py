#!/usr/bin/env python2

from sip import setapi

setapi("QDate", 2)
setapi("QDateTime", 2)
setapi("QTextStream", 2)
setapi("QTime", 2)
setapi("QVariant", 2)
setapi("QString", 2)
setapi("QUrl", 2)

from sys import argv, exit
from PyKDE4.kdecore import ki18n, KAboutData, KCmdLineArgs
from PyKDE4.kdeui import KAction, KApplication, KIcon, KMainWindow, KToggleAction
from PyQt4.QtCore import pyqtSignal, QAbstractItemModel, QByteArray, QDataStream, QIODevice, QMimeData, QModelIndex, QObject, QSize, Qt, QTimer
from PyQt4.QtGui import QFont, QHBoxLayout, QIcon, QKeySequence, QLabel, QSlider, QSplitter, QTreeView, QVBoxLayout, QWidget
from posixpath import basename, splitext
from mpd import MPDClient, MPDError
import socket


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

# The play/pause button on both of my multimedia keyboards is Qt.Key_MediaPlay, not
# Qt.Key_MediaTogglePlayPause.

# TO DO:

# Okay, here's the current do-do list:

# * get dragging and dropping from the library to the playlist to work again
# * double-clicking on a song (any of them) should take selections into account (if there are any).
# * removing items from the playlist
# * playlists (saving, renaming, deleting)
# * get the configuration dialog working again (authentication, volume, single, consume, etc)
# * album art downloading
# * refreshing the server

# * make sure alphabetical sorting is case-insensitive
# * make sure playlists aren't listed in the directory listings.
# * test the hell out of losing the connection to the server
# * make sure that events are consistent even when another client is chaning the server state.


# Last.fm API key. Base64-encoded.
LAST_FM_KEY_BASE64 = 'Mjk1YTAxY2ZhNjVmOWU1MjFiZGQyY2MzYzM2ZDdjODk='

def main():
    appName = "Quetzalcoatl"
    catalog = ""
    programName = ki18n("Quetzalcoatl")
    version = "2.0"
    description = ki18n("mpd client")
    license = KAboutData.License_GPL
    copyright = ki18n("(c) 2009 Dugan Chen")
    text = ki18n("none")
    homePage = "www.duganchen.ca"
    bugEmail = "see homepage"
    aboutData = KAboutData(appName, catalog, programName, version, \
    description, license, copyright, text, homePage, bugEmail)

    KCmdLineArgs.init(argv, aboutData)
    app = KApplication()
    main = UI(None)
    main.show()
    exit(app.exec_())

class UI(KMainWindow):

    def __init__(self, client):
        KMainWindow.__init__(self)
        self.setWindowIcon(KIcon("multimedia-player"))
        self.resize(800, 600)
        self.setWindowTitle('Quetzalcoatl')
        
        client = Client({'host': 'localhost', 'port': 6600})
        controller = UIController(client, self)
        poller = Poller(client, self)
        controller.server_updated.connect(poller.poll)
        poller.state_changed.connect(controller.set_state)
        poller.state_changed.connect(self.__set_state)
        poller.time_changed.connect(self.__set_time)
        
#        poller.shuffle_changed.connect(controller.set_shuffle)
#        poller.repeat_changed.connect(controller.set_repeat)

        centralWidget = QWidget(self)
        self.setCentralWidget(centralWidget)
        layout = QVBoxLayout()
        centralWidget.setLayout(layout)
        
        self.__toolbar = self.toolBar('ToolBar')
        
        self.__toolbar.setToolBarsEditable(False)
        self.__toolbar.setToolBarsLocked(True)
        self.__toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        stop_action = KAction(KIcon('media-playback-stop'), 'Stop', self)
        stop_action.setShortcut(QKeySequence(Qt.Key_MediaStop))

        stop_action.triggered.connect(controller.stop)
        self.__toolbar.addAction(stop_action)

        self.__play_action = KAction(KIcon('media-playback-start'), 'Play', self)
        self.__play_action.setShortcut(QKeySequence(Qt.Key_MediaPlay))

        self.__play_action.triggered.connect(controller.play)
        self.__toolbar.addAction(self.__play_action)

        self.__pause_action = KAction(KIcon('media-playback-pause'), 'Pause', self)
        self.__pause_action.setShortcut(QKeySequence(Qt.Key_MediaPause))

        self.__pause_action.triggered.connect(controller.pause)

        self.__skip_backward_action = KAction(KIcon('media-skip-backward'), 'Previous', self)
        self.__skip_backward_action.setShortcut(QKeySequence(Qt.Key_MediaPrevious))
        self.__skip_backward_action.triggered.connect(controller.skip_backward)
        self.__toolbar.addAction(self.__skip_backward_action)

        skip_forward_action = KAction(KIcon('media-skip-forward'), 'Next', self)
        skip_forward_action.setShortcut(QKeySequence(Qt.Key_MediaNext))

        skip_forward_action.triggered.connect(controller.skip_forward)
        self.__toolbar.addAction(skip_forward_action)

        self.__toolbar.addSeparator()

        shuffle = KToggleAction(KIcon('media-playlist-shuffle'), 'Shuffle', self)
        poller.shuffle_changed.connect(shuffle.setChecked)
        shuffle.toggled.connect(controller.set_shuffle)
        self.__toolbar.addAction(shuffle)

        repeat = KToggleAction(KIcon('media-playlist-repeat'), 'Repeat', self)
        poller.repeat_changed.connect(repeat.setChecked)
        repeat.toggled.connect(controller.set_repeat)
        self.__toolbar.addAction(repeat)
        
        splitter = QSplitter()
        self.__slider = QSlider(Qt.Horizontal)
        self.__slider.setTracking(False)
        layout.addWidget(self.__slider)
        self.__slider.sliderMoved.connect(controller.setElapsed)
        self.__slider.sliderPressed.connect(self.__hold_slider)
        self.__slider.sliderReleased.connect(controller.seekToElapsed)
        self.__slider.sliderReleased.connect(self.__release_slider)
        layout.addWidget(splitter)

        database_view = QTreeView()
        database_view.setIconSize(QSize(34, 34))
        
        database_view.setSelectionMode(QTreeView.ExtendedSelection)
        database_view.setDragEnabled(True)
        
        splitter.addWidget(database_view)
        database_model = DatabaseModel(client)
        database_model.append_row(Playlists())
        database_model.append_row(Artists())
        database_model.append_row(Albums())
        database_model.append_row(Compilations())
        database_model.append_row(AllSongs())
        database_model.append_row(Genres())
        database_model.append_row(Composers())
        database_model.append_row(Directory('/', 'drive-harddisk'))
        database_view.setModel(database_model)
        database_view.setDragEnabled(True)
        database_view.doubleClicked.connect(database_model.handleDoubleClick)
        database_view.setHeaderHidden(True)
        playlist_view = PlaylistView()
        
        splitter.addWidget(playlist_view)

        database_model.server_updated.connect(poller.poll)
        playlist_model = PlaylistModel(client, Item())
        playlist_view.doubleClicked.connect(playlist_model.handleDoubleClick)
        playlist_view.setModel(playlist_model)
        poller.playlist_changed.connect(playlist_model.set_playlist)
        poller.song_id_changed.connect(playlist_model.set_songid)
        poller.song_id_changed.connect(controller.set_songid)
        playlist_model.server_updated.connect(poller.poll)
        
        self.__status_bar = self.statusBar()
        combined_time = QLabel()
        self.__status_bar.addPermanentWidget(combined_time)
            
        playlist_model.playlist_changed.connect(playlist_view.resizeColumnsToContents)
        
        self.__state = 'STOP'
        self.__elapsed = 0
        self.__total = 0
        self.__slider_is_held = False

        timer = QTimer(self)
        timer.timeout.connect(poller.poll)
        timer.setInterval(1000)
        poller.poll()
        timer.start()
        
        
    def __set_time(self, elapsed, total):
        if self.__state != 'STOP':
            if self.__elapsed == elapsed and self.__total != total:
                return
        
            self.__status_bar.showMessage('{0}/{1}'.format(Item.time_str(elapsed), Item.time_str(total)))
            
            if not self.__slider_is_held:
                if self.__total != total:
                    self.__slider.setMaximum(total)
                if self.__elapsed != elapsed:
                    self.__slider.setSliderPosition(elapsed)
            
            self.__elapsed = elapsed
            self.__total = total
    
    def __set_state(self, state):

        if state != self.__state:
            self.__state = state
            actions = self.__toolbar.actions()
    
            if self.__state == 'stop':
                self.__status_bar.showMessage('')
                self.__slider.setEnabled(False)
                self.__slider.setSliderPosition(0)
            
            if self.__state == 'play' and  self.__play_action in actions:
                self.__toolbar.removeAction(self.__play_action)
                self.__toolbar.insertAction(self.__skip_backward_action, self.__pause_action)
                self.__slider.setEnabled(True)
            if self.__state == 'pause' or state == 'stop' and self.__pause_action in actions:
                self.__toolbar.removeAction(self.__pause_action)
                self.__toolbar.insertAction(self.__skip_backward_action, self.__play_action)
                self.__slider.setEnabled(True)
    
    def __hold_slider(self):
        self.__slider_is_held = True
    
    def __release_slider(self):
        self.__slider_is_held = False
        

class UIController(QObject):
    """
    The UI class's slots.
    """
    
    # To signal that we need to poll.
    server_updated = pyqtSignal()

    def __init__(self, client, parent = None):
        super(UIController, self).__init__(parent)
        self.__client = client
        
        self.__state = 'STOP'
        self.__songid = None
        self.__repeat = False
        self.__shuffle = False
        self.__elapsed = 0
    
    def set_songid(self, songid):
        self.__songid = songid
    
    def setElapsed(self, value):
        self.__elapsed = value
    
    def seekToElapsed(self):
        if self.__songid is not None and self.__state != 'stop':
            self.__client.seekid(self.__songid, self.__elapsed)
            self.server_updated.emit()
    
    def set_repeat(self, value):
        if value != self.__repeat:
            self.__repeat = value
            self.__client.repeat(int(value))
            self.server_updated.emit()
    
    def set_shuffle(self, value):

        if value != self.__shuffle:

            self.__shuffle = value
            self.__client.shuffle(int(value))
            self.server_updated.emit()

    def stop(self):
        if self.__state != 'stop':
            self.__client.stop()
            self.server_updated.emit()
    
    def play(self):
        if self.__state != 'play':
            self.__client.play()
            self.server_updated.emit()

    def pause(self):
        if self.__state != 'pause':
            self.__client.pause()
            self.server_updated.emit()
    
    def skip_backward(self):
        self.__client.previous()
        self.server_updated.emit()

    def skip_forward(self):
        self.__client.next()
        self.server_updated.emit()
    
    def set_state(self, state):

        if state != self.__state:
            self.__state = state
        

class PlaylistView(QTreeView):
    
    """ The playlist view. """
    
    def __init__(self, parent=None):
        """
        Initializes to default values.
        """
        
        super(PlaylistView, self).__init__(parent)
        
        # The icon size chosen accomodates both
        # last.fm icons and Oxygen icons.
        self.setIconSize(QSize(34, 34))
        
        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True)

        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True);
        self.setAcceptDrops(True);
        self.setDropIndicatorShown(True);#        

        self.__is_resized = False
    
    def resizeColumnsToContents(self):
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)

class ItemModel(QAbstractItemModel):
    
    """ The Quetzalcoatl item model. """

    server_updated = pyqtSignal()
    
    def __init__(self, client, root, parent=None):
        super(ItemModel, self).__init__(parent)
        self.__root = root
        self.__root.has_children = True
        self.__headers = ['0', '1']
        self.__client = client

    def data(self, index, role=Qt.DisplayRole):
        item = self.itemFromIndex(index)
        if role == Qt.DecorationRole and index.column() == 0:
            return item.icon
        if role == Qt.DisplayRole:
            return item.data(index)
        return None

    def flags(self, index):
        
        item = self.itemFromIndex(index)
        if item != self.__root:
            return item.flags
        return Qt.NoItemFlags

    def index(self, row, column, parent_index=QModelIndex()):
        
        if not self.hasIndex(row, column, parent_index):
            return QModelIndex()
        
        parent = self.itemFromIndex(parent_index)
        child = parent.child(row)

        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()
        
    def parent(self, index):
        
        if not index.isValid():
            return QModelIndex()
        
        child = index.internalPointer()
        parent = child.parent
        
        if parent == self.__root:
            return QModelIndex()
        
        return self.createIndex(parent.row, 0, parent)
        
    def rowCount(self, parent_index=QModelIndex()):
        
        if parent_index.column() > 0:
            return 0

        parent = self.itemFromIndex(parent_index)
        return parent.row_count
        
    def columnCount(self, parent_index=QModelIndex()):
        
        return len(self.__headers)
    
    def itemFromIndex(self, index):
        if not index.isValid():
            return self.__root
        return index.internalPointer()
    
    def canFetchMore(self, parent_index):
        
        parent = self.itemFromIndex(parent_index)
        return parent.can_fetch_more
    
    def fetchMore(self, parent_index):
        
        parent = self.itemFromIndex(parent_index)

        try:
            rows = parent.fetch_more(self.__client)
        except (MPDError, socket.error) as e:
            print str(e)
            return

        if len(rows) == 0:
            return

        self.beginInsertRows(parent_index, parent.row_count,
                             parent.row_count + len(rows))
        for row in rows:
            parent.append_row(row)
        self.endInsertRows()
        parent.can_fetch_more = False
            
    def hasChildren(self, parent_index=QModelIndex()):
        parent = self.itemFromIndex(parent_index)
        return parent.has_children
        

    def append_row(self, item):
        """
        Appends an item to the root.
        """

        self.beginInsertRows(QModelIndex(), self.__root.row_count,
                self.__root.row_count)
        self.__root.append_row(item)
        self.endInsertRows()

    def remove_rows(self, row, count):
        """
        Removes count rows from the root, starting at row.
        """
        
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)
        self.__root.remove_rows(row, count)
        self.endRemoveRows()

    def set_raw_data(self, row, value):
        index = self.index(row, 0)
        item = self.itemFromIndex(index)
        item.raw_data = value
        self.dataChanged.emit(index, index)

    @property
    def client(self):
        return self.__client

    def handleDoubleClick(self, index):
        """
        Handles double clicks.

        Defers to the item under the cursor.
        """
        if self.itemFromIndex(index).handleDoubleClick(self.__client):
            self.server_updated.emit()
    
    @property
    def children(self):
        """ Returns an iterator for the children. """
        return self.__root.children

class DatabaseModel(ItemModel):
    def __init__(self, client, parent=None):
        root = Item()
        root.has_children = True
        super(DatabaseModel, self).__init__(client, root, parent)
    
    def columnCount(self, parent_index=QModelIndex()):
        return 1

class PlaylistModel(ItemModel):
    playlist_changed = pyqtSignal()

    def __init__(self, client, root, parent_index=None):
        super(PlaylistModel, self).__init__(client, root, parent_index)
        self.__songid = None
        self.__headers = ('Name', 'Time')

    def set_playlist(self, playlist, length):
        old_length = self.rowCount()
        if length < old_length:
            self.remove_rows(length, old_length - length + 1)

        for song in playlist:
            if song['pos'] < old_length:
                self.set_raw_data(song['pos'], song)
            else:
                self.append_row(PlaylistItem(song))
        
        self.playlist_changed.emit()
   
    def dropMimeData(self, data, action, row, column, parent):
        mime_type = self.mimeTypes()[0]
        if data.hasFormat(mime_type):
            encoded_data = data.data(mime_type)
            stream = QDataStream(encoded_data, QIODevice.ReadOnly)
            root = self.itemFromIndex(QModelIndex())
            dest_row = row
            while not stream.atEnd():
                source_row = stream.readUInt16()
                item = root.child(source_row)
                songid = item.raw_data['id']
                if source_row < dest_row:
                    self.client.moveid(songid, dest_row - 1)
                else:
                    self.client.moveid(songid, dest_row)
                    dest_row += 1

            self.server_updated.emit()
            self.playlist_changed.emit()

            return True
            
        return False

    def flags(self, index):
        if index.isValid():
            flags = self.itemFromIndex(index).flags
            if index.column() > 1:
                flags &= ~Qt.ItemIsDragEnabled
            return flags
        else:
            return Qt.ItemIsDropEnabled

    def mimeTypes(self):
        return ['x-application/vnd.mpd.songid']

    def mimeData(self, indexes):
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.WriteOnly)
        for row in sorted(set(self.itemFromIndex(x).row
                for x in indexes if x.isValid())):
            stream.writeUInt16(row)
        mime_data = QMimeData()
        mime_data.setData(self.mimeTypes()[0], encoded_data)

        
        return mime_data

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.FontRole and index.internalPointer().raw_data['id'] == self.__songid:
            font = QFont()
            font.setBold(True)
            return font
        else:
            return super(PlaylistModel, self).data(index, role)
    
    def set_songid(self, value):
        
        if self.__songid == value:
            return
        
        old_id = self.__songid
        self.__songid = value
        
        for row, song in enumerate(self.children):
            
            # Clear the old song and bold the new one.
            if song.raw_data['id'] == old_id or song.raw_data['id'] == self.__songid:
                self.dataChanged.emit(self.index(row, 0), self.index(row, 1))
        
        self.playlist_changed.emit()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        
        if self.__header_is_valid(section, orientation, role):
            return self.__headers[section]
        return None

    def __header_is_valid(self, section, orientation, role):
        
        if section > len(self.__headers) - 1:
            return False
        if orientation != Qt.Horizontal:
            return False
        if role != Qt.DisplayRole:
            return False
        return True
    


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


    def __init__(self, raw_data=None, parent=None):
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
        self.__raw_data = raw_data

    @property
    def raw_data(self):
        return self.__raw_data

    @raw_data.setter
    def raw_data(self, value):
        self.__raw_data = value

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
    def children(self):
        """
        Returns an iterator for the children.
        """
        return self.__child_items.__iter__()

    @property
    def row_count(self):
        """ Returns the number of children. """
        return len(self.__child_items)
    
    def data(self, index, role=Qt.DisplayRole):
        """
        Returns data for the item's display role..
        
        Default implementation returns the raw data.
        """
        
        return self.__raw_data
    
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
    
    def fetch_more(self, client):
        """
        Fetches and returns a list of child items.
        Does not modify the item.
        Default implementation just returns an empty list.
        """

        return []

    def handleDoubleClick(self, client):
        """
        Handles double clicks.

        Returns True the server information needs to be refreshed.
        """
        
        return False

    @classmethod
    def title(cls, song):
        if 'title' in song:
            return song["title"]
        return splitext(basename(song["file"]))[0]

    @classmethod
    def alphabetical_order(cls, song):
        return cls.title(song).lower()

    @classmethod
    def time_str(cls, dt):
        """
        Given a delta of time (in seconds), returns a formatted string
        representation.
        """
        seconds = dt % 60
        minutes = dt % 3600 / 60
        hours = dt / 3600
        
        if hours == 0 and minutes == 0:
            return '0:{0:02}'.format(seconds)
        if hours == 0:
            return '{0:02}:{1:02}'.format(minutes, seconds)
        return '{0}:{1:02}:{1:02}'.format(hours, minutes, seconds)

class Song(Item):
    
    def __init__(self, song):
        super(Song, self).__init__(song)
        self.flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
        self.icon = self.icons['audio-x-generic']
        self.has_children = False
        self.can_fetch_more = False
        self.__label = self.title(self.raw_data).decode('utf-8')

    def data(self, index):
        if index.column() == 0:
            return self.__label
        return None
    
    @property
    def raw_data(self):
        return super(Song, self).raw_data
    
    @raw_data.setter
    def raw_data(self, value):
        super(Song, self).raw_data = value
        self.__label = self.title(self.raw_data).decode('utf-8')

class RandomSong(Song):
    """
    For songs not sorted by album.
    """
    def __init__(self, song):
        super(RandomSong, self).__init__(song)

    def handleDoubleClick(self, client):
        """
        Reimplementation
        """

        try:
            client.playid(client.addid(self.raw_data['file']))
        except (MPDError, socket.error) as e:
            print str(e)
        
        return True

class AlbumSong(Song):
    """
    Songs in the context of an album.
    """
    
    # The double-click event should send the entire album to the playlist.
    
    def __init__(self, song):
        super(AlbumSong, self).__init__(song)

    def handleDoubleClick(self, client):
        """
        Handles double clicks.

        The callback gets called on completion.
        """
        
        try:
            client.clear()
        except (MPDError, socket.error) as e:
            print str(e)
            return False
        
        for uri in (song.raw_data['file'] for song in self.parent.children):
            try:
                songid = client.addid(uri)
            except (MPDError, socket.error) as e:
                print str(e)
                return False
            
            if uri == self.raw_data['file']:
                try:
                    client.playid(songid)
                except (MPDError, socket.error) as e:
                    print str(e)
                    return False
        return True

class ExpandableItem(Item):
    """
    An expandable item. In the database model.
    """
    
    def __init__(self, label, icon_name):
        """
        Takes a text label and the name of its icon.
        """
        super(ExpandableItem, self).__init__(label)
        self.icon = self.icons[icon_name]
        self.has_children = True
        self.can_fetch_more = True
        self.flags = Qt.ItemIsEnabled

    def data(self, index):
        if index.column() == 0:
            return self.raw_data

        return None

    @classmethod
    def has_tag(cls, song, tag):
        return tag in song and len(song[tag].strip()) > 0
    
    @classmethod
    def match_tag(cls, song, tag, value):
        return tag in song and song[tag] == value
    
    @classmethod
    def sorted_album(cls, songs):
        track = lambda song: song['track'] if 'track' in song else cls.title(song)
        disc = lambda song: song['disc'] if 'disc' in song else None
        return [AlbumSong(song) for song in sorted(sorted(songs, key=track), key=disc)]

class AllSongs(ExpandableItem):
    """
    The navigation node for all songs.
    """
    
    def __init__(self):
        super(AllSongs, self).__init__('Songs', 'server-database')

    def fetch_more(self, client):
        songs = (x for x in client.listallinfo() if 'file' in x)
        return [RandomSong(x) for x in sorted(songs, key=self.alphabetical_order)]

class Playlists(ExpandableItem):
    """
    The node for the stored playlists.
    """
    
    def __init__(self):
        super(Playlists, self).__init__('Playlists', 'folder-documents')
    
    def fetch_more(self, client):
        return []

class Artists(ExpandableItem):
    """
    The Artists node.
    """

    def __init__(self):
        super(Artists, self).__init__('Artists', 'server-database')
    
    def fetch_more(self, client):
        artists = (artist for artist in client.list('artist') if len(artist.strip()) > 0)
        return [Artist(artist) for artist in sorted(artists)]

class Artist(ExpandableItem):
    """
    Artists -> Artist
    """

    def __init__(self, artist):
        super(Artist, self).__init__(artist, 'folder-sound')
        self.__artist = artist
    
    def fetch_more(self, client):
        works = [ArtistSongs(self.__artist)]
        albums = (album for album in client.list('album', self.__artist) if len(album.strip()) > 0)
        works.extend([ArtistAlbum(self.__artist, album)
                for album in sorted(albums)])
        return works

class ArtistSongs(ExpandableItem):
    """
    Artists->Artist->All Songs
    """
    def __init__(self, artist):
        super(ArtistSongs, self).__init__('All Songs', 'server-database')
        self.__artist = artist
    
    def fetch_more(self, client):
        songs = (x for x in client.find('artist', self.__artist))
        return [RandomSong(x) for x in sorted(songs, key=self.alphabetical_order)]

class ArtistAlbum(ExpandableItem):
    
    def __init__(self, artist, album):
        super(ArtistAlbum, self).__init__(album, 'media-optical-audio')
        self.__artist = artist
        self.__album = album
    
    def fetch_more(self, client):
        return self.sorted_album(song for song in client.find('album', self.__album) if 'artist' in song and song['artist'] == self.__artist)

class Albums(ExpandableItem):
    """
    The Artists node.
    """

    def __init__(self):
        super(Albums, self).__init__('Albums', 'server-database')
    
    def fetch_more(self, client):
        albums = (album for album in client.list('album') if len(album.strip()) > 0)
        return [Album(album) for album in sorted(albums)]

class Album(ExpandableItem):
    """
    Albums -> Album
    """
    
    def __init__(self, album):
        super(Album, self).__init__(album, 'folder-sound')
        self.__album = album
    
    def fetch_more(self, client):
        return self.sorted_album(client.find('album', self.__album))

class Compilations(ExpandableItem):
    """
    The Compilations (Album Artists) node.
    """

    def __init__(self):
        super(Compilations, self).__init__('Compilations', 'server-database')
    
    def fetch_more(self, client):
        album_artists = (album_artist for album_artist in client.list('albumartist') if len(album_artist.strip()) > 0)
        return [Compilation(artist) for artist in sorted(album_artists)]

class Compilation(ExpandableItem):
    """
    Compilations -> Compilation
    """
    
    def __init__(self, artist):
        super(Compilation, self).__init__(artist, 'folder-sound')
        self.__artist = artist
    
    def fetch_more(self, client): 
        return self.sorted_album(client.find('albumartist', self.__artist))

class Genres(ExpandableItem):
    """
    The Genres node.
    """

    def __init__(self):
        super(Genres, self).__init__('Genres', 'server-database')
    
    def fetch_more(self, client):
        genres = (genre for genre in client.list('genre') if len(genre.strip()) > 0)
        return [Genre(genre) for genre in sorted(genres)]

class Genre(ExpandableItem):
    """
    Genres -> Genre
    """

    def __init__(self, genre):
        super(Genre, self).__init__(genre, 'folder-sound')
        self.__genre = genre
    
    def fetch_more(self, client):
        works = [GenreSongs(self.__genre)]
        works.append(GenreCompilers(self.__genre))
        raw_artists = (song['artist'] for song in client.find('genre', self.__genre) if self.__is_valid(song))
        artists = sorted(set(raw_artists))
        works.extend([GenreArtist(self.__genre, artist) for artist in artists])
        return works

    @classmethod
    def __is_valid(self, song):
        return self.has_tag(song, 'artist') and self.has_tag(song, 'album')

class GenreSongs(ExpandableItem):
    """
    Genres->Genre->All Songs
    """
    def __init__(self, genre):
        super(GenreSongs, self).__init__('All Songs', 'server-database')
        self.__genre = genre
    
    def fetch_more(self, client):
        songs = (x for x in client.find('genre', self.__genre))
        return [RandomSong(x) for x in sorted(songs, key=self.alphabetical_order)]

class GenreCompilers(ExpandableItem):
    # Genre -> Genre -> Compilations
    
    def __init__(self, genre):
        super(GenreCompilers, self).__init__('Compilations', 'server-database')
        self.__genre = genre
    
    def fetch_more(self, client):
        compilers = set(song['albumartist'] for song in client.find('genre', self.__genre) if self.has_tag(song, 'albumartist'))
        return [GenreCompiler(self.__genre, compiler) for compiler in sorted(compilers, key=str.lower)]

class GenreCompiler(ExpandableItem):
    # Genre -> Genre -> Compilations -> Various Artists
    
    def __init__(self, genre, album_artist):
        super(GenreCompiler, self).__init__(album_artist, 'folder-sound')
        self.__genre = genre
        self.__album_artist = album_artist
    
    def fetch_more(self, client):
        albums = set(song['album'] for song in
                     client.find('albumartist', self.__album_artist)
                     if self.match_tag(song, 'genre', self.__genre))
        return [GenreCompilation(self.__genre, self.__album_artist, album) for album in sorted(albums, key=str.lower)]

class GenreCompilation(ExpandableItem):
    
    """
    Genres -> Genre -> Compilations -> Album Artist -> Album
    """
    
    def __init__(self, genre, album_artist, album):
        super(GenreCompilation, self).__init__(album, 'media-optical-audio')
        self.__genre = genre
        self.__album_artist = album_artist
        self.__album = album
        
    def fetch_more(self, client):
        album_songs = client.find('album', self.__album)
        return self.sorted_album(song for song in album_songs if self.__is_valid(song))
    
    def __is_valid(self, song):
        return self.match_tag(song, 'genre', self.__genre) and self.match_tag(song, 'albumartist', self.__album_artist)


class GenreArtist(ExpandableItem):
    """
    Genres -> Genre -> Artist
    """

    def __init__(self, genre, artist):
        super(GenreArtist, self).__init__(artist, 'folder-sound')
        self.__genre = genre
        self.__artist = artist
    
    def fetch_more(self, client):
        works = [GenreArtistSongs(self.__genre, self.__artist)]
        raw_albums = (song['album'] for song in client.find('artist', self.__artist) if self.__is_valid(song))
        albums = sorted(set(raw_albums))
        works.extend([GenreArtistAlbum(self.__genre, self.__artist, album) for album in albums])
        return works
    
    def __is_valid(self, song):
        return self.match_tag(song, 'genre', self.__genre) and self.has_tag(song, 'album')

class GenreArtistSongs(ExpandableItem):
    """
    Genre->Artist->All Songs
    """
    def __init__(self, genre, artist):
        super(GenreArtistSongs, self).__init__('All Songs', 'server-database')
        self.__genre = genre
        self.__artist = artist
    
    def fetch_more(self, client):
        songs = (song for song in client.find('artist', self.__artist) if self.match_tag(song, 'genre', self.__genre))
        return [RandomSong(x) for x in sorted(songs, key=self.alphabetical_order)]

class GenreArtistAlbum(ExpandableItem):
    
    """
    Genres -> Genre -> Artist -> Album
    """
    
    def __init__(self, genre, artist, album):
        super(GenreArtistAlbum, self).__init__(album, 'media-optical-audio')
        self.__genre = genre
        self.__artist = artist
        self.__album = album
        
    def fetch_more(self, client):
        album_songs = client.find('album', self.__album)
        return self.sorted_album(song for song in album_songs if 'genre' in song and self.__is_valid(song))
    
    def __is_valid(self, song):
        return self.match_tag(song, 'genre', self.__genre) and self.match_tag(song, 'artist', self.__artist)

class Composers(ExpandableItem):
    """
    The Composers node.
    """

    def __init__(self):
        super(Composers, self).__init__('Composers', 'server-database')
    
    def fetch_more(self, client):
        composers = (composer for composer in client.list('composer') if len(composer.strip()) > 0)
        return [Composer(composer) for composer in sorted(composers)]

class Composer(ExpandableItem):
    """
    Composers -> Composer
    """
    def __init__(self, composer):
        super(Composer, self).__init__(composer, 'folder-sound')
        self.__composer = composer
    
    def fetch_more(self, client):
        works = [ComposerSongs(self.__composer)]
        raw_albums = (song['album'] for song in client.find('composer', self.__composer) if self.__is_valid(song))
        albums = sorted(set(raw_albums))
        works.extend([ComposerAlbum(self.__composer, album) for album in albums])
        return works
    
    def __is_valid(self, song):
        return self.has_tag(song, 'album')

class ComposerSongs(ExpandableItem):
    """
    Composers->Composer->All Songs
    """
    def __init__(self, composer):
        super(ComposerSongs, self).__init__('All Songs', 'server-database')
        self.__composer = composer
    
    def fetch_more(self, client):
        songs = (x for x in client.find('composer', self.__composer))
        return [RandomSong(x) for x in sorted(songs, key=self.alphabetical_order)]

class ComposerAlbum(ExpandableItem):
    """
    Composers -> Composer -> Album
    """
    def __init__(self, composer, album):
        super(ComposerAlbum, self).__init__(album, 'media-optical-audio')
        self.__composer = composer
        self.__album = album
    
    def fetch_more(self, client):
        return self.sorted_album(song for song in client.find('album', self.__album) if self.match_tag(song, 'composer', self.__composer))

class Directory(ExpandableItem):
    """
    The Directories node.
    """

    def __init__(self, root, icon):
        super(Directory, self).__init__(root, icon)
        self.__root = root
        if basename(root) != '':
            self.raw_data = basename(root)
    
    def fetch_more(self, client):
        listing = client.lsinfo(self.__root)

        directories = [Directory(directory, 'folder-sound') for directory in sorted((x['directory'] for x in listing if 'directory' in x),
                     key=str.lower)]

        files = [RandomSong(song) for song in sorted((x for x in listing if 'file' in x), key=self.alphabetical_order)]
        
        directories.extend(files)
        return directories


class PlaylistItem(Item):
    """
    A song in the playlist.
    """
    def __init__(self, song):
        super(PlaylistItem, self).__init__(song)
        self.flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
        self.__time_data = self.time_str(self.raw_data['time'])
        self.__title_data = self.title(self.raw_data).decode('utf-8')

    def data(self, index):
        if index.column() == 0:
            return self.__title_data
        if index.column() == 1:
            return self.__time_data 
        return None
    
    @property
    def icon(self):
        return self.icons['audio-x-generic']
    
    def handleDoubleClick(self, client):
        client.playid(self.raw_data['id'])
        return True
    

class Poller(QObject):

    """
    The class that polls for updates.
    """

    playlist_changed = pyqtSignal(list, int)
    repeat_changed = pyqtSignal(bool)
    shuffle_changed = pyqtSignal(bool)
    state_changed = pyqtSignal(str)
    time_changed = pyqtSignal(int, int)
    song_id_changed = pyqtSignal(int)

    def __init__(self, client, parent=None):
        super(Poller, self).__init__(parent)
        self.__client = client
        self.__client.is_connected_changed.connect(self.__set_is_connected)

        self.__status = {}
        self.__set_is_connected(False)

    def poll(self):

        """
        Polls for updates.

        Connects and disconnects if necessary.
        """

        try:
            self.__handle_status(self.__client.status())
        except (MPDError, socket.error) as e:
            print str(e)

    def __handle_status(self, status):
        if self.__is_changed(status, 'repeat'):
            self.repeat_changed.emit(status['repeat'])

        if self.__is_changed(status, 'random'):
            self.shuffle_changed.emit(status['random'])

        if self.__is_changed(status, 'state'):
            self.state_changed.emit(status['state'])

        # There is no else. If there is no time, the state is STOP.
        if self.__is_changed(status, 'time') and 'time' in status:
            elapsed, total = status['time']
            self.time_changed.emit(elapsed, total)
            
        if self.__is_changed(status, 'songid'):
            if 'songid' in status:
                self.song_id_changed.emit(status['songid'])
            else:
                self.song_id_changed.emit(None)
        
        if 'playlist' in status:
            if 'playlist' in self.__status:
                if self.__is_changed(status, 'playlist'):
                    self.playlist_changed.emit(sorted(self.__client.plchanges(self.__status['playlist']),
                        key=lambda x: x['pos']), status['playlistlength'])
            else:
                self.playlist_changed.emit(sorted(self.__client.playlistinfo(),
                    key=lambda x: x['pos']), status['playlistlength'])
        
        self.__status = status

    def __set_is_connected(self, is_connected):
        """
        Responds to the client changing connection state.
        """

        if is_connected == True:
            self.poll()
        else:
            self.__reset()

    def __is_changed(self, new_status, key):
        
        if not key in self.__status and not key in new_status:
            return False
        
        if not key in self.__status and key in new_status:
            return True
        
        if key in self.__status and not key in new_status:
            return True
        
        if self.__status[key] != new_status[key]:
            return True
        
        return False

    def __reset(self):
        self.__status = {}
        self.repeat_changed.emit(False)
        self.shuffle_changed.emit(False)
        self.state_changed.emit('STOP')
        self.song_id_changed.emit(None)


class Client(QObject):
    """
    Encapsulates instantiating the clients.
    """

    is_connected_changed = pyqtSignal(bool)

    def __init__(self, options, parent=None):
        super(Client, self).__init__(parent)
        self.__options = options
        self.__poller = None

    def open(self):

        if self.__poller is None:
            client = MPDClient()
            try:
                client.connect(self.__options['host'], self.__options['port'])
                self.__poller = SanitizedClient(client)
                self.is_connected_changed.emit(True)
            except (MPDError, socket.error) as e:
                self.__poller = None
                raise e

    def close(self):
        if self.__poller is not None:
            try:
                self.__poller.disconnect()
            except:
                pass
            self.__poller = None
            self.is_connected_changed.emit(False)

    def __getattr__(self, attr):
        """
        Allows access to the client's methods.

        Just throws exceptions on error.
        """

        if self.__poller is None:
            self.open()
            # Any exceptions raised here will have propagated.

        attribute = getattr(self.__poller, attr)
        if hasattr(attribute, "__call__"):
            return lambda *args: self.__wrapper(attribute, *args)
        return attribute

    def __wrapper(self, method, *args):
        try:
            return method(*args)
        except (MPDError, socket.error) as e:

            # If there's an exception, the signal is emitted.
            # Then the signal is raised. In that order.

            self.is_connected_changed.emit(False)
            self.__poller = None
            raise e

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
        self.__sanitizers['repeat'] = lambda x: bool(int(x))
        self.__sanitizers['consume'] = lambda x: bool(int(x))
        self.__sanitizers['random'] = lambda x: bool(int(x))
        self.__sanitizers['single'] = lambda x: bool(int(x))
        self.__sanitizers['track'] = self.__sanitized_track
        self.__sanitizers['time'] = self.__sanitize_time
        self.__sanitizers['title'] = self.__sanitize_tag
        self.__sanitizers['author'] = self.__sanitize_tag
        self.__sanitizers['album'] = self.__sanitize_tag
        self.__sanitizers['genre'] = self.__sanitize_tag
        self.__sanitizers['album'] = self.__sanitize_tag
        self.__sanitizers['composer'] = self.__sanitize_tag
        self.__sanitizers['albumartist'] = self.__sanitize_tag
        self.__sanitizers['mixrampdb'] = float
        self.__sanitizers['disc'] = self.__sanitized_track
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

class Options(object):

    # Future versions will use KDE's data store
    def __init__(self):
        self.__data = {}

    def __getitem__(self, key):
        return self.__data[key]

    def __setitem__(self, key, value):
        self.__data[key] = value


if __name__ == "__main__":
    main()




