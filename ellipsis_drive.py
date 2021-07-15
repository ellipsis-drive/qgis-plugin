# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EllipsisConnect
                                 A QGIS plugin
 Connect to Ellipsis Drive
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-06-24
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Ellipsis Drive
        email                : floydremmerswaal@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import json
import requests
from requests import api
from requests.structures import CaseInsensitiveDict

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QListWidgetItem, QListWidget, QMessageBox, QWidget, QGridLayout, QLabel

from PyQt5 import QtCore

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .ellipsis_drive_dialog import EllipsisConnectDialog
import os.path

from threading import Timer

class ListData:
    """ Class used for objects in the QList of the EllipsisConnect plugin """
    def __init__(self, type="none", data=""):
        self.type = type
        self.data = data
    
    def setData(self, type, data):
        self.type = type
        self.data = data

    def getData(self):
        return self.data

    def getType(self):
        return self.type

# taken from https://gist.github.com/walkermatt/2871026
def debounce(wait):
    """ Decorator that will postpone a functions
        execution until after wait seconds
        have elapsed since the last time it was invoked. """
    def decorator(fn):
        def debounced(*args, **kwargs):
            def call_it():
                fn(*args, **kwargs)
            try:
                debounced.t.cancel()
            except(AttributeError):
                pass
            debounced.t = Timer(wait, call_it)
            debounced.t.start()
        return debounced
    return decorator

def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

URL = 'https://api.ellipsis-drive.com/v1'

class EllipsisConnect:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'EllipsisConnect_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Ellipsis Drive Connect')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        self.username = ""
        self.password = ""
        self.communitySearch = ""
        self.loggedIn = False
        self.loginToken = ""
        self.rememberMe = False

        self.radioState = ""

        self.settings = QSettings('Ellipsis Drive', 'Ellipsis Drive Connect')
        if (self.settings.contains("token")):
            print("Login data found")
            self.loggedIn = True
            self.loginToken = self.settings.value("token")
        else:
            print("No login data found")
        

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('EllipsisConnect', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/ellipsis_drive/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Ellipsis Drive Connect'),
                action)
            self.iface.removeToolBarIcon(action)

    def loginButton(self, value):
        apiurl = f"{URL}/account/login"
        print(f'Logging in: username: {self.username}, password: {self.password}')

        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/json"
        data = '{"username": "%s", "password": "%s"}' % (self.username, self.password)

        print(data)
        resp = requests.post(apiurl, headers=headers, data=data)
        jprint(resp.json())
        data = resp.json()
        if resp:
            #print(f"Token: {data['token']}")
            self.loggedIn = True
            self.loginToken = data['token']
            print("logged in")
            if self.rememberMe and self.confirmRemember():
                # make sure people want their token saved!!
                self.settings.setValue("token",data["token"])
                print("login token saved to settings")
            else:
                print("token NOT saved to settings")
            #TODO: UI elementen weghalen/toevoegen? misschien zelfs in constructor doen eigenlijk
        else:
            self.loggedIn = False
            self.loginToken = ""
            print("Login failed")
        #print(f'token: {token}')
        #self.dlg.label_output.setText(f"Output:")

    def onUsernameChange(self, text):
        self.username = text

    def onPasswordChange(self, text):
        self.password = text

    def addToList(self, value):
        # better to make something like self.items, so we can explicitly change the items
        # https://doc.qt.io/qtforpython/PySide6/QtWidgets/QListWidgetItem.html
        QListWidgetItem("string", self.dlg.listWidget_mydrive)

    @debounce(0.5)
    def getCommunityList(self):
        """ gets the list of public projects and add them to the list widget on the community tab """
        # reset the list before updating it
        self.dlg.listWidget_community.clear()
        # TODO add functionality to search for name etc
        # add functionality for raster/vector data
        apiurl = f"{URL}/account/maps"
        print("Getting community maps")
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        data = {
            "access": ["public"],
            "name": f"{self.communitySearch}"
        }

        j1 = requests.post(apiurl, json=data, headers=headers)
        if not j1:
            print("getCommunityList failed!")
            return []
        data = json.loads(j1.text)
        for mapdata in data["result"]:
            newitem = QListWidgetItem()
            newitem.setText(mapdata["name"])
            item = ListData("id", mapdata["id"])
            newitem.setData(QtCore.Qt.UserRole, item)
            self.dlg.listWidget_community.addItem(newitem)
        
    def onCommunitySearchChange(self, text):
        """ Change the internal state of the community search string """
        self.communitySearch = text
        self.getCommunityList()

    def onCommunityItemClick(self, item):
        print(f"{item.text()}, data type: {item.data((QtCore.Qt.UserRole)).getType()}, data value: {item.data((QtCore.Qt.UserRole)).getData()}")

    def manageRadioState(self, b):
        if b.text() == "Raster data":
            if b.isChecked():
                self.radioState = "raster"
            else:
                self.radioState = "vector"
        elif b.text() == "Vector data":
            if b.isChecked():
                self.radioState = "vector"
            else:
                self.radioState = "raster"

    def onChangeRemember(self, button):
        self.rememberMe = button.isChecked()

    def confirmRemember(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)

        msg.setText("Remembering your login data should only be done on devices you trust.")
        msg.setWindowTitle("Are you sure?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        retval = msg.exec_()
        return retval == QMessageBox.Ok

    def getMetadata(self, mapid):
        """ Returns metadata (in JSON) for a map (by mapid) by calling the Ellipsis API"""
        apiurl = F"{URL}/metadata"
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        data = {
            "mapId": f"{mapid}",
        }
        j1 = requests.post(apiurl, json=data, headers=headers)
        if not j1:
            print("getMetadata failed!")
            return {}
        data = json.loads(j1.text)
        jprint(data)
        return data

    def logOut(self):
        print("logging out")
        if (self.settings.contains("token")):
            self.settings.remove("token")

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            print("first run of run()")
            self.first_start = False
            self.dlg = EllipsisConnectDialog()
            #self.dlg.pushButton_login.clicked.connect(self.loginButton)
            #self.dlg.pushButton_logout.clicked.connect(self.logOut)
            #self.dlg.pushButton_addtolist.clicked.connect(self.addToList)

            #self.dlg.lineEdit_username.textChanged.connect(self.onUsernameChange)
            #self.dlg.lineEdit_password.textChanged.connect(self.onPasswordChange)
            #self.dlg.lineEdit_communitysearch.textChanged.connect(self.onCommunitySearchChange)
            
            #self.dlg.radioRaster.toggled.connect(lambda:self.manageRadioState(self.dlg.radioRaster))
            #self.dlg.radioVector.toggled.connect(lambda:self.manageRadioState(self.dlg.radioVector))

            #self.dlg.checkBox_remember.stateChanged.connect(lambda:self.onChangeRemember(self.dlg.checkBox_remember))

            #self.getCommunityList()
            #self.dlg.listWidget_community.itemClicked.connect(self.onCommunityItemClick)

        print("run")

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
