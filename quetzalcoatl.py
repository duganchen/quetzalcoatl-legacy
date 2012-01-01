#!/usr/bin/env python2

from sip import setapi

setapi("QDate", 2)
setapi("QDateTime", 2)
setapi("QTextStream", 2)
setapi("QTime", 2)
setapi("QVariant", 2)
setapi("QString", 2)
setapi("QUrl", 2)

from PyKDE4.kdecore import ki18n, KAboutData, KCmdLineArgs
from PyKDE4.kdeui import KAction, KApplication, KDialog, KIcon, KLineEdit
from PyKDE4.kdeui import KMainWindow
from PyKDE4.kdeui import KMessageBox, KToggleAction
from PyQt4.QtCore import QAbstractItemModel, QByteArray
from PyQt4.QtCore import QDataStream, QEvent, QIODevice, QMimeData
from PyQt4.QtCore import QModelIndex, QObject, QRegExp, QSize, Qt, QTimer
from PyQt4.QtCore import QUrl, pyqtSignal
from PyQt4.QtGui import QFont, QFormLayout, QIcon, QKeySequence, QLabel
from PyQt4.QtGui import QSlider, QPixmap, QRegExpValidator, QSplitter
from PyQt4.QtGui import QToolTip, QTreeView, QVBoxLayout, QWidget
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest
from mpd import MPDClient, MPDError
from base64 import b64decode
import cPickle
from datetime import datetime
import json
from os import makedirs, path
import posixpath
from select import EPOLLIN, epoll
import socket
from urllib import urlencode
from urlparse import parse_qs, urlparse, urlunsplit
from sys import argv, exit
from xdg import BaseDirectory


def main():
    appName = "Quetzalcoatl"
    catalog = ""
    programName = ki18n("Quetzalcoatl")
    version = "2.0"
    description = ki18n("MPD client")
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

        self.__play_action = KAction(KIcon('media-playback-start'), 'Play',
                self)
        self.__play_action.setShortcut(QKeySequence(Qt.Key_MediaPlay))

        self.__play_action.triggered.connect(controller.play)
        self.__toolbar.addAction(self.__play_action)

        self.__pause_action = KAction(KIcon('media-playback-pause'), 'Pause',
                self)
        self.__pause_action.setShortcut(QKeySequence(Qt.Key_MediaPause))

        self.__pause_action.triggered.connect(controller.pause)

        self.__skip_backward_action = KAction(KIcon('media-skip-backward'),
                'Previous', self)
        self.__skip_backward_action.setShortcut(QKeySequence(
            Qt.Key_MediaPrevious))
        self.__skip_backward_action.triggered.connect(controller.skip_backward)
        self.__toolbar.addAction(self.__skip_backward_action)

        skip_forward_action = KAction(KIcon('media-skip-forward'), 'Next',
                self)
        skip_forward_action.setShortcut(QKeySequence(Qt.Key_MediaNext))

        skip_forward_action.triggered.connect(controller.skip_forward)
        self.__toolbar.addAction(skip_forward_action)

        self.__toolbar.addSeparator()

        shuffle = KToggleAction(KIcon('media-playlist-shuffle'), 'Shuffle',
                self)
        poller.shuffle_changed.connect(shuffle.setChecked)
        shuffle.toggled.connect(controller.set_shuffle)
        self.__toolbar.addAction(shuffle)

        repeat = KToggleAction(KIcon('media-playlist-repeat'), 'Repeat', self)
        poller.repeat_changed.connect(repeat.setChecked)
        repeat.toggled.connect(controller.set_repeat)
        self.__toolbar.addAction(repeat)

        self.__toolbar.addSeparator()

        delete = KAction(KIcon('list-remove'),
                '[DEL]ete selected playlist items', self)
        delete.setShortcut(QKeySequence(Qt.Key_Delete))
        self.__toolbar.addAction(delete)

        save_playlist = KAction(KIcon('document-save-all'),
                '[CTRL-S]ave playlist', self)
        save_playlist.setShortcut(QKeySequence('CTRL+S'))
        self.__toolbar.addAction(save_playlist)

        splitter = QSplitter()
        self.__slider = QSlider(Qt.Horizontal)
        self.__slider.setTracking(False)
        layout.addWidget(self.__slider)
        self.__slider.sliderMoved.connect(controller.setElapsed)
        self.__slider.sliderPressed.connect(self.__hold_slider)
        self.__slider.sliderReleased.connect(controller.seekToElapsed)
        self.__slider.sliderReleased.connect(self.__release_slider)
        layout.addWidget(splitter)

        icon_manager = IconManager(self)

        database_view = DatabaseView()
        splitter.addWidget(database_view)
        database_model = DatabaseModel(client, icon_manager)
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
        database_view.setHeaderHidden(True)
        playlist_view = PlaylistView()
        playlist_view.combined_timed_changed.connect(self.__set_combined_time)

        delete.triggered.connect(playlist_view.delete_selected)

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
        self.__combined_time = QLabel()
        self.__status_bar.addPermanentWidget(self.__combined_time)

        playlist_model.playlist_changed.connect(
                playlist_view.resizeColumnsToContents)

        self.__state = 'STOP'
        self.__elapsed = 0
        self.__total = 0
        self.__slider_is_held = False

        poller.updated.connect(database_model.update)
        poller.stored_playlist_updated.connect(
                database_model.update_stored_playlist)

        timer = QTimer(self)
        timer.timeout.connect(poller.poll)
        timer.setInterval(1000)
        poller.start()
        poller.poll()
        timer.start()
        playlist_view.setDragEnabled(True)

        playlist_saver = PlaylistSaver(client, self)
        save_playlist.triggered.connect(playlist_saver.show)

    def __set_time(self, elapsed, total):
        if self.__state != 'STOP':
            if self.__elapsed == elapsed and self.__total != total:
                return

            self.__status_bar.showMessage('{0}/{1}'.format(
                Item.time_str(elapsed), Item.time_str(total)))

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
                self.__toolbar.insertAction(self.__skip_backward_action,
                        self.__pause_action)
                self.__slider.setEnabled(True)
            if self.__state == 'pause' or state == 'stop' and \
                self.__pause_action in actions:

                self.__toolbar.removeAction(self.__pause_action)
                self.__toolbar.insertAction(self.__skip_backward_action,
                        self.__play_action)
                self.__slider.setEnabled(True)

    def __hold_slider(self):
        self.__slider_is_held = True

    def __release_slider(self):
        self.__slider_is_held = False

    def __set_combined_time(self, time):
        self.__combined_time.setText(time)


class UIController(QObject):
    """
    The UI class's slots.
    """

    # To signal that we need to poll.
    server_updated = pyqtSignal()

    def __init__(self, client, parent=None):
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
        print 'skipping forward'
        self.server_updated.emit()
        print 'done'

    def set_state(self, state):

        if state != self.__state:
            self.__state = state


class PlaylistSaver(KDialog):

    def __init__(self, client, parent=None):
        super(PlaylistSaver, self).__init__(parent)
        self.__client = client

        self.setCaption("Save Playlist")

        self.setButtons(self.ButtonCode(self.Ok | self.Cancel))
        body = QWidget(self)
        layout = QFormLayout(body)
        self.__name = PlaylistSaver.createLineEdit(self)
        layout.addRow(self.tr("&Name"), self.__name)
        self.setMainWidget(body)

    def accept(self):
        name = self.__name.text().strip()
        if self.isOkay(name.encode("utf-8"), self):
            self.__client.save(name.encode('utf-8'))

    def isOkay(self, name, parent):

        if len(name) == 0:
            return False

        if name[0] == ".":
            KMessageBox.error(parent, "Playlist names may not begin "\
            "with a period.")
            return False

        matched = False
        for check in self.__client.listplaylists():
            if check["playlist"] == name:
                matched = True
                break
        if matched:
            KMessageBox.error(parent, "A playlist by that name "\
            "already exists.")
            return False

        return True

    @classmethod
    def createLineEdit(cls, parent):
        lineEdit = KLineEdit()
        rx = QRegExp("^[^\/]+$")
        lineEdit.setValidator(QRegExpValidator(rx, parent))
        # Plus dot, plus extension, makes 255.
        lineEdit.setMaxLength(251)
        return lineEdit


class ItemView(QTreeView):
    def __init__(self, parent=None):
        super(ItemView, self).__init__(parent)
        # The icon size chosen accomodates both
        # last.fm icons and Oxygen icons.
        self.setIconSize(QSize(34, 34))
        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True)

    def viewportEvent(self, event):

        if event.type() == QEvent.ToolTip:
            index = self.indexAt(event.pos())
            if index.isValid():
                song = index.internalPointer()
                tag_values = []

                # Songs and non-songs (like 'Genres') have different flags.
                if song.flags & Qt.ItemIsSelectable:
                    for tag in ('title', 'track', 'album', 'disc', 'artist',
                            'albumartist', 'composer', 'genre'):
                        if tag in song:
                            value = song[tag]
                            if tag != 'track' and tag != 'disc':
                                value = value.decode('utf-8')
                            tag_values.append(u'{0}: {1}'.format(tag, value))
                if len(tag_values) > 0:
                    QToolTip.showText(event.globalPos(), '\n'.join(tag_values))
                    return True

        return super(ItemView, self).viewportEvent(event)


class DatabaseView(ItemView):

    def __init__(self, parent=None):
        super(DatabaseView, self).__init__(parent)
        self.doubleClicked.connect(self.__handleDoubleClick)

    def __handleDoubleClick(self, index):

        if len(self.selectedIndexes()) == 1:
            self.model().handleDoubleClick(index)
            return

        self.model().play_indexes(self.selectedIndexes(), index)


class PlaylistView(ItemView):

    """ The playlist view. """

    combined_timed_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Initializes to default values.
        """

        super(PlaylistView, self).__init__(parent)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        self.__is_resized = False

    def resizeColumnsToContents(self):
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)

    def delete_selected(self):
        self.model().delete(self.selectedIndexes())

    def selectionChanged(self, selected, deselected):
        super(PlaylistView, self).selectionChanged(selected, deselected)

        if len(self.selectedIndexes()) == 0:
            self.combined_timed_changed.emit('')
            return

        total_time = 0
        for index in self.selectedIndexes():
            song = index.internalPointer()
            if 'time' in song:
                total_time += song['time']

        self.combined_timed_changed.emit(Item.time_str(total_time))


class ItemModel(QAbstractItemModel):

    """ The Quetzalcoatl item model. """

    server_updated = pyqtSignal()

    def __init__(self, client, root, icon_manager, parent=None):
        super(ItemModel, self).__init__(parent)
        self.__root = root
        self.__root.has_children = True
        self.__headers = ['0', '1']
        self.__client = client
        self.__icon_manager = icon_manager

    def data(self, index, role=Qt.DisplayRole):
        item = self.itemFromIndex(index)
        if role == Qt.DecorationRole and index.column() == 0:
            if item.is_song:
                return self.__icon_manager.icon(item.song)
            return item.icon
        if role == Qt.DisplayRole:
            return item.data(index).decode('utf-8')
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
        rows = parent.fetch_more(self.__client)

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

    def play_indexes(self, indexes, index):
        """
        For when adding selected indexes. Takes the indexes, and
        the index to play.
        """

        self.client.clear()
        for current_index in indexes:
            song = self.itemFromIndex(current_index)
            songid = self.client.addid(song['file'])
            if index == current_index:
                self.client.playid(songid)
        self.server_updated.emit()

    @property
    def children(self):
        """ Returns an iterator for the children. """
        return self.__root.children


class DatabaseModel(ItemModel):
    def __init__(self, client, icon_manager, parent=None):
        root = Item()
        root.has_children = True
        super(DatabaseModel, self).__init__(client, root, icon_manager, parent)

    def columnCount(self, parent_index=QModelIndex()):
        return 1

    def mimeTypes(self):
        return ['x-application/vnd.mpd.uri']

    def mimeData(self, indexes):
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.WriteOnly)
        for index in sorted(indexes, key=lambda x: x.row(), reverse=True):
            stream.writeString(index.internalPointer()['file'])
        mime_data = QMimeData()
        mime_data.setData(self.mimeTypes()[0], encoded_data)

        return mime_data

    def update(self):
        """
        Handles the "server updated" signal"
        """
        print 'Server Updated'

    def update_stored_playlist(self):
        print 'Stored playlist updated'


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

        # MPD just doesn't have a single command to move a single song in the
        # playlist to the end. So songs in the playlist can only be dragged
        # to a valid drop point.
        if data.hasFormat('x-application/vnd.mpd.songid') and row != -1:
            encoded_data = data.data('x-application/vnd.mpd.songid')
            stream = QDataStream(encoded_data, QIODevice.ReadOnly)
            while not stream.atEnd():
                source_row = stream.readUInt16()
                songid = stream.readUInt16()
                dest_row = row - 1 if source_row < row else row
                self.client.moveid(songid, dest_row)

            self.server_updated.emit()
            self.playlist_changed.emit()

            return True

        if data.hasFormat('x-application/vnd.mpd.uri'):
            encoded_data = data.data('x-application/vnd.mpd.uri')
            stream = QDataStream(encoded_data, QIODevice.ReadOnly)
            uris = []
            while not stream.atEnd():
                uris.append(stream.readString())
            if row == -1:
                uris.reverse()

            for uri in uris:
                if row == -1:
                    self.client.add(uri)
                else:
                    self.client.addid(uri, row)

            self.server_updated.emit()
            self.playlist_changed.emit()
            return True

        return False

    def flags(self, index):
        if index.isValid() and index.column() == 0:
            return self.itemFromIndex(index).flags
        if index.isValid() and index.column() > 0:
            return Qt.ItemIsEnabled
        if not index.isValid():
            # invalid indexes have a row and column of -1.
            return Qt.ItemIsDropEnabled

    def mimeTypes(self):
        return ['x-application/vnd.mpd.songid',
                'x-application/vnd.mpd.uri']

    def mimeData(self, indexes):
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.WriteOnly)
        for index in sorted(indexes, key=lambda x: x.row(), reverse=True):
            stream.writeUInt16(index.row())
            stream.writeUInt16(index.internalPointer()['id'])
        mime_data = QMimeData()
        mime_data.setData(self.mimeTypes()[0], encoded_data)

        return mime_data

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.FontRole and index.internalPointer()['id'] == \
                self.__songid:
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
            if song['id'] == old_id or song['id'] == self.__songid:
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

    def delete(self, indexes):

        for id in set(index.internalPointer()['id'] for index in indexes):
            self.client.deleteid(id)
        self.server_updated.emit()

    def set_raw_data(self, row, value):
        index = self.index(row, 0)
        item = self.itemFromIndex(index)
        item.set_raw_data(value)
        self.dataChanged.emit(index, self.index(row, 1))


class Item(object):
    """ A model item. """

    icons = {}
    icons['view-media-playlist'] = QIcon(KIcon('view-media-playlist'))
    icons['audio-x-generic'] = QIcon(KIcon('audio-x-generic'))
    icons['folder-favorites'] = QIcon(KIcon('folder-favorites'))
    icons['folder-documents'] = QIcon(KIcon('folder-documents'))
    icons['server-database'] = QIcon(KIcon('server-database'))
    icons['drive-harddisk'] = QIcon(KIcon('drive-harddisk'))
    icons['folder-sound'] = QIcon(KIcon('folder-sound'))
    icons['media-optical-audio'] = QIcon(KIcon('media-optical-audio'))

    def __init__(self, parent=None):
        """
        Creates an Item with the most
        boring default settings possible.
        """
        self.__parent_item = parent
        self.__child_items = []
        self.__can_fetch_more = False
        self.__has_children = False
        self.__flags = Qt.NoItemFlags

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

    def data(self, index):
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

        return None

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
        return posixpath.splitext(posixpath.basename(song["file"]))[0]

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
        self.flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | \
                Qt.ItemIsDragEnabled
        self.has_children = False
        self.can_fetch_more = False
        self.set_raw_data(song)
        self.__icon = self.icons['audio-x-generic']

    def __getitem__(self, key):
        return self.__song[key]

    def __contains__(self, key):
        return key in self.__song

    def data(self, index):
        if index.column() == 0:
            return self.__label

        if index.column() == 1:
            return self.__time

        return None

    @property
    def icon(self):
        return self.__icon

    def set_raw_data(self, song):
        self.__song = song
        self.__label = self.title(song)

        # Internet streams (which may be added by other clients, of course...)
        # don't have times.
        self.__time = self.time_str(song['time']) if 'time' in song else None

    @property
    def is_song(self):
        return True
    
    @property
    def song(self):
        return self.__song


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

        client.playid(client.addid(self['file']))

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

        client.clear()

        for uri in (song['file'] for song in self.parent.children):
            songid = client.addid(uri)

            if uri == self['file']:
                client.playid(songid)

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
        self.__icon = self.icons[icon_name]
        self.has_children = True
        self.can_fetch_more = True
        self.flags = Qt.ItemIsEnabled
        self.__label = label

    def data(self, index):
        if index.column() == 0:
            return self.__label

        return None

    @property
    def icon(self):
        return self.__icon

    @classmethod
    def has_tag(cls, song, tag):
        return tag in song and len(song[tag].strip()) > 0

    @classmethod
    def match_tag(cls, song, tag, value):
        return tag in song and song[tag] == value

    @classmethod
    def sorted_album(cls, songs):
        track = lambda song: song['track'] if 'track' in song else\
                cls.title(song)
        disc = lambda song: song['disc'] if 'disc' in song else None
        return [AlbumSong(song) for song in sorted(sorted(songs, key=track),
            key=disc)]

    @property
    def is_song(self):
        return False


class AllSongs(ExpandableItem):
    """
    The navigation node for all songs.
    """

    def __init__(self):
        super(AllSongs, self).__init__('Songs', 'server-database')

        self.icon_manager = IconManager()

    def fetch_more(self, client):
        songs = (x for x in client.listallinfo() if 'file' in x)

        return [RandomSong(x) for x in sorted(songs,
            key=self.alphabetical_order)]


class Playlists(ExpandableItem):
    """
    The node for the stored playlists.
    """

    def __init__(self):
        super(Playlists, self).__init__('Playlists', 'folder-favorites')

    def fetch_more(self, client):

        # Sample listsplaylists() value:
        # [{'last-modified': '2011-09-18T06:05:42Z', 'playlist': 'test'}]

        return [Playlist(x['playlist']) for x
                in sorted(client.listplaylists(),
                          key=lambda x: x['playlist'].lower())]


class Playlist(ExpandableItem):
    """
    Playlists->Playlist. Left side.
    """

    def __init__(self, playlist):
        super(Playlist, self).__init__(playlist, 'view-media-playlist')
        self.__playlist = playlist

    def fetch_more(self, client):
        # AlbumSong, for the double-click behavior.
        return [RandomSong(x) for x
                in client.listplaylistinfo(self.__playlist)]


class Artists(ExpandableItem):
    """
    The Artists node.
    """

    def __init__(self):
        super(Artists, self).__init__('Artists', 'server-database')

    def fetch_more(self, client):
        artists = (artist for artist in client.list('artist')
                if len(artist.strip()) > 0)
        return [Artist(artist) for artist in sorted(artists, key=str.lower)]


class Artist(ExpandableItem):
    """
    Artists -> Artist
    """

    def __init__(self, artist):
        super(Artist, self).__init__(artist, 'folder-sound')
        self.__artist = artist

    def fetch_more(self, client):
        works = [ArtistSongs(self.__artist)]
        albums = (album for album in client.list('album', self.__artist)
                if len(album.strip()) > 0)
        works.extend([ArtistAlbum(self.__artist, album)
                for album in sorted(albums, key=str.lower)])
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
        return [RandomSong(x) for x in sorted(songs,
            key=self.alphabetical_order)]


class ArtistAlbum(ExpandableItem):

    def __init__(self, artist, album):
        super(ArtistAlbum, self).__init__(album, 'media-optical-audio')
        self.__artist = artist
        self.__album = album

    def fetch_more(self, client):
        return self.sorted_album(song for song
                in client.find('album', self.__album)
                if 'artist' in song and song['artist'] == self.__artist)


class Albums(ExpandableItem):
    """
    The Artists node.
    """

    def __init__(self):
        super(Albums, self).__init__('Albums', 'server-database')

    def fetch_more(self, client):
        albums = (album for album in client.list('album')
                if len(album.strip()) > 0)
        return [Album(album) for album in sorted(albums, key=str.lower)]


class Album(ExpandableItem):
    """
    Albums -> Album
    """

    def __init__(self, album):
        super(Album, self).__init__(album, 'media-optical-audio')
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
        album_artists = (album_artist for album_artist
                in client.list('albumartist')
                if len(album_artist.strip()) > 0)
        return [AlbumArtist(artist) for artist
                in sorted(album_artists, key=str.lower)]


class AlbumArtist(ExpandableItem):

    def __init__(self, albumartist):
        super(AlbumArtist, self).__init__(albumartist, 'folder-sound')
        self.__albumartist = albumartist

    def fetch_more(self, client):
        return [Compilation(self.__albumartist, album) for album
                in sorted(set(song['album'] for song
                    in client.find('albumartist', self.__albumartist)
                    if self.has_tag(song, 'album')), key=str.lower)]


class Compilation(ExpandableItem):
    """
    Compilations -> Compilation
    """

    def __init__(self, albumartist, album):
        super(Compilation, self).__init__(album, 'media-optical-audio')
        self.__albumartist = albumartist
        self.__album = album

    def fetch_more(self, client):
        return self.sorted_album(song for song
                in client.find('album', self.__album)
                if self.match_tag(song, 'albumartist', self.__albumartist))


class Genres(ExpandableItem):
    """
    The Genres node.
    """

    def __init__(self):
        super(Genres, self).__init__('Genres', 'server-database')

    def fetch_more(self, client):
        genres = (genre for genre in client.list('genre')
                if len(genre.strip()) > 0)
        return [Genre(genre) for genre in sorted(genres, key=str.lower)]


class Genre(ExpandableItem):
    """
    Genres -> Genre
    """

    def __init__(self, genre):
        super(Genre, self).__init__(genre, 'folder-sound')
        self.__genre = genre

    def fetch_more(self, client):
        works = [GenreSongs(self.__genre)]
        raw_artists = (song['artist'] for song in client.find('genre',
            self.__genre) if self.__is_valid(song))
        artists = sorted(set(raw_artists), key=str.lower)
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
        return [RandomSong(x) for x in sorted(songs,
            key=self.alphabetical_order)]


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
        raw_albums = (song['album'] for song in client.find('artist',
            self.__artist) if self.__is_valid(song))
        albums = sorted(set(raw_albums), key=str.lower)
        works.extend([GenreArtistAlbum(self.__genre, self.__artist, album)
            for album in albums])
        return works

    def __is_valid(self, song):
        return self.match_tag(song, 'genre',
                self.__genre) and self.has_tag(song, 'album')


class GenreArtistSongs(ExpandableItem):
    """
    Genre->Artist->All Songs
    """
    def __init__(self, genre, artist):
        super(GenreArtistSongs, self).__init__('All Songs', 'server-database')
        self.__genre = genre
        self.__artist = artist

    def fetch_more(self, client):
        songs = (song for song in client.find('artist', self.__artist)
                if self.match_tag(song, 'genre', self.__genre))
        return [RandomSong(x) for x
                in sorted(songs, key=self.alphabetical_order)]


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
        return self.sorted_album(song for song in album_songs
                if 'genre' in song and self.__is_valid(song))

    def __is_valid(self, song):
        return self.match_tag(song, 'genre', self.__genre) and self.match_tag(
                song, 'artist', self.__artist)


class Composers(ExpandableItem):
    """
    The Composers node.
    """

    def __init__(self):
        super(Composers, self).__init__('Composers', 'server-database')

    def fetch_more(self, client):
        composers = (composer for composer in client.list('composer')
                if len(composer.strip()) > 0)
        return [Composer(composer) for composer
                in sorted(composers, key=str.lower)]


class Composer(ExpandableItem):
    """
    Composers -> Composer
    """
    def __init__(self, composer):
        super(Composer, self).__init__(composer, 'folder-sound')
        self.__composer = composer

    def fetch_more(self, client):
        works = [ComposerSongs(self.__composer)]
        raw_albums = (song['album'] for song
                in client.find('composer', self.__composer)
                if self.__is_valid(song))
        albums = sorted(set(raw_albums), key=str.lower)
        works.extend([ComposerAlbum(self.__composer, album) for album
            in albums])
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
        return [RandomSong(x) for x in sorted(songs,
            key=self.alphabetical_order)]


class ComposerAlbum(ExpandableItem):
    """
    Composers -> Composer -> Album
    """
    def __init__(self, composer, album):
        super(ComposerAlbum, self).__init__(album, 'media-optical-audio')
        self.__composer = composer
        self.__album = album

    def fetch_more(self, client):
        return self.sorted_album(song for song
                in client.find('album', self.__album)
                if self.match_tag(song, 'composer', self.__composer))


class Directory(ExpandableItem):
    """
    The Directories node.
    """

    def __init__(self, root, icon):
        super(Directory, self).__init__(root, icon)
        self.__label = posixpath.basename(root) if posixpath.basename(root) == '' else root
        self.__root = root

    def fetch_more(self, client):
        listing = client.lsinfo(self.__root)
        directories = [Directory(directory, 'folder-sound') for directory
                in sorted((x['directory'] for x in listing
                    if 'directory' in x), key=str.lower)]

        files = [RandomSong(song) for song in sorted((x for x in listing
            if 'file' in x), key=self.alphabetical_order)]

        directories.extend(files)
        return directories


class PlaylistItem(Song):
    """
    A song in the playlist.
    """
    def __init__(self, song):
        super(PlaylistItem, self).__init__(song)

    def handleDoubleClick(self, client):
        client.playid(self['id'])
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
    updated = pyqtSignal()
    stored_playlist_updated = pyqtSignal()

    def __init__(self, client, parent=None):
        super(Poller, self).__init__(parent)
        self.__client = client
        self.__client.is_connected_changed.connect(self.__set_is_connected)

        self.__status = {}
        self.__set_is_connected(False)

    def start(self):
        """
        Sends the initial poll commands.
        """
        self.__client.send_idle('stored_playlist', 'update')

    def poll(self):

        """
        Polls for updates.

        Connects and disconnects if necessary.
        """

        poll_id = self.__client.poll_id()
        idle_id = self.__client.idle_id()
        self.__client.send_status()

        # Check for idle results
        poll = epoll()
        poll.register(poll_id, EPOLLIN)
        poll.register(idle_id, EPOLLIN)
        result = poll.poll()
        poll.close()

        for fd, event in result:
            if fd == idle_id:
                updates = self.__client.fetch_idle()
                if 'update' in updates:
                    self.updated.emit()
                if 'stored_playlist' in updates:
                    self.stored_playlist_updated.emit()
                self.__client.send_idle('update', 'stored_playlist')

        # The results of the status command will always be there,
        # of course.
        status = self.__client.fetch_status()
        self.__handle_status(status)

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
                    self.playlist_changed.emit(sorted(self.__client.plchanges(
                        self.__status['playlist']), key=lambda x: x['pos']),
                        status['playlistlength'])
            else:
                self.playlist_changed.emit(sorted(self.__client.playlistinfo(),
                    key=lambda x: x['pos']), status['playlistlength'])

        self.__status = status

    def __set_is_connected(self, is_connected):
        """
        Responds to the client changing connection state.
        """

        # Polling on connect is causing problems. We've taken it out.
        if is_connected == False:
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
        self.__idler = None
        self.__commander = None
        self.__wrapped_poller = None

    def open(self):

        if self.__poller is None:
            self.__poller = MPDClient()
            try:
                self.__poller.connect(self.__options['host'],
                        self.__options['port'])
                self.__wrapped_poller = SanitizedClient(self.__poller)
                self.__idler = MPDClient()
                self.__idler.connect(self.__options['host'],
                        self.__options['port'])

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

            try:
                self.__idler.noidle()
            except:
                pass

            try:
                self.__idler.disconnect()
            except:
                pass

            self.is_connected_changed.emit(False)

    def __getattr__(self, attr):
        """
        Allows access to the client's methods.

        Just throws exceptions on error.
        """

        if self.__poller is None:
            self.open()
            # Any exceptions raised here will have propagated.

        if attr in ['send_idle', 'fetch_idle']:
            attribute = getattr(self.__idler, attr)
        else:
            attribute = getattr(self.__wrapped_poller, attr)
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
            self.close()
            raise e

    def poll_id(self):
        return self.__poller.fileno()

    def idle_id(self):
        return self.__idler.fileno()


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

        # Converting server timestamps from UTC to local would require
        # adding dateutil as a dependency. So we don't.

        self.__sanitizers['last-modified'] = lambda x: datetime.strptime(x,
                '%Y-%m-%dT%H:%M:%SZ')

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

        # 'playlist' in status is an integer
        # in ls[all]info it's a filename

        root, ext = posixpath.splitext(value)
        if len(ext.strip()) == 0:
            try:
                return int(value)
            except:
                pass

        return value

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




class IconManager(QObject):

    """
    Manages icons. Including pulling them from last.fm
    """

    icon_loaded = pyqtSignal(str)
    art_loaded = pyqtSignal(str)

    __last_fm_key = b64decode('Mjk1YTAxY2ZhNjVmOWU1MjFiZGQyY2MzYzM2ZDdjODk=')

    __stock_icons = {}
    __stock_icons['ac3'] = QIcon(KIcon('audio-ac3'))
    __stock_icons['mid'] = QIcon(KIcon('audio-midi'))
    __stock_icons['sid'] = QIcon(KIcon('audio-prs.sid'))
    __stock_icons['ra'] = QIcon(KIcon('audio-vn.rn-realmedia'))
    __stock_icons['aiff'] = QIcon(KIcon('audio-x-aiff'))
    __stock_icons['flac'] = QIcon(KIcon('audio-x-flac'))
    __stock_icons['ogg'] = QIcon(KIcon('audio-x-flac+ogg'))
    __stock_icons['ape'] = QIcon(KIcon('audio-x-monkey'))
    __stock_icons['spx'] = QIcon(KIcon('audio-x-speex+ogg'))
    __stock_icons['wav'] = QIcon(KIcon('audio-x-wav'))

    def __init__(self, parent=None):
        super(IconManager, self).__init__(parent)
        self.__network_access_manager = QNetworkAccessManager(self)
        self.__url_mbid = {}
        self.__icon_mbid_filepath = {}
        self.__art_mbid_filepath = {}
        self.__mbid_icon = {}
        self.__mbid_art = {}
        self.__mbids = set()

        try:
            with open(self.__path('mbid_filename'), 'rb') as f:
                self.__icon_mbid_filepath = cPickle.load(f)
        except IOError:
            self.__icon_mbid_filepath = {}

        for mbid, filepath in self.__icon_mbid_filepath:
            # Error handling might be nice here...
            self.__mbid_icon[mbid] = QIcon(filepath)

    def icon(self, song):
        """
        Returns a QIcon showing the album art for the given song. If the icon
        fetched from last.fm, the request is initiated and a icon_loaded
        signal is emitted on success.
        """

        if 'musicbrainz_albumid' in song:
            mbid = song['musicbrainz_albumid']

            if mbid in self.__mbid_icon:
                return self.__mbid_icon[mbid]

            self.__get_album_art(mbid)

        return self.__icon_by_filename(song)

    def close(self):
        """
        Serializes data for when the program is closed.
        """
        with open(self.__path('mbid_filename'), 'wb') as f:
            cPickle.dump(self.__icon_mbid_filepath, f,
                    cPickle.HIGHEST_PROTOCOL)

    def initialize(self):
        for mbid, filepath in self.__icon_mbid_filepath:
            # Error handling might be nice here...
            self.__mbid_icon[mbid] = QIcon(filepath)

    @classmethod
    def __icon_by_filename(self, song):

        _, ext = path.splitext(song['file'])

        if ext in self.__stock_icons:
            return self.__stock_icons[ext]
        return QIcon(KIcon('audio-x-generic'))

    def __get_album_art(self, mbid):
        if mbid in self.__mbids:
            return

        print 'fetching {0}'.format(mbid)

        print self.__mbids

        self.__mbids.add(mbid)
        request = QNetworkRequest()
        request.setUrl(QUrl(self.__album_info_url(mbid)))
        request.setRawHeader('User-Agent', 'Quetzalcoatl 2.0')
        reply = self.__network_access_manager.get(request)
        reply.finished.connect(self.__album_info_downloaded)

    def __album_info_downloaded(self):
        info_reply = self.sender()
        query = urlparse(info_reply.url().toString()).query
        mbid = parse_qs(query)['mbid'][0]

        data = json.loads(info_reply.readAll().data())

        if 'error' in data:
            return

        mega_url = [x['#text'] for x in data['album']['image']
                if x['size'] == 'mega'][0]
        self.__url_mbid[mega_url] = mbid

        mega_request = QNetworkRequest()
        mega_request.setUrl(QUrl(mega_url))
        mega_reply = self.__network_access_manager.get(mega_request)
        mega_reply.finished.connect(self.__art_downloaded)

        small_url = [x['#text'] for x in data['album']['image']
                if x['size'] == 'small'][0]
        self.__url_mbid[small_url] = mbid

        small_request = QNetworkRequest()
        small_request.setUrl(QUrl(small_url))
        small_reply = self.__network_access_manager.get(small_request)
        small_reply.finished.connect(self.__icon_downloaded)

        info_reply.deleteLater()

    def __icon_downloaded(self):
        reply = self.sender()
        mbid = self.__url_mbid[reply.url().toString()]
        filepath = self.__image_downloaded(reply)
        self.__icon_mbid_filepath[mbid] = filepath
        self.__mbid_icon[mbid] = QIcon(filepath)
        self.icon_loaded.emit(mbid)
        reply.deleteLater()

    def __art_downloaded(self):
        reply = self.sender()
        mbid = self.__url_mbid[reply.url().toString()]
        filepath = self.__image_downloaded(reply)
        self.__art_mbid_filepath[mbid] = filepath
        self.__mbid_art[mbid] = QPixmap(filepath)
        self.art_loaded.emit(mbid)
        reply.deleteLater()

    def __image_downloaded(self, reply):
        image_path = path.join(BaseDirectory.xdg_cache_home, 'quetzalcoatl',
                *urlparse(reply.url().toString()).path.split('/')[2:])
        if not path.exists(path.dirname(image_path)):
            makedirs(path.dirname(image_path))
        image = open(image_path, 'wb')
        image.write(reply.readAll())
        image.close()
        return image_path

    @classmethod
    def __path(cls, filename):
        root_path = path.join(BaseDirectory.xdg_cache_home, 'quetzalcoatl')
        if not path.exists(root_path):
            makedirs(root_path)
        return path.join(root_path, filename)

    @classmethod
    def __album_info_url(cls, mbid):
        scheme = 'http'
        netloc = 'ws.audioscrobbler.com'
        path = '/2.0/'
        query = urlencode({'mbid': mbid, 'api_key': cls.__last_fm_key,
            'method': 'album.getinfo', 'format': 'json'})
        fragment = ''
        parts = (scheme, netloc, path, query, fragment)
        return urlunsplit(parts)


if __name__ == "__main__":
    main()
