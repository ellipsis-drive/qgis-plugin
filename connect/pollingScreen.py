from PyQt5.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QWidget,
    QLineEdit,
    QCheckBox,
    QSizePolicy,
    QSpacerItem,
)
from qgis.core import *
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from qgis.core import QgsMessageLog, Qgis
from .util import *
from .polling import POLLING_MANAGER


class pollingScreenTab(QDialog):
    """Displayed when a user is logged in with OAuth. It tells the user to set a password."""

    returnsignal = pyqtSignal()

    def __init__(self):
        super(pollingScreenTab, self).__init__()
        self.manager = POLLING_MANAGER
        QgsMessageLog.logMessage(
            "go to polling4",
            "MyPlugin",
            Qgis.Info
        )


        self.polling = QSettings("Ellipsis Drive", "Ellipsis Drive Connect")
        self.setMinimumHeight(0)
        self.setMinimumWidth(0)

        self.constructUI()


    def sizeHint(self):
        a = QWidget.sizeHint(self)
        a.setHeight(SIZEH)
        a.setWidth(SIZEW)
        return a

    def cancel(self):
        self.manager.stopPolling()
        self.returnsignal.emit()

    def constructUI(self):
        self.gridLayout = QGridLayout()
        self.label = QLabel()
        self.label.setText("Please login in the browser")

        self.label_appurl = QLabel()
        self.label_appurl.setText("Waiting.....")



        self.backButton = QPushButton()
        self.backButton.setText("Cancel")
        self.backButton.clicked.connect(self.cancel)

        self.gridLayout.addWidget(self.label, 0, 0)
        self.gridLayout.addWidget(self.label_appurl, 2, 0)

        self.gridLayout.addWidget(self.backButton, 5, 0)

        self.spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.gridLayout.addItem(self.spacer, 4, 0, 1, 2)
        self.setLayout(self.gridLayout)

