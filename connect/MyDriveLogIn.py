import requests
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)
from qgis.PyQt.QtCore import QSettings, pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox
from requests.structures import CaseInsensitiveDict
from qgis.core import QgsMessageLog, Qgis
import webbrowser

from .polling import POLLING_MANAGER


from .util import *
from . import util

class MyDriveLoginTab(QDialog):
    """login tab, sends a signal with the token on succesful login. Used in combination with the MyDriveLoggedInTab"""

    loginSignal = pyqtSignal(object, object)
    settingsSignal = pyqtSignal()
    pollingSignal = pyqtSignal()

    def __init__(self):
        super(MyDriveLoginTab, self).__init__()
        self.manager = POLLING_MANAGER
        # uic.loadUi(os.path.join(TABSFOLDER, "MyDriveLoginTab.ui"), self)
        self.settings = QSettings("Ellipsis Drive", "Ellipsis Drive Connect")
        self.constructUI()

        self.userInfo = {}
        self.rememberMe = self.checkBox_remember.isChecked()
        self.loggedIn = False

    def keyPressEvent(self, qKeyEvent):
        """enable the user to press enter to log in"""
        if qKeyEvent.key() == QtCore.Qt.Key_Return:
            self.loginButton()
        else:
            super().keyPressEvent(qKeyEvent)

    def sizeHint(self):
        """used by qgis to set the size"""
        a = QWidget.sizeHint(self)
        a.setHeight(SIZEH)
        a.setWidth(SIZEW)
        return a

    def constructUI(self):
        """function that constructs the login UI"""
        self.gridLayout = QGridLayout()



        self.checkBox_remember = QCheckBox()
        self.checkBox_remember.setChecked(True)
        self.checkBox_remember.setText("Remember me")

        self.pushButton_login = QPushButton()
        self.pushButton_login.setText("Login")
        self.spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.pushButton_settings = QPushButton()
        self.pushButton_settings.setText("Settings")
        self.pushButton_settings.clicked.connect(self.goToSettings)

        self.pushButton_login.clicked.connect(self.loginButton)
        self.checkBox_remember.stateChanged.connect(
            lambda: self.onChangeRemember(self.checkBox_remember)
        )

        self.gridLayout.addWidget(self.checkBox_remember, 4, 0)

        self.gridLayout.addWidget(self.pushButton_settings, 5, 1)
        self.gridLayout.addWidget(self.pushButton_login, 4, 1)

        self.gridLayout.addItem(self.spacer, 6, 0, 1, 2)

        self.setLayout(self.gridLayout)

    def goToSettings(self):
        self.settingsSignal.emit()








    def onChangeRemember(self, button):
        """function called when the 'remember me' checkbox is clicked"""
        self.rememberMe = button.isChecked()

    def confirmRemember(self):
        """confirm if the user is sure that they want their info to be remembered"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)

        msg.setText(
            "Remembering your login data should only be done on devices you trust."
        )
        msg.setWindowTitle("Are you sure?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Ok)
        retval = msg.exec_()
        return retval == QMessageBox.Ok

    def displayLoginError(self):
        """displays an error, called when the login fails"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)

        msg.setText("Please enter your correct username and password.")
        msg.setWindowTitle("Login failed!")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return

    def displayNoneError(self):
        """displays an error, called when the login fails"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)

        msg.setText("Please check in the settings if your API url is correct.")
        msg.setWindowTitle("Login failed!")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return



    def loginButton(self):
        QgsMessageLog.logMessage(
            "go to polling",
            "MyPlugin",
            Qgis.Info
        )
        CaseInsensitiveDict()
        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/json"
        reqsuc, content = makeRequest(
            "/account/security/remoteSession", headers=headers, data={}, method="POST"
        )

        if reqsuc:
            QgsMessageLog.logMessage(
                str(content),
                "MyPlugin",
                Qgis.Info
            )

            uuid = content['id']
            util.SESSION = uuid

            webbrowser.open( util.getAPPUrl() + "/login?session=" + uuid)
            self.pollingSignal.emit()


            # define function to run when condition is met
            def onSuccess(token):
                self.manager.stopPolling()
                QgsMessageLog.logMessage(
                    "success! " + token ,
                    "MyPlugin",
                    Qgis.Info
                )
                if  self.rememberMe:
                    self.settings.setValue("token", token)
                    log("login token saved to settings")
                else:
                    log("token NOT saved to settings")
                success, data = getUserData(token)
                if success:
                    self.loginSignal.emit(token, data)


            self.manager.startPolling(uuid,onSuccess)



        else:
            log("Login failed")
            QgsMessageLog.logMessage(
                str(content),
                "MyPlugin",
                Qgis.Info
            )
            log(content)
            self.displayNoneError()






    def onUsernameChange(self, text):
        """makes the internal username match the form"""
        self.username = text

    def onPasswordChange(self, text):
        """makes the internal password match the form"""
        self.password = text
