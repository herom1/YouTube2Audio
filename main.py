import os
import shutil
import sys
import time
from functools import partial
import requests
import qdarkstyle
from PyQt5.QtCore import QThread, QPersistentModelIndex, pyqtSignal
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QTableWidgetItem
import utils
from ui import UiMainWindow


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
IMG_PATH = os.path.join(BASE_PATH, "img")
UTILS_PATH = os.path.join(BASE_PATH, "utils")


class MainPage(QMainWindow, UiMainWindow):
    """Main page of the application."""

    def __init__(self, parent=None):
        super(MainPage, self).__init__(parent)
        self.setupUi(self)
        # Hide the fetching data label, error label, and revert button
        self.url_fetching_data_label.hide()
        self.url_error_label.hide()
        self.revert_annotate.hide()
        self.credit_url.linkActivated.connect(self.set_credit_url)
        self.credit_url.setText(
            '<a href="https://github.com/irahorecka/YouTube2Mp3">Source code</a>'
        )
        # Connect the delete video button with the remove_selected_items fn.
        self.remove_from_table_button.clicked.connect(self.remove_selected_items)
        # Connect song property setter buttons.
        self.set_album.clicked.connect(
            partial(self.set_albm_artst_genr_artwrk, column_index=1)
        )
        self.set_artist.clicked.connect(
            partial(self.set_albm_artst_genr_artwrk, column_index=2)
        )
        self.set_genre.clicked.connect(
            partial(self.set_albm_artst_genr_artwrk, column_index=3)
        )
        self.set_artwork.clicked.connect(
            partial(self.set_albm_artst_genr_artwrk, column_index=4)
        )
        # Buttons connection with the appropriate functions
        self.url_load_button.clicked.connect(self.url_loading_button_click)
        self.url_input.returnPressed.connect(self.url_load_button.click)
        self.url_input.mousePressEvent = lambda _: self.url_input.selectAll()
        self.download_button.clicked.connect(self.download_button_click)
        self.download_path.clicked.connect(self.get_download_path)
        self.itunes_annotate.clicked.connect(self.itunes_annotate_click)
        self.revert_annotate.clicked.connect(self.default_annotate_table)
        self.video_table.cellPressed.connect(self.display_artwork_videoinfo)
        # edit table cell with single click
        self.video_table.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
        # Input changes in video property text box to appropriate cell.
        self.change_video_info_input.clicked.connect(self.replace_cell_item)
        self.change_video_info_input_all.clicked.connect(self.replace_cell_column)
        self.video_info_input.returnPressed.connect(self.change_video_info_input.click)
        # Exit application
        self.cancel_button.clicked.connect(self.close)
        # Get download directory
        self.download_dir = BASE_PATH
        self.download_folder_select.setText(
            self.get_parent_current_dir(self.download_dir)  # get directory tail
        )

    def url_loading_button_click(self):
        """Reads input data from self.url_input and creates an instance
        of the UrlLoading thread."""
        self.videos_dict = dict()  # Clear videos_dict upon reloading new playlist.

        playlist_url = self.url_input.text()
        if not playlist_url:  # i.e. empty playlist_url
            self.url_error_label.show()
            self.default_annotate_table()
            return

        self.url_fetching_data_label.show()
        self.url_error_label.hide()
        self.calc = UrlLoading(playlist_url)
        self.calc.countChanged.connect(self.url_loading_finished)
        self.calc.start()

    def url_loading_finished(self, videos_dict, executed):
        """Retrieves data from thread when complete, updates GUI table."""
        # First entry of self.videos_dict in MainPage class
        self.videos_dict = videos_dict
        self.url_fetching_data_label.hide()
        self.video_table.clearContents()  # clear table for new loaded content
        if executed:
            self.default_annotate_table()  # set table content
        else:
            self.url_error_label.show()

    def itunes_annotate_click(self):
        """Load iTunes annotation info on different thread."""
        try:
            assert self.videos_dict  # i.e. click annotate button with empty table
        except (AttributeError, AssertionError):
            return
        self.annotate = iTunesLoading(self.videos_dict)
        self.annotate.loadFinished.connect(self.itunes_annotate_finished)
        self.annotate.start()

    def itunes_annotate_finished(self, itunes_query_tuple):
        """Populate GUI table with iTunes meta information once
        iTunes annotation query complete."""
        for row_index, ITUNES_META_JSON in itunes_query_tuple:
            self.itunes_annotate_table(row_index, ITUNES_META_JSON)

        self.itunes_annotate.hide()
        self.revert_annotate.show()

    def get_download_path(self):
        """Fetch download file path"""
        self.download_dir = QFileDialog.getExistingDirectory(
            self, "Open folder", BASE_PATH
        )
        if not self.download_dir:
            self.download_dir = BASE_PATH

        self.download_folder_select.setText(
            self.get_parent_current_dir(self.download_dir)
        )

    def download_button_click(self):
        """ Executes when the button is clicked """
        try:
            assert self.videos_dict  # assert self.videos_dict exists
        except (AttributeError, AssertionError):
            self.download_status.setText("No video to download.")
            return

        playlist_properties = self.get_playlist_properties()

        self.download_button.setEnabled(False)
        self.download_status.setText("Downloading...")
        self.down = DownloadingVideos(
            self.videos_dict, self.download_dir, playlist_properties
        )
        self.down.downloadCount.connect(self.download_finished)
        self.down.start()

    def download_finished(self, download_time):
        """Emit changes to MainPage once dowload is complete."""
        _min = int(download_time // 60)
        sec = int(download_time % 60)
        self.download_status.setText(f"Download time: {_min} min. {sec} sec.")
        self.download_button.setEnabled(True)

    def default_annotate_table(self):
        """Default table annotation to video title in song columns"""
        if not self.videos_dict:  # i.e. an invalid playlist input
            self.video_table.clearContents()
            return

        for index, key in enumerate(self.videos_dict):
            self.video_table.setItem(index, 0, QTableWidgetItem(key))  # part of QWidget
            self.video_table.setItem(index, 1, QTableWidgetItem("Unknown"))
            self.video_table.setItem(index, 2, QTableWidgetItem("Unknown"))
            self.video_table.setItem(index, 3, QTableWidgetItem("Unknown"))
            self.video_table.setItem(index, 4, QTableWidgetItem("Unknown"))
        self.revert_annotate.hide()
        self.itunes_annotate.show()

    def itunes_annotate_table(self, row_index, ITUNES_META_JSON):
        """Provide iTunes annotation guess based on video title"""
        try:
            song_name, song_index = ITUNES_META_JSON["track_name"], 0
            album_name, album_index = ITUNES_META_JSON["album_name"], 1
            artist_name, artist_index = ITUNES_META_JSON["artist_name"], 2
            genre_name, genre_index = ITUNES_META_JSON["primary_genre_name"], 3
            artwork_name, artwork_index = ITUNES_META_JSON["artwork_url_fullres"], 4
        except TypeError:  # ITUNES_META_JSON was never called.
            try:
                song_name, song_index = (
                    self.video_table.item(row_index, 0).text(),
                    0,
                )  # get video title
            except AttributeError:  # nothing populated on table
                song_name, song_index = "Unknown", 0

            album_name, album_index = "Unknown", 1
            artist_name, artist_index = "Unknown", 2
            genre_name, genre_index = "Unknown", 3
            artwork_name, artwork_index = "default_artwork.png", 4
        self.video_table.setItem(row_index, song_index, QTableWidgetItem(song_name))
        self.video_table.setItem(row_index, album_index, QTableWidgetItem(album_name))
        self.video_table.setItem(row_index, artist_index, QTableWidgetItem(artist_name))
        self.video_table.setItem(row_index, genre_index, QTableWidgetItem(genre_name))
        self.video_table.setItem(
            row_index, artwork_index, QTableWidgetItem(artwork_name)
        )

    def display_artwork_videoinfo(self, row, column):
        """Display selected artwork and self.video_info_input on Qpixmap widget."""
        # artwork
        try:
            artwork_file = self.video_table.item(row, 4).text()
            response = requests.get(artwork_file)
            if response.status_code != 200:  # invalid image url
                qt_artwork_img = os.path.join(IMG_PATH, "default_artwork.png")
            else:
                artwork_img = response.content
                qt_artwork_img = QtGui.QImage()
                qt_artwork_img.loadFromData(artwork_img)
                self.album_artwork.setPixmap(QtGui.QPixmap.fromImage(qt_artwork_img))
        except (
            AttributeError,
            requests.exceptions.MissingSchema,
        ):  # i.e. selected empty cell or cell has non-url str
            qt_artwork_img = os.path.join(IMG_PATH, "default_artwork.png")

        # set self.video_info_iput properties
        try:
            self.video_info_input.setText(self.video_table.item(row, column).text())
        except AttributeError:
            self.video_info_input.setText("")

        # set artwork properties
        self.album_artwork.setPixmap(QtGui.QPixmap(qt_artwork_img))
        self.album_artwork.setScaledContents(True)
        self.album_artwork.setAlignment(QtCore.Qt.AlignCenter)

    def set_albm_artst_genr_artwrk(self, column_index):
        """Set cell content in album, artist, genre, and artwork
        columns based on cell selection or selected cell content."""
        rows = self.video_table.rowCount()
        try:
            for row_index in range(rows):
                item = self.video_table.item(row_index, column_index)  # get cell value
                if item and item.text():
                    self.video_table.setItem(
                        row_index,
                        column_index,
                        QTableWidgetItem(self.video_info_input.text()),
                    )  # part of QWidget
        except AttributeError:  # i.e. empty self.video_info_input
            pass

    def replace_cell_item(self):
        """Change selected cell value to value in self.video_info_input."""
        row = self.video_table.currentIndex().row()
        column = self.video_table.currentIndex().column()
        video_info_input_value = self.video_info_input.text()
        self.video_table.setItem(row, column, QTableWidgetItem(video_info_input_value))

    def replace_cell_column(self):
        """Change every occupied cell in the selected column to value
        in self.video_info_input."""
        column = self.video_table.currentIndex().column()
        self.set_albm_artst_genr_artwrk(column)

    def remove_selected_items(self):
        """Removes the selected items from self.videos_table and self.videos_dict.
        Table widget updates -- multiple row deletion capable."""
        try:
            video_list = [key_value for key_value in self.videos_dict.items()]
        except AttributeError:  # i.e. empty self.videos_dict
            video_list = []

        row_index_list = []
        for model_index in self.video_table.selectionModel().selectedRows():
            row = model_index.row()
            row_index = QPersistentModelIndex(model_index)
            row_index_list.append(row_index)
            try:
                current_key = video_list[row][0]
                del self.videos_dict[
                    current_key
                ]  # remove row item from self.videos_dict
            except (IndexError, KeyError):  # no item/key in video_list or videos_dict
                pass

        for index in row_index_list:
            self.video_table.removeRow(index.row())

    def get_playlist_properties(self):
        """Get video information from self.video_table to reflect to
        downloaded MP3 metadata."""
        playlist_properties = []

        for row_index, key_value in enumerate(self.videos_dict.items()):
            song_properties = {}
            song_properties["song"] = self.get_row_text(
                self.video_table.item(row_index, 0)
            ).replace(
                "/", "-"
            )  # will be filename -- change illegal char to legal - make func
            song_properties["album"] = self.get_row_text(
                self.video_table.item(row_index, 1)
            )
            song_properties["artist"] = self.get_row_text(
                self.video_table.item(row_index, 2)
            )
            song_properties["genre"] = self.get_row_text(
                self.video_table.item(row_index, 3)
            )
            song_properties["artwork"] = self.get_row_text(
                self.video_table.item(row_index, 4)
            )

            playlist_properties.append(
                song_properties
            )  # this assumes that dict will be ordered like list

        return playlist_properties

    def set_credit_url(self, url_str):
        """Set source code url on upper right of table."""
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url_str))

    @staticmethod
    def get_row_text(cell_item):
        """Get text of cell value, if empty return empty str."""
        try:
            cell_item = cell_item.text()
            return cell_item
        except AttributeError:
            cell_item = ""
            return cell_item

    @staticmethod
    def get_parent_current_dir(current_path):
        """Get current and parent directory as str."""
        parent_dir, current_dir = os.path.split(current_path)
        parent_dir = os.path.split(parent_dir)[1]  # get tail of parent_dir
        parent_current_dir = f"../{parent_dir}/{current_dir}"

        return parent_current_dir


class UrlLoading(QThread):
    """ Loads the videos data from playlist in another thread."""

    countChanged = pyqtSignal(dict, bool)

    def __init__(self, playlist_link, parent=None):
        QThread.__init__(self, parent)
        self.playlist_link = playlist_link

    def run(self):
        """ Main function, gets all the playlist videos data, emits the info dict"""
        try:
            videos_dict = utils.get_youtube_content(self.playlist_link)
            self.countChanged.emit(videos_dict, True)
        except Exception as error:
            print(error)
            self.countChanged.emit({}, False)


class iTunesLoading(QThread):
    """Get video data properties from iTunes."""

    loadFinished = pyqtSignal(tuple)

    def __init__(self, videos_dict, parent=None):
        QThread.__init__(self, parent)
        self.videos_dict = videos_dict

    def run(self):
        """Multithread query to iTunes - return tuple."""
        try:
            query_iter = (
                (row_index, key_value)
                for row_index, key_value in enumerate(self.videos_dict.items())
            )
        except AttributeError:  # i.e. no content in table
            return
        itunes_query = utils.map_threads(utils.thread_query_itunes, query_iter)
        itunes_query_tuple = tuple(itunes_query)

        self.loadFinished.emit(itunes_query_tuple)


class DownloadingVideos(QThread):
    """Download all videos from the videos_dict using the id."""

    downloadCount = pyqtSignal(float)  # attempt to emit delta_t

    def __init__(self, videos_dict, download_path, playlist_properties, parent=None):
        QThread.__init__(self, parent)
        self.videos_dict = videos_dict
        self.download_path = download_path
        self.playlist_properties = playlist_properties

    def run(self):
        """ Main function, downloads videos by their id while emitting progress data"""
        # Download
        mp4_path = os.path.join(self.download_path, "mp4")
        try:
            os.mkdir(mp4_path)
        except FileExistsError:
            pass

        time0 = time.time()
        video_properties = (
            (key_value, (self.download_path, mp4_path), self.playlist_properties[index])
            for index, key_value in enumerate(
                self.videos_dict.items()
            )  # dict is naturally sorted in iteration
        )
        utils.map_threads(utils.thread_query_youtube, video_properties)
        shutil.rmtree(mp4_path)  # remove mp4 dir
        time1 = time.time()

        delta_t = time1 - time0
        self.downloadCount.emit(delta_t)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MainPage()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    widget.show()
    sys.exit(app.exec_())
