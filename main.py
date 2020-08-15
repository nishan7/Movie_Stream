import os
import subprocess
import sys
import threading
import urllib
import uuid
import webbrowser
from collections import defaultdict
import reusables
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QScrollArea, QVBoxLayout, \
    QPushButton, QMainWindow, QHBoxLayout, QLabel, QStatusBar, QMenuBar, QSpacerItem, QLineEdit, QComboBox, \
    QMenu, QDialog, QDialogButtonBox, QSlider
from PyQt5.QtGui import QCursor
import requests
from imdb import IMDb
from tmdbv3api import TMDb, Movie
import requests_cache
import player


requests_cache.install_cache('cache')
tmdb = TMDb()
movie = Movie()
IMDB_RATINGS = False

# from database import Network

class Recommender(QtCore.QThread):

    def __init__(self):
        super().__init__()

    def run(self):
        pass


class ThreadedSearcher(QtCore.QThread):
    # Main Class use to update Ui info
    search_result = QtCore.pyqtSignal(list)
    RUNNING = False

    def __init__(self):
        super().__init__()
        self.query = None

    def putStack(self, query):
        self.query = query
        # print(self.query)
        if not self.RUNNING:
            # print(self.stack)
            self.start()

    def run(self):
        self.RUNNING = True
        while self.query:
            movie_search = movie.search(self.query)
            result = []
            for i in range(min(5, len(movie_search))):
                if 'release_date' in movie_search[i].__dict__.keys():
                    result.append((movie_search[i].title, movie_search[i].release_date[:4], movie_search[i].id))

            self.search_result.emit(result)
            self.query = ''
        #     self.end_signal.emit(0)

        self.RUNNING = False

        return


class Updater(QtCore.QThread):
    # Main Class use to update Ui info
    update_signal = QtCore.pyqtSignal(dict)
    RUNNING = False

    def __init__(self):
        super().__init__()
        # self.data = data
        # self.movies = movies
        self.stack = []
        if IMDB_RATINGS:
            self.imdb_obj = IMDb()

    def putStack(self, id):
        self.stack.append(id)
        # print(self.stack)
        if not self.RUNNING:
            # print(self.stack)
            self.run()

    def get_image(self, name, poster_path=None, backdrop_path=None):
        # Args can be left bank, to avoid downloading pictures
        # print(os.chdir('..'))
        # print("*** movie name ***** ", name, "******")
        self.return_value = defaultdict(str)
        if poster_path:
            poster_url = 'https://image.tmdb.org/t/p/w154' + poster_path
            r = requests.get(poster_url)
            with open(os.path.abspath('./media/poster/' + str(name) + '.jpg'), 'wb') as f:
                f.write(r.content)
            self.return_value['poster_value'] = './media/poster/' + str(name) + '.jpg'

        if backdrop_path:
            backdrop_url = 'https://image.tmdb.org/t/p/w780' + backdrop_path
            r = requests.get(backdrop_url)
            with open(os.path.abspath('./media/backdrop/' + str(name) + '.jpg'), 'wb') as f:
                f.write(r.content)
            self.return_value['backdrop_value'] = './media/backdrop/' + str(name) + '.jpg'

        return self.return_value

    def credits(self, credits):
        cast = dict()
        i = 0
        for actor in credits['cast']:
            i += 1
            if (i == 5): break
            cast[actor['name']] = [actor['name'], actor['id']]

        director = []
        for crew in credits['crew']:
            if crew['job'] == 'Director':
                director.append(crew['name'])

        temp = dict()
        temp['cast'] = cast
        temp['director'] = director
        # print(json.dumps(temp, indent=4))
        return temp

    def refresh_disk_data(self):
        disk_json = reusables.load_json('database.json')
        disk_json[self.movie_dat['id']] = self.movie_dat
        reusables.save_json(disk_json, 'database.json', indent=2)

    def search(self, id):
        fetched_data = {}
        det = movie.details(id, append_to_response='append_to_response=videos,images,casts')
        # change_dict['iid'] = det.id  ## name is used a object name in unsearched movie
        fetched_data['id'] = str(det.id)
        # change_dict['Rating'] = str(movie_details['rating'])

        if IMDB_RATINGS: # if imdb ratings are disables, as they are too slow
            rating = self.imdb_obj.get_movie(det.imdb_id[2:]).get('rating')
        else:
            rating=-1

        fetched_data['Rating'] = str(rating)
        fetched_data['Budget'] = str(det.budget // 1000000) + 'M'
        fetched_data['Box Office'] = str(det.revenue // 1000000) + 'M'
        fetched_data['Year'] = det.release_date[:4]
        fetched_data['tagline'] = det.tagline
        fetched_data['imdb_id'] = det.imdb_id
        fetched_data['title'] = det.title
        fetched_data['plot'] = det.overview
        images = self.get_image(det.id, det.poster_path, det.backdrop_path)

        fetched_data['poster_value'] = images['poster_value']
        fetched_data['backdrop_value'] = images['backdrop_value']

        runtime = det.runtime
        fetched_data['runtime_mins'] = runtime
        fetched_data['Duration'] = '{}h {}m'.format(runtime // 60, runtime - (60 * (runtime // 60)))

        credits_list = self.credits(det.casts)

        fetched_data['cast'] = [actor for actor in credits_list['cast'].keys()]

        fetched_data['Director'] = [director for director in credits_list['director']]

        genres_dict = det.genres

        fetched_data['Genre'] = ", ".join([genre["name"] for genre in det.genres])
        # pprint(fetched_data)
        self.movie_dat = fetched_data
        self.refresh_disk_data()
        return self.movie_dat

    def run(self):
        self.RUNNING = True
        # time.sleep(3)
        # Get the info for the needed movies
        while len(self.stack) > 0:
            try:
                movie_data = self.search(self.stack.pop())
                self.update_signal.emit(movie_data)
            except TypeError:
                pass
        # else:
        #     self.end_signal.emit(0)
        self.RUNNING = False

        return


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=-1, hspacing=-1, vspacing=-1):
        super(FlowLayout, self).__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        del self._items[:]

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self):
        if self._hspacing >= 0:
            return self._hspacing
        else:
            return self.smartSpacing(
                QtWidgets.QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._vspacing >= 0:
            return self._vspacing
        else:
            return self.smartSpacing(
                QtWidgets.QStyle.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)

    def expandingDirections(self):
        return QtCore.Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QtCore.QSize(left + right, top + bottom)
        return size

    def doLayout(self, rect, testonly):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        lineheight = 0
        for item in self._items:
            widget = item.widget()
            hspace = self.horizontalSpacing()
            if hspace == -1:
                hspace = widget.style().layoutSpacing(
                    QtWidgets.QSizePolicy.PushButton,
                    QtWidgets.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
            vspace = self.verticalSpacing()
            if vspace == -1:
                vspace = widget.style().layoutSpacing(
                    QtWidgets.QSizePolicy.PushButton,
                    QtWidgets.QSizePolicy.PushButton, QtCore.Qt.Vertical)
            nextX = x + item.sizeHint().width() + hspace
            if nextX - hspace > effective.right() and lineheight > 0:
                x = effective.x()
                y = y + lineheight + vspace
                nextX = x + item.sizeHint().width() + hspace
                lineheight = 0
            if not testonly:
                item.setGeometry(
                    QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = nextX
            lineheight = max(lineheight, item.sizeHint().height())
        return y + lineheight - rect.y() + bottom

    def smartSpacing(self, pm):
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()


class Setting_UI(QDialog):

    def __init__(self, *args, **kwargs):
        super(Setting_UI, self).__init__(*args, **kwargs)

        self.setWindowTitle("Settings")
        self.resize(685, 218)

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addItem(QSpacerItem(10, 35, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred))
        self.layout.addWidget(QLabel('Enter the path for your movies'))
        self.path_line_edit = QLineEdit()

        self.layout.addWidget(self.path_line_edit)
        self.layout.addWidget(self.buttonBox)
        self.layout.setAlignment(Qt.AlignTop)
        self.setLayout(self.layout)


class App(QMainWindow):
    PATH = None

    def __init__(self):
        super().__init__()
        self.old_disk_data = reusables.load_json('database.json')
        self.window_title = 'Movies'
        self.left = 300
        self.top = 300
        self.width = 920
        self.height = 600
        self.data = {}
        tmdb2imdb = {}
        # self.getConfig()
        self.movies = {}  # Contains the id -> title of movies
        self.popular_movies = []
        self.threaded_search = ThreadedSearcher()
        self.threaded_search.search_result.connect(self.search_response)
        self.initUI()
        # Contains all the movies that fetched as popular movies form tmdb at intialization

    def getConfig(self):
        config = reusables.load_json('config.json')
        self.PATH = config['path']

    @QtCore.pyqtSlot(dict)
    def updateData(self, movie):
        self.data[movie['id']] = movie
        self.statusBar.showMessage('Received info about: ' + movie['title'])
        # It is callback function from infoGetter, that tells to update UI
        btn = self.movieAreaContents.findChild(QtWidgets.QToolButton, str(movie['id']))
        if btn:
            btn.setText('{} ({})'.format(movie['title'], movie['Year']))
            icon = QtGui.QIcon()
            icon.addPixmap(QtGui.QPixmap(movie['poster_value']), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            btn.setIcon(icon)

    def infoGetterThreaded(self):
        # It starts the threaded info getter that obtains the images, plots and other info from tmbd (database.py)
        # self.updater = Updater(self.data, self.movies)
        self.updater = Updater()
        self.updater.update_signal.connect(self.updateData)
        self.updater.start()
        # self.insertSearchStack()

    def put_in_updater_stack(self, id):
        # if id not in
        if id in self.old_disk_data.keys():  # If already avaiable disk data is avaiable, use that
            self.updateData(self.old_disk_data[id])
            return
        threading.Thread(target=self.updater.putStack, args=(id,)).start()

    def updateAvailabeInfo(self):
        for iid, info in self.data.items():
            btn = self.movieAreaContents.findChild(QtWidgets.QToolButton, iid)
            btn.setText('{} ({})'.format(info['title'], info['Year']))
            icon = QtGui.QIcon()
            icon.addPixmap(QtGui.QPixmap(info['poster_value']), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            btn.setIcon(icon)

    def initUI(self):
        self.setWindowTitle(self.window_title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        # Topmost widget in the program
        self.mainWigdet = QWidget()
        self.mainWigdet.setObjectName('main Widget')
        self.mainLayout = QVBoxLayout()

        # Gets the toolbar layout from the function
        self.toolbar = self.addToolbar()

        # Layout for the main area of the application ie movieArea & infoArea
        self.mainArea = QHBoxLayout()

        movieArea = self.movieArea()
        self.mainArea.addWidget(movieArea)

        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum,
                                            QtWidgets.QSizePolicy.Expanding)
        self.mainArea.addItem(spacerItem2)

        infoArea = self.infoArea()
        self.mainArea.addWidget(infoArea)

        # Finally setting of the application
        self.mainLayout.addLayout(self.toolbar)
        self.mainLayout.addLayout(self.mainArea)
        self.mainWigdet.setLayout(self.mainLayout)
        self.setCentralWidget(self.mainWigdet)

        self.insertMenuBar()
        self.insertStatusbar()

        # for a in ['title', 'tagline', 'Year', 'Rating', 'Director', 'Duration', 'Genre', 'Budget', 'Box Office',
        #           'cast','plot']:
        #     self.contents.findChild(QLabel, a).setText(a)

        # Call the threaded function, to update the info about the movies simultaneously

        self.infoGetterThreaded()

        # Update the icons for the data that is already avaiable
        self.updateAvailabeInfo()

        #
        self.installEventFilter(self)

        # All the buttons in movieArea, used by search
        self.popular_movies_buttons = self.movieAreaContents.children()[1:]

        for id in self.movies:
            self.put_in_updater_stack(id)

        # print('done')

        # Set the inital infoArea to the first movie on the list
        # if self.movies:
        #     self.showInfoArea(list(self.movies.keys())[0])

    def create_movie_button(self, movie_name, id):
        icon_size = QtCore.QSize(156, 210)
        btn_size = QtCore.QSize(167, 240)
        icon = QtGui.QIcon()

        btn = QtWidgets.QToolButton()
        btn.setText(movie_name)
        btn.setObjectName(str(id))

        # if iid in self.data.keys():  # Already searched movies uses database
        #     btn.setText('{} ({})'.format(self.data[iid]['title'], self.data[iid]['Year']))
        #     btn.setObjectName(str(iid))
        # else:  ## Still unsearched movies uses pathname
        #     btn.setText(movie.split(os.path.sep)[-1])
        #     btn.setObjectName(str(iid))

        path = './media/poster/' + 'na' + '.jpg'
        # print(movie, path)
        icon.addPixmap(QtGui.QPixmap(path), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        btn.setIcon(icon)
        btn.setAutoRaise(True)
        btn.setStyleSheet('''text-align:left;''')
        btn.setIconSize(icon_size)
        btn.setAutoExclusive(True)
        btn.setCheckable(True)
        btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        btn.setFixedSize(btn_size)
        btn.installEventFilter(self)
        self.lyt.addWidget(btn)

    def movieArea(self):
        scrollArea = QScrollArea()  # Main scroll Area
        self.movieAreaContents = QWidget()  # Contents for inside the scroll area i.e. Buttons
        self.setObjectName('movieAreaContents')
        self.lyt = FlowLayout(hspacing=15, vspacing=10)  # Layout for those contents/buttons
        self.lyt.setContentsMargins(0, 0, 0, 50)

        # Setup the properties of scrollbar
        scrollArea.setGeometry(QtCore.QRect(0, 0, 405, 748))
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollArea.setWidgetResizable(True)

        movies = self.getMovieNamesList()
        for iid, movie in movies.items():
            self.create_movie_button(movie, iid)

        self.movieAreaContents.setLayout(self.lyt)
        scrollArea.setWidget(self.movieAreaContents)

        # Register buttons for events
        return scrollArea

    def infoArea(self):
        scrollArea = QScrollArea()  # Main scroll Area
        self.contents = QWidget()  # Contents for inside the scroll area i.e. Buttons
        lyt = QVBoxLayout()  # Layout for those contents/buttons

        # Setup Properties for Content
        self.contents.setGeometry(QtCore.QRect(0, 0, 670, 806))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.contents.sizePolicy().hasHeightForWidth())
        self.contents.setSizePolicy(sizePolicy)
        self.contents.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.contents.setObjectName("info_scroll_area")

        # Setup properties for box layout
        lyt.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        lyt.setSpacing(10)
        lyt.setContentsMargins(10, -1, -1, -1)

        # Setup the properties of scrollarea
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMinimumSize(QtCore.QSize(675, 0))

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(scrollArea.sizePolicy().hasHeightForWidth())
        scrollArea.setSizePolicy(sizePolicy)

        # Basic icon size
        icon_size = QtCore.QSize(154, 210)
        btn_size = QtCore.QSize(154, 240)
        icon = QtGui.QIcon()

        # #Function to rapidly create common heading value rows
        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)

        def infoRow(name):
            row = QHBoxLayout()
            row.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)

            font = QtGui.QFont()
            font.setPointSize(9)
            font.setBold(True)
            font.setWeight(75)

            first = QLabel()
            first.setFont(font)
            first.setText(name)
            first.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop | QtCore.Qt.AlignTrailing)

            font = QtGui.QFont()
            font.setPointSize(9)

            second = QLabel(text='')
            second.setFont(font)
            second.setObjectName(name)
            second.setOpenExternalLinks(True)
            second.setAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

            row.addWidget(first)
            row.addWidget(second)
            return row

        ####    Title
        self.title = QLabel('')
        font = QtGui.QFont()
        font.setFamily("Calibri")
        font.setPointSize(16)
        font.setBold(True)
        font.setWeight(75)
        self.title.setFont(font)
        self.title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.title.setWordWrap(True)
        self.title.setObjectName("title")
        lyt.addWidget(self.title)

        # Backdrop
        self.image = QtWidgets.QVBoxLayout()
        self.image.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.image.setSpacing(0)
        self.image.setObjectName("image")
        self.backdrop_value = QtWidgets.QLabel()
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Ignored)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.backdrop_value.sizePolicy().hasHeightForWidth())
        self.backdrop_value.setSizePolicy(sizePolicy)
        self.backdrop_value.setMinimumSize(QtCore.QSize(624, 351))
        self.backdrop_value.setMaximumSize(QtCore.QSize(624, 351))
        self.backdrop_value.setPixmap(QtGui.QPixmap("./media/backdrop/na.jpg"))
        self.backdrop_value.setScaledContents(True)
        # self.setStyleSheet('''padding: 0px 0px 0px 0px;''')
        self.backdrop_value.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.backdrop_value.setObjectName("backdrop_value")
        self.image.addWidget(self.backdrop_value)

        # Poster
        self.poster_value = QtWidgets.QLabel()
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.poster_value.sizePolicy().hasHeightForWidth())
        self.poster_value.setSizePolicy(sizePolicy)
        self.poster_value.setMinimumSize(QtCore.QSize(0, 52))
        self.poster_value.setMaximumSize(QtCore.QSize(16777215, 240))
        self.poster_value.setPixmap(QtGui.QPixmap('./media/poster/na.jpg'))
        self.poster_value.setScaledContents(False)
        self.poster_value.setAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.poster_value.setIndent(0)
        self.poster_value.setStyleSheet('''padding: 0px 0px 0px 40px;''')
        self.poster_value.setObjectName("poster_value")
        self.image.addWidget(self.poster_value)
        lyt.addLayout(self.image)

        ## Tagline
        self.tagline = QLabel(
            text='')
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setWeight(50)
        self.tagline.setFont(font)
        self.tagline.setAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.tagline.setWordWrap(True)
        self.tagline.setObjectName('tagline')
        lyt.addWidget(self.tagline)

        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        lyt.addItem(spacer)

        lyt.addLayout(infoRow('Year'))
        lyt.addLayout(infoRow('Rating'))
        lyt.addLayout(infoRow('Director'))
        lyt.addLayout(infoRow('Duration'))
        lyt.addLayout(infoRow('Genre'))
        lyt.addLayout(infoRow('Budget'))
        lyt.addLayout(infoRow('Box Office'))

        # Cast
        self.cast_box = QtWidgets.QVBoxLayout()
        self.cast_box.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.cast_box.setSpacing(4)

        self.cast = QtWidgets.QLabel(text='Cast')
        font = QtGui.QFont()
        font.setPointSize(9)
        font.setBold(True)
        font.setWeight(75)
        self.cast.setFont(font)
        self.cast.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.cast_box.addWidget(self.cast)

        self.cast_value = QtWidgets.QLabel(text='')
        font = QtGui.QFont()
        font.setPointSize(9)
        self.cast_value.setFont(font)
        self.cast_value.setOpenExternalLinks(True)
        self.cast_value.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.cast_value.setWordWrap(True)
        self.cast_value.setObjectName("cast")
        self.cast_box.addWidget(self.cast_value)

        lyt.addLayout(self.cast_box)

        # Spacer
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        lyt.addItem(spacer)

        # Description
        self.plot_value = QtWidgets.QLabel(text='')
        font = QtGui.QFont()
        font.setPointSize(9)
        self.plot_value.setFont(font)
        self.plot_value.setTextFormat(QtCore.Qt.AutoText)
        self.plot_value.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.plot_value.setWordWrap(True)
        self.plot_value.setObjectName("plot")
        lyt.addWidget(self.plot_value)

        lyt.addItem(QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        # rating_box = QHBoxLayout()
        #
        # self.slider = QSlider(Qt.Horizontal)
        # self.slider.setMinimum(1)
        # self.slider.setMaximum(10)
        # self.slider.setTickInterval(1)
        # self.slider.setTickPosition(QSlider.TicksBelow)

        # self.rating_value = QLabel(text=' (0/5) ')
        #
        # self.slider.valueChanged[int].connect(self.rating_value_changed)
        #
        # rating_box.addWidget(QLabel(text='Your Rating'))
        # rating_box.addWidget(self.slider)
        # rating_box.addWidget(self.rating_value)

        # rating_box.setAlignment(Qt.AlignVCenter)
        # rating_box.setAlignment(Qt.AlignBottom)

        # lyt.addLayout(rating_box)

        self.contents.setLayout(lyt)

        # child = contents.findChild(QLabel, 'a')
        scrollArea.setWidget(self.contents)

        return scrollArea

    # def rating_value_changed(self, x):
    #     my_ratings = reusables.load_json('my_ratings.json')
    #     self.rating_value.setText('({:.1f}/5)'.format(x / 2))
    #     self.data[self.CURRENT_MOVIE]['my_rating'] = x / 2
    #     my_ratings[self.data[self.CURRENT_MOVIE]['imdb']] = x / 2
    #
    #     reusables.save_json(my_ratings, 'my_ratings.json', indent=2)
    #     reusables.save_json(self.data, 'database_v2.json', indent=2)

    def insertStatusbar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('Loaded {} movies'.format(len(self.movies)))

    def openSettings(self):
        config = reusables.load_json('config.json')
        dlg = Setting_UI(self)
        dlg.path_line_edit.setText(config['path'])
        if dlg.exec_():
            # If okay is pressed
            new_path = dlg.path_line_edit.text()

            if os.path.exists(new_path):
                self.PATH = new_path
                print(self.PATH)
                self.initUI()


        else:
            # If cancel is pressed
            pass

    def insertMenuBar(self):
        # create menu
        menubar = QMenuBar()

        # layout.addWidget(menubar, 0, 0)
        actionFile = menubar.addMenu("File")
        actionSetting = actionFile.addAction("Settings")
        # actionFile.addAction("New")
        # actionFile.addAction("Open")
        # actionFile.addAction("Save")
        actionFile.addSeparator()
        actionQuit = actionFile.addAction("Quit")
        menubar.addMenu("Edit")
        menubar.addMenu("View")
        menubar.addMenu("Help")

        # Event Handlers
        actionSetting.triggered.connect(self.openSettings)
        actionQuit.triggered.connect(self.close)

        self.setMenuBar(menubar)

    def addToolbar(self):
        layout = QtWidgets.QHBoxLayout()
        # layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

        # Add the widgets with size contrainsts

        self.search_field = QLineEdit()
        self.search_field.setMaximumSize(QtCore.QSize(500, 32))
        self.search_field.setAlignment(Qt.AlignLeft)

        search_button = QPushButton('Search')
        search_button.setMaximumSize(QtCore.QSize(68, 34))

        spacerItem = QtWidgets.QSpacerItem(10, 35, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)

        sort_label = QLabel('Sort By')
        sort_label.setOpenExternalLinks(True)

        sort_label.setMaximumSize(QtCore.QSize(72, 32))

        comboBox = QComboBox()
        comboBox.setMaximumSize(QtCore.QSize(100, 32))
        comboBox.addItems(['Name A-Z', 'Name Z-A', 'Rating', 'Year', 'Runtime'])

        propertiesButton = QPushButton('Properties')
        propertiesButton.setMaximumSize(QtCore.QSize(95, 34))

        spacerItem2 = QtWidgets.QSpacerItem(10, 35, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        ## Events
        search_button.clicked.connect(self.search_option)
        self.search_field.returnPressed.connect(self.search_option)
        self.search_field.textChanged.connect(self.search_option)
        comboBox.currentIndexChanged['QString'].connect(self.sort_option_changed)

        # Add the widgets to the layout
        layout.addWidget(self.search_field)
        layout.addWidget(search_button)
        layout.addItem(spacerItem)
        layout.addWidget(sort_label)
        layout.addWidget(comboBox)
        layout.addWidget(propertiesButton)
        layout.addItem(spacerItem2)
        layout.setAlignment(Qt.AlignLeft)
        layout.setAlignment(Qt.AlignHCenter)
        return layout

    # def search_option(self):
    #     query = self.search_field.text()
    #
    #     child_dict = defaultdict(str)
    #
    #     accepted_list = []
    #     for child in self.childs:
    #         if query == '':  # If the query is None, the  add all the widgets
    #             self.lyt.addWidget(child)
    #         elif query.lower() not in self.data[child.objectName()]['title'].lower():
    #             child.setParent(None)
    #         else:
    #             self.lyt.addWidget(child)
    #
    #     self.statusBar.showMessage('{}'.format(self.movieAreaContents.children()[:1]))

    @QtCore.pyqtSlot(list)
    def search_response(self, list_of_results):
        print(len(list_of_results))

        for child in self.movieAreaContents.children()[1:]:  # Remove all the button from movieArea
            child.setParent(None)

        for title, year, id in list_of_results:  # Add newly searched movies
            if id not in self.popular_movies:
                self.create_movie_button('{} ({})'.format(title, year), str(id))
                self.put_in_updater_stack(str(id))

        for child in self.popular_movies_buttons:  # Add the popular movies again
            self.lyt.addWidget(child)

    def threadedSearcherRequest(self, query):
        # print('here', query)
        self.threaded_search.putStack(query)

    def search_option(self):
        query = self.search_field.text()

        child_dict = defaultdict(str)

        self.threadedSearcherRequest(query)

        accepted_list = []
        # for child in self.popular_movies_buttons:
        #     if query == '':  # If the query is None, the  add all the widgets
        #         self.lyt.addWidget(child)
        #     elif query.lower() not in self.data[child.objectName()]['title'].lower():
        #         child.setParent(None)
        #     else:
        #         self.lyt.addWidget(child)
        #
        # self.statusBar.showMessage('{}'.format(self.movieAreaContents.children()[:1]))

    def sort_option_changed(self):
        sort_option = self.sender().currentText()

        childs = self.movieAreaContents.children()[1:]
        child_dict = defaultdict(str)
        child_dict = {child.objectName(): child for child in childs}

        for c in childs:
            c.setParent(None)
        dat = self.movies.keys()

        if sort_option == 'Name A-Z':
            dat = sorted(self.data, key=lambda x: self.data[x]['title'], reverse=False)
        elif sort_option == 'Name Z-A':
            dat = sorted(self.data, key=lambda x: self.data[x]['title'], reverse=True)
        elif sort_option == 'Rating':
            dat = sorted(self.data, key=lambda x: self.data[x]['Rating'], reverse=True)
        elif sort_option == 'Year':
            dat = sorted(self.data, key=lambda x: int(self.data[x]['Year']), reverse=True)
        elif sort_option == 'Runtime':
            dat = sorted(self.data, key=lambda x: int(self.data[x]['runtime_mins']), reverse=False)

        for k, v in self.movies.items():
            if k not in dat:
                dat.append(k)

        for iid in dat:
            self.lyt.addWidget(child_dict[iid])

        self.repaint()

    def showInfoArea(self, id):
        self.CURRENT_MOVIE = id
        linkgetter = lambda lst: ''.join([
            '''<a style="text-decoration:none; color:black;" href="https://google.com/search?q={}">{}, </a> '''.format(
                urllib.parse.quote(item), item) for item in lst])
        if id in self.data.keys():
            info = self.data[id]
            for k in ['title', 'tagline', 'Year', 'Rating', 'Director', 'Duration', 'Genre', 'Budget', 'Box Office',
                      'cast', 'plot']:
                text = info[k]

                if type(text) == list:
                    text = linkgetter(text)
                    # print(text)

                self.contents.findChild(QLabel, k).setText(text)
            self.contents.findChild(QLabel, 'poster_value').setPixmap(QtGui.QPixmap(info['poster_value']))
            self.contents.findChild(QLabel, 'backdrop_value').setPixmap(QtGui.QPixmap(info['backdrop_value']))

            # Set the my_ratings
            # if 'my_rating' in self.data[self.CURRENT_MOVIE]:
            #     if self.data[self.CURRENT_MOVIE]['my_rating']:
            #         self.rating_value.setText('({:.1f}/5)'.format(self.data[self.CURRENT_MOVIE]['my_rating']))
            #         self.slider.setValue(int(self.data[self.CURRENT_MOVIE]['my_rating'] * 2))

    def play_torrent(self, imdb_id):
        threading.Thread(target=player.play, args=(imdb_id,)).start()

    def eventFilter(self, obj, event):
        if type(obj) is QtWidgets.QToolButton:
            if event.type() == QtCore.QEvent.MouseButtonDblClick:
                # print("Double Click")
                print('Playing: ', self.data[obj.objectName()]['title'])
                self.play_torrent(self.data[obj.objectName()]['imdb_id'])
                # os.startfile(self.movies[obj.objectName()])

            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton:
                    # print(self.movie_name_json[obj.objectName()], "Left click")
                    # self.update_movie_info(movie_name=obj.objectName())
                    self.showInfoArea(obj.objectName())

                elif event.button() == QtCore.Qt.RightButton:
                    # print(obj.objectName(), "Right click", event.globalPos())
                    self.movieButtonContextMenu(obj.objectName())
                    # self.actionRight(obj)
                    # print(self.db.database[obj.objectName()]['location'])
                    # subprocess.Popen(r'explorer /select, ' + self.db.database[obj.objectName()]['location'])
        else:
            # For global keys
            if event.type() == QtCore.QEvent.KeyPress:
                key = event.key()

                # for a in self.movieAreaContents.children()[1:]:
                #     a.hide()
                #     if a.isChecked():
                #         print(self.movie_name_json[a.objectName()])

                if key == Qt.Key_Return:
                    print('Return Key pressed')

                    # print(obj.childern())
                elif key == Qt.Key_Delete:
                    print('Delete Key Pressed')

        return QtCore.QObject.event(obj, event)

    def movieButtonContextMenu(self, id):
        contextMenu = QMenu(self)
        open_location = contextMenu.addAction("Open Folder Location")
        search = contextMenu.addAction("Search in Google")
        delete = contextMenu.addAction("Delete")
        # print(self.mapToGlobal(point))
        action = contextMenu.exec_(QCursor.pos())
        if action == search:
            webbrowser.open('https://google.com/search?q=' + urllib.parse.quote(self.data[id]['title']))
        elif action == open_location:
            subprocess.Popen(r'explorer /select, ' + self.movies[id])
        elif action == delete:
            pass

    def getMovieNamesList(self):
        movie = Movie()
        popular = movie.popular()
        #
        # lst = [(p.title, p.release_date[:4]) for p in popular]
        self.movies = {}
        for p in popular:
            # det = movie.details(p.id, append_to_response='append_to_response=videos')
            # print(p.id, p.title, p.release_date[:4], det.imdb_id)
            self.movies[str(p.id)] = p.title
            self.popular_movies.append(str(p.id))

        return self.movies




if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    # time.sleep(5)
    a = app.exec_()
    print('After Closing')
    # endCleanup()
    sys.exit(a)
