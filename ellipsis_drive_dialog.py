# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EllipsisConnectDialog
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

import os
import sys
import json
from PyQt5.QtGui import QIcon
import requests
from requests import api
from requests.structures import CaseInsensitiveDict

from threading import ThreadError, Timer

from PyQt5.QtWidgets import QCheckBox, QDialog, QInputDialog, QLineEdit, QMainWindow

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

from qgis.PyQt.QtCore import QSettings, pyqtSignal

from PyQt5 import QtCore

from qgis.PyQt.QtWidgets import QAction, QListWidgetItem, QListWidget, QMessageBox, QWidget, QGridLayout, QLabel

from enum import Enum

PYCLIP = False

try:
    import pyclip
    PYCLIP = True
except ImportError:
    PYCLIP = False


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ellipsis_drive_dialog_base.ui'))

# definitions of constants

TABSFOLDER = os.path.join(os.path.dirname(__file__), "tabs/")
ICONSFOLDER = os.path.join(os.path.dirname(__file__), "icons/")

FOLDERICON = os.path.join(ICONSFOLDER,"folder.svg")
VECTORICON = os.path.join(ICONSFOLDER,"vector.svg")
RASTERICON = os.path.join(ICONSFOLDER,"raster.svg")
ERRORICON = os.path.join(ICONSFOLDER,"error.svg")

URL = 'https://api.ellipsis-drive.com/v1'
#URL = 'http://dev.api.ellipsis-drive.com/v1'

# for reference
# API = 'https://api.ellipsis-drive.com/v1'
DEVAPI = 'http://dev.api.ellipsis-drive.com/v1'

DEBUG = True

class ErrorLevel(Enum):
    NORMAL = 1
    DISABLED = 2
    NOLAYERS = 3
    NOTIMESTAMPS = 4
    DELETED = 5
    WCSACCESS = 6

# TODO
# - pagination of folders and maps
# - Trash folder?
# - properly allign the 'My Drive' and 'Community Library' tabs (buttons should remain stationary when switching)
# - create seperate files for the tabs
# - clean up the file
# - when the path becomes too long, a part is cut-off: find fix for this

def getErrorLevel(map):
    if "deleted" in map and map["deleted"]:
        return ErrorLevel.DELETED
    elif "isShape" in map and "timestamps" in map and (not map["isShape"] and len(map["timestamps"]) == 0):
        return ErrorLevel.NOTIMESTAMPS
    elif "isShape" in map and "geometryLayers" and (map["isShape"] and len(map["geometryLayers"]) == 0):
        return ErrorLevel.NOLAYERS
    elif "disabled" in map and map["disabled"]:
        return ErrorLevel.DISABLED
    elif "accessLevel" in map and "isShape" in map and not map["isShape"] and map["accessLevel"] < 200:
        return ErrorLevel.WCSACCESS
    else:
        return ErrorLevel.NORMAL

def convertMapdataToListItem(mapdata, isFolder = True, isShape = False, isMap = False, errorLevel = ErrorLevel.NORMAL):
    # TODO other object as data, maybe the entire mapdata object?
    newitem = QListWidgetItem()
    icon = QIcon()
    if isShape:
        icon = QIcon(VECTORICON)
        item = ListData("id", mapdata["id"], True)
    elif isMap:
        icon= QIcon(RASTERICON)
        item = ListData("id", mapdata["id"], False)
    elif isFolder:
        icon = QIcon(FOLDERICON)
        item = ListData("id", mapdata["id"])
    elif mapdata["isShape"]:
        icon = QIcon(VECTORICON)
        item = ListData("id", mapdata["id"], mapdata["isShape"])
    else:
        icon = QIcon(RASTERICON)
        item = ListData("id", mapdata["id"], mapdata["isShape"])

    # now we handle the errorLevel
    if errorLevel == 0 or errorLevel == ErrorLevel.NORMAL or errorLevel == ErrorLevel.WCSACCESS:
        item.setDisableWCS(errorLevel == ErrorLevel.WCSACCESS)
        newitem.setText(mapdata["name"])
        newitem.setData(QtCore.Qt.UserRole, item)
        newitem.setIcon(icon)
        return newitem
    else:
        errmsgdict = {
            ErrorLevel.DELETED: "Project deleted",
            ErrorLevel.NOTIMESTAMPS: "Map has no timestamps",
            ErrorLevel.NOLAYERS: "Shape has no layers",
            ErrorLevel.DISABLED: "Project disabled",
        }
        item = ListData("error")
        newitem.setText(f'{mapdata["name"]} ({errmsgdict[errorLevel]})')
        newitem.setData(QtCore.Qt.UserRole, item)
        newitem.setIcon(QIcon(ERRORICON))
        return newitem
     


def getMetadata(mapid):
    """ Returns metadata (in JSON) for a map (by mapid) by calling the Ellipsis API"""
    apiurl = F"{URL}/metadata"
    headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
    data = {
        "mapId": f"{mapid}",
    }
    j1 = requests.post(apiurl, json=data, headers=headers)
    if not j1:
        log("getMetadata failed!")
        return {}
    data = json.loads(j1.text)
    log(f"metadata of map with id {mapid}")
    jlog(data)
    log("end of metadata")
    return data

def getUrl(mode, mapId, token = "empty"):
    """ constructs the url and copies it to the clipboard"""
    theurl = ""
    if token == "empty":
        theurl = f"{URL}/{mode}/{mapId}"
    else:
        theurl = f"{URL}/{mode}/{mapId}?token={token}"
    log(f"getUrl: {theurl}")
    if PYCLIP:
        pyclip.copy(theurl)
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Url copied to clipboard!")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
    else:
        msg = QInputDialog()
        msg.setWindowTitle("Success")
        msg.setLabelText(f"Please copy the following url.")
        msg.setTextValue(theurl)
        msg.setOption(QInputDialog.NoButtons)
        msg.exec_()

class ListData:
    """ Class used for objects in the QList of the EllipsisConnect plugin """
    def __init__(self, type="none", data="", isaShape=None, shouldDisableWCS=False):
        self.type = type
        self.data = data
        self.isaShape = isaShape
        self.shouldDisableWCS = shouldDisableWCS
    
    def setDisableWCS(self, val):
        self.shouldDisableWCS = val

    def getDisableWCS(self):
        return self.shouldDisableWCS

    def setData(self, type, data, isaShape):
        self.type = type
        self.data = data
        self.isaShape = isaShape

    def getData(self):
        return self.data

    def getType(self):
        return self.type
    
    def isShape(self):
        return self.isaShape

    def isEmpty(self):
        return self.type == "none" and self.data == ""

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

def log(text):
    """ only prints when DEBUG is True """
    if DEBUG:
        print(text)

def jlog(obj):
    """ logs a JSON object"""
    text = json.dumps(obj, sort_keys=True, indent=4)
    log(text)

class MyDriveLoginTab(QDialog):
    """ login tab, sends a signal with the token on succesful login """
    loginSignal = pyqtSignal(object, object)
    def __init__(self):
        super(MyDriveLoginTab, self).__init__()
        uic.loadUi(os.path.join(TABSFOLDER, "MyDriveLoginTab.ui"), self)
        self.pushButton_login.clicked.connect(self.loginButton)
        self.lineEdit_username.textChanged.connect(self.onUsernameChange)
        self.lineEdit_password.textChanged.connect(self.onPasswordChange)
        self.checkBox_remember.stateChanged.connect(lambda:self.onChangeRemember(self.checkBox_remember))
        
        self.settings = QSettings('Ellipsis Drive', 'Ellipsis Drive Connect')

        self.username = ""
        self.password = ""
        self.userInfo = {}
        self.rememberMe = self.checkBox_remember.isChecked()
        self.loggedIn = False
    
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

    def displayLoginError(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)

        msg.setText("Please enter your correct username and password.")
        msg.setWindowTitle("Login failed!")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return

    def getUserData(self, token):
        log("Getting user data")
        apiurl = f"{URL}/account/info"
        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(apiurl, headers=headers)
        data = resp.json()
        jlog(data)
        if (resp):
            log("getUserData success")
            self.userInfo = data
            return True
        log("getUserData failed")
        return False
        

    def loginButton(self):
        """ handler for the log in button """
        actual_remember = False
        # check if the user is sure that they want us to remember their login token
        if (self.rememberMe):
            confirm_remember = self.confirmRemember()
            if (not confirm_remember):
                return
            else:
                actual_remember = True

        apiurl = f"{URL}/account/login"
        log(f'Logging in: username: {self.username}, password: {self.password}')

        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/json"
        data = '{"username": "%s", "password": "%s", "validFor": %i}' % (self.username, self.password, 3155760000)

        log(data)
        resp = requests.post(apiurl, headers=headers, data=data)
        data = resp.json()
        jlog(data)
        if resp:
            #print(f"Token: {data['token']}")
            self.loggedIn = True
            loginToken = data['token']
            log("logged in")
            if actual_remember:
                self.settings.setValue("token",data["token"])
                log("login token saved to settings")
            else:
                log("token NOT saved to settings")
            
            if self.getUserData(loginToken):
                self.loginSignal.emit(loginToken, self.userInfo)
            self.username = ""
            self.password = ""
            self.lineEdit_username.setText("")
            self.lineEdit_password.setText("")
        else:
            self.displayLoginError()
            log("Login failed")

    def onUsernameChange(self, text):
        self.username = text

    def onPasswordChange(self, text):
        self.password = text

class MyDriveLoggedInTab(QDialog):
    """ The LoggedIn tab, giving users access to their drive"""
    logoutSignal = pyqtSignal()
    def __init__(self):
        super(MyDriveLoggedInTab, self).__init__()
        uic.loadUi(os.path.join(TABSFOLDER, "MyDriveLoggedInTab.ui"), self)
        self.loginToken = ""
        self.loggedIn = False
        self.userInfo = {}
        self.selected = None
        self.level = 0
        self.mode = ""
        self.path = "/"
        self.folderstack = []
        self.currentlySelectedMap = None
        self.currentlySelectedId = ""
        self.searching = False
        self.searchText = ""

        self.listWidget_mydrive.itemDoubleClicked.connect(self.onListWidgetClick)

        self.pushButton_logout.clicked.connect(self.logOut)
        self.pushButton_stopsearch.clicked.connect(self.stopSearch)
        self.pushButton_stopsearch.setEnabled(False)

        self.pushButton_wms.clicked.connect(lambda:getUrl("wms", self.currentlySelectedId, self.loginToken))
        self.pushButton_wmts.clicked.connect(lambda:getUrl("wmts", self.currentlySelectedId, self.loginToken))
        self.pushButton_wfs.clicked.connect(lambda:getUrl("wfs", self.currentlySelectedId, self.loginToken))
        self.pushButton_wcs.clicked.connect(lambda:getUrl("wcs", self.currentlySelectedId, self.loginToken))

        self.listWidget_mydrive_maps.itemClicked.connect(self.onMapItemClick)

        self.lineEdit_search.textChanged.connect(self.onSearchChange)

        self.settings = QSettings('Ellipsis Drive', 'Ellipsis Drive Connect')
        self.disableCorrectButtons(True)
        self.populateListWithRoot()

    def stopSearch(self):
        self.searching = False
        self.searchText = ""
        self.pushButton_stopsearch.setEnabled(False)
        self.lineEdit_search.setText("")
        self.returnToNormal()

    def resetState(self):
        self.clearListWidget()
        self.loginToken = ""
        self.loggedIn = False
        self.userInfo = {}
        self.selected = None
        self.level = 0
        self.mode = ""
        self.path = "/"
        self.folderstack = []
        self.currentlySelectedMap = None
        self.currentlySelectedId = ""
        self.searching = False
        self.searchText = ""
        self.disableCorrectButtons(True)
        self.populateListWithRoot()

    def returnToNormal(self):
        if len(self.folderstack) == 0:
            self.populateListWithRoot()
        else:
            self.getFolder(self.folderstack[len(self.folderstack)-1], len(self.folderstack) == 1)

    @debounce(0.5)
    def performSearch(self):
        if not self.searching:
            return
        log("performing search")

        self.clearListWidget(True)
        self.currentlySelectedId = ""
        self.disableCorrectButtons(True)

        apiurl1 = f"{URL}/account/maps"
        apiurl2 = f"{URL}/account/shapes"

        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        if (not self.loginToken == ""):
            headers["Authorization"] = f"Bearer {self.loginToken}"
        data = {
            "access": ["owned", "subscribed", "favorited"],
            "name": f"{self.searchText}",
        }

        j1 = requests.post(apiurl1, json=data, headers=headers)
        j2 = requests.post(apiurl2, json=data, headers=headers)

        if not j1 or not j2:
            log("performSearch failed!")
            log("Data:")
            log(data)
            log("Headers:")
            log(headers)
            if not j1:
                log("Maps:")
                log(apiurl1)
                log(j1.content)
            if not j2:
                log("Shapes:")
                log(apiurl2)
                log(j2.content)

        data = json.loads(j1.text)
        data2 = json.loads(j2.text)

        [self.listWidget_mydrive_maps.addItem(convertMapdataToListItem(mapdata, False, False, True, getErrorLevel(mapdata))) for mapdata in data["result"]]
        [self.listWidget_mydrive_maps.addItem(convertMapdataToListItem(mapdata, False, True, False, getErrorLevel(mapdata))) for mapdata in data2["result"]]
        if len(data["result"]) == 0  and len(data2["result"]) == 0:
            listitem = QListWidgetItem()
            listitem.setText("No results found!")
            self.listWidget_mydrive_maps.addItem(listitem)
            log("no search results")


    def onSearchChange(self, text):
        if (text == ""):
            self.searching = False
            self.searchText = ""
            self.pushButton_stopsearch.setEnabled(False)
            self.returnToNormal()
        else:
            self.pushButton_stopsearch.setEnabled(True)
            self.searching = True
            self.searchText = text
            self.performSearch()

    def disableCorrectButtons(self, disableAll = False, WCSDisabled = False):
        """ helper function to fix the currently enabled buttons """
        self.pushButton_wms.setEnabled(False)
        self.pushButton_wmts.setEnabled(False)
        self.pushButton_wfs.setEnabled(False)
        self.pushButton_wcs.setEnabled(False)
        
        if disableAll or self.currentlySelectedMap is None:
            return

        if self.currentlySelectedMap.data((QtCore.Qt.UserRole)).isShape():
            self.pushButton_wfs.setEnabled(True)
        else:
            self.pushButton_wms.setEnabled(True)
            self.pushButton_wmts.setEnabled(True)
            if (not WCSDisabled):
                self.pushButton_wcs.setEnabled(True)
        
        #TODO implement logic based on the selected map? or do that when a map is selected

    def onMapItemClick(self, item):
        if item.data((QtCore.Qt.UserRole)).getType() == "error":
            return
        self.currentlySelectedId = item.data((QtCore.Qt.UserRole)).getData()
        self.currentlySelectedMap = item
        log(f"{item.text()}, data type: {item.data((QtCore.Qt.UserRole)).getType()}, data value: {item.data((QtCore.Qt.UserRole)).getData()}")
        self.disableCorrectButtons(WCSDisabled = (item.data((QtCore.Qt.UserRole)).getDisableWCS()))

    def removeFromPath(self):
        """ remove one level from the path, useful when going back in the folder structure """
        if (self.level == 0):
            self.setPath("/")
            return
        self.setPath(self.path.rsplit('/',1)[0])

    def addToPath(self, foldername):
        if self.path == "/":
            self.path = ""
        self.setPath(f"{self.path}/{foldername}")

    def setPath(self, path):
        """ set the displayed path """
        self.path = path
        self.label_path.setText(f"{path}")

    def onNext(self):
        """ handler for the Next button, used for navigating the folder structure """
        log("BEGIN")
        log(self.folderstack)
        success = True
        if (self.level == 0):
            success = self.onNextRoot()
        else:
            success = self.onNextNormal()
        if success:
            self.level += 1
            self.selected = None
            self.currentlySelectedMap = None
            self.currentlySelectedId = ""
            self.disableCorrectButtons()
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Error!")
            msg.setText("Cannot open this folder")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            log("cannot open the folder")
        log(f"level: {self.level} folderstack: {self.folderstack}")
        log("END")
        # TODO using addToPath

    def onNextNormal(self):
        """ non-root onNext"""
        pathId = self.selected.data(QtCore.Qt.UserRole).getData()
        if self.getFolder(pathId):
            self.folderstack.append(pathId)
            self.addToPath(self.selected.text())
            return True
        else:
            log("Error! onNextNormal: getFolder failed")
            log(f"pathid: {pathId}")
            return False
        
        #self.addToPath(pathId = self.selected.get)

    def onNextRoot(self):
        """ onNext for root folders """
        root = self.selected.data(QtCore.Qt.UserRole).getData()
        if self.getFolder(root, True):
            self.folderstack.append(root)
            self.addToPath(root)
            return True
        else:
            log("Error! onNextRoot: getFolder failed")
            log(f"root: {root}")
            return False

    def getFolder(self, id, isRoot=False):
        """ clears the listwidgets and fills them with the folders and maps in the specified folder """
        apiurl = ""
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        headers["Authorization"] = f"Bearer {self.loginToken}"
        data = {}
        data2= {}
        if (isRoot):
            apiurl = f"{URL}/path/listRoot"
            data = {
            "root": f"{id}",
            "type": "map"
            }
            data2 = {
                "root": f"{id}",
                "type": "folder"
            }
        else:
            apiurl = f"{URL}/path/listFolder"
            data = {
                "pathId": f"{id}",
                "type": "map"
            }
            data2 = {
                "pathId": f"{id}",
                "type": "folder"
            }

        j1 = requests.post(apiurl, json=data, headers=headers)
        j2 = requests.post(apiurl, json=data2, headers=headers)

        if not j1 or not j2:
            log("getFolder failed!")
            log("Data:")
            log(data)
            log("Headers:")
            log(headers)
            log("Url:")
            log(apiurl)
            if not j1:
                log("Map:")
                log(j1.content)
            if not j2:
                log("Folder:")
                log(j2.content)
            return False
        
        self.clearListWidget()

        maps = json.loads(j1.text)
        folders = json.loads(j2.text)

        [self.listWidget_mydrive_maps.addItem(convertMapdataToListItem(mapdata, False, errorLevel=getErrorLevel(mapdata))) for mapdata in maps["result"]]
        [self.listWidget_mydrive.addItem(convertMapdataToListItem(folderdata, True)) for folderdata in folders["result"]]
        return True

    def onPrevious(self):
        log("onPrevious start")
        log(self.folderstack)
        self.level -= 1
        self.removeFromPath()
        self.selected = None
        self.currentlySelectedId = ""
        self.currentlySelectedMap = None

        if self.level == 0:
            self.populateListWithRoot()
            self.path = "/"
            self.folderstack = []
            self.disableCorrectButtons(True)
            log(self.folderstack)
            log("onPrevious level 0 end")
            return
        
        if self.level == 1:
            if (self.getFolder(self.folderstack[0], True)):
                self.folderstack.pop()
                self.disableCorrectButtons()
                log(self.folderstack)
                log("onPrevious level 1 end")
                return
            else:
                log("Error on getFolder!")

        
        if self.getFolder(self.folderstack[len(self.folderstack) - 2]):
            self.folderstack.pop()
            self.disableCorrectButtons()
            log(self.folderstack)
            log("onPrevious regular end")
        else:
            log("getFolder failed!")
        

    def clearListWidget(self, isRoot = False):
        """ clears list widgets"""
        for _ in range(self.listWidget_mydrive.count()):
            self.listWidget_mydrive.takeItem(0)
        #no parent folder of the root folder, so don't display the ".." directory
        if  not isRoot:
            retitem = QListWidgetItem()
            retitem.setText("..")
            retitem.setData(QtCore.Qt.UserRole, ListData("return", "..", False))
            retitem.setIcon(QIcon(FOLDERICON))
            self.listWidget_mydrive.addItem(retitem)
        
        for _ in range(self.listWidget_mydrive_maps.count()):
            self.listWidget_mydrive_maps.takeItem(0)
        

    def onListWidgetClick(self, item):
        self.selected = item
        if self.selected.data(QtCore.Qt.UserRole).getType() == "return":
            self.onPrevious()
        else:
            self.onNext()

    def logOut(self):
        """ emits the logout signal and removes the login token from the settings """
        log("logging out")
        if (self.settings.contains("token")):
            self.settings.remove("token")
        self.logoutSignal.emit()

    def populateListWithRoot(self):
        """ Clears the listwidgets and adds the 3 root folders to the folder widget """
        self.clearListWidget(True)
        myprojects = ListData("rootfolder", "myMaps")
        sharedwithme = ListData("rootfolder", "shared")
        favorites = ListData("rootfolder", "favorites")

        myprojectsitem = QListWidgetItem()
        sharedwithmeitem = QListWidgetItem()
        favoritesitem = QListWidgetItem()

        myprojectsitem.setText("My Projects")
        sharedwithmeitem.setText("Shared with me")
        favoritesitem.setText("Favorites")

        myprojectsitem.setData(QtCore.Qt.UserRole, myprojects)
        sharedwithmeitem.setData(QtCore.Qt.UserRole, sharedwithme)
        favoritesitem.setData(QtCore.Qt.UserRole, favorites)

        myprojectsitem.setIcon(QIcon(FOLDERICON))
        sharedwithmeitem.setIcon(QIcon(FOLDERICON))
        favoritesitem.setIcon(QIcon(FOLDERICON))

        self.listWidget_mydrive.addItem(myprojectsitem)
        self.listWidget_mydrive.addItem(sharedwithmeitem)
        self.listWidget_mydrive.addItem(favoritesitem)

class MyDriveTab(QDialog):
    loginSignal = pyqtSignal(object)
    logoutSignal = pyqtSignal()
    def __init__(self):
        super(MyDriveTab, self).__init__()
        uic.loadUi(os.path.join(TABSFOLDER, "MyDriveStack.ui"), self)

        # idea: use QStacketWidget to switch between logged in and logged out

        self.loginWidget = MyDriveLoginTab()
        self.loggedInWidget = MyDriveLoggedInTab()

        self.loggedIn = False
        self.loginToken = ""

        self.userInfo = {}

        self.loginWidget.loginSignal.connect(self.handleLoginSignal)
        self.loggedInWidget.logoutSignal.connect(self.handleLogoutSignal)

        self.stackedWidget.addWidget(self.loginWidget)
        self.stackedWidget.addWidget(self.loggedInWidget)
        
        self.settings = QSettings('Ellipsis Drive', 'Ellipsis Drive Connect')

        if (self.settings.contains("token")):
            log("Login data found")
            self.loggedIn = True
            self.loginToken = self.settings.value("token")
            self.loggedInWidget.loginToken = self.loginToken
            log("Getting username")
            apiurl = f"{URL}/account/info"
            headers = CaseInsensitiveDict()
            headers["Authorization"] = f"Bearer {self.loginToken}"
            resp = requests.get(apiurl, headers=headers)
            data = resp.json()
            jlog(data)
            if (resp):
                log("getting user info success")
                self.loggedInWidget.userInfo = data
                self.loggedInWidget.label.setText(f"Welcome {data['username']}!")
            else:
                log("getUserData failed")

            self.stackedWidget.setCurrentIndex(1)
        else:
            log("No login data found")

    def handleLoginSignal(self, token, userInfo):
        log("login signal received!")
        self.loginToken = token
        self.loggedIn = True
        self.loggedInWidget.loginToken = token
        self.loggedInWidget.loggedIn = True
        self.loggedInWidget.userInfo = userInfo
        self.loggedInWidget.label.setText(f"Welcome {userInfo['username']}!")
        self.userInfo = userInfo
        self.loginSignal.emit(token)
        self.stackedWidget.setCurrentIndex(1)
    
    def handleLogoutSignal(self):
        log("logout signal received!")
        self.loggedIn = False
        self.loginToken = ""
        self.loggedInWidget.loggedIn = False
        self.loggedInWidget.loginToken = ""
        self.loggedInWidget.resetState()
        self.stackedWidget.setCurrentIndex(0)
    
class CommunityTab(QDialog):
    def __init__(self):
        super(CommunityTab, self).__init__()
        uic.loadUi(os.path.join(TABSFOLDER, "CommunityTab.ui"), self)
        self.communitySearch = ""
        self.currentlySelectedId = ""
        self.currentlySelectedMap = None
        self.loginToken = ""

        self.listWidget_community.itemClicked.connect(self.onCommunityItemClick)
        self.lineEdit_communitysearch.textChanged.connect(self.onCommunitySearchChange)

        self.pushButton_wms.clicked.connect(lambda:getUrl("wms", self.currentlySelectedId))
        self.pushButton_wmts.clicked.connect(lambda:getUrl("wmts", self.currentlySelectedId))
        self.pushButton_wfs.clicked.connect(lambda:getUrl("wfs", self.currentlySelectedId))
        self.pushButton_wcs.clicked.connect(lambda:getUrl("wcs", self.currentlySelectedId))
        

        self.disableCorrectButtons(True)

        self.settings = QSettings('Ellipsis Drive', 'Ellipsis Drive Connect')

        if (self.settings.contains("token")):
            self.loginToken = self.settings.value("token")

        self.getCommunityList()

    # api.ellipsis-drive.com/v1/wms/mapId
    # api.ellipsis-drive.com/v1/wmts/mapId
    # api.ellipsis-drive.com/v1/wfs/mapId

    def disableCorrectButtons(self, disableAll = False):
        """ enable and disable the correct buttons in the community library tab """

        self.pushButton_wms.setEnabled(False)
        self.pushButton_wmts.setEnabled(False)
        self.pushButton_wfs.setEnabled(False)
        self.pushButton_wcs.setEnabled(False)
        
        if disableAll or self.currentlySelectedMap is None:
            return

        if self.currentlySelectedMap.data((QtCore.Qt.UserRole)).isShape():
            self.pushButton_wfs.setEnabled(True)
        else:
            self.pushButton_wms.setEnabled(True)
            self.pushButton_wmts.setEnabled(True)
            self.pushButton_wcs.setEnabled(True)

    
    @debounce(0.5)
    def getCommunityList(self):
        """ gets the list of public projects and add them to the list widget on the community tab """

        # reset the list before updating it
        # self.listWidget_community.clear()

        print(f"getCommunityList called, token = '{self.loginToken}'")

        for _ in range(self.listWidget_community.count()):
            self.listWidget_community.takeItem(0)
        
        self.currentlySelectedId = ""
        self.disableCorrectButtons(True)

        apiurl1 = f"{URL}/account/maps"
        apiurl2 = f"{URL}/account/shapes"
        log("Getting community maps")
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        if (not self.loginToken == ""):
            headers["Authorization"] = f"Bearer {self.loginToken}"
        data1 = {
            "access": ["public"],
            "name": f"{self.communitySearch}",
            "disabled": False,
            "hasTimestamps": True
        }

        data2= {
            "access": ["public"],
            "name": f"{self.communitySearch}",
            "disabled": False,
            "hasGeometryLayers": True
        }

        j1 = requests.post(apiurl1, json=data1, headers=headers)
        j2 = requests.post(apiurl2, json=data2, headers=headers)
        if not j1 or not j2:
            log("getCommunityList failed!")
            return
        data = json.loads(j1.text)
        data2 = json.loads(j2.text)

        [self.listWidget_community.addItem(convertMapdataToListItem(mapdata, False, False, True, errorLevel=getErrorLevel(mapdata))) for mapdata in data["result"]]
        [self.listWidget_community.addItem(convertMapdataToListItem(mapdata, False, True, False, errorLevel=getErrorLevel(mapdata))) for mapdata in data2["result"]]
        
    def onCommunitySearchChange(self, text):
        """ Change the internal state of the community search string """
        self.communitySearch = text
        self.getCommunityList()

    def onCommunityItemClick(self, item):
        self.currentlySelectedId = item.data((QtCore.Qt.UserRole)).getData()
        self.currentlySelectedMap = item
        log(f"{item.text()}, data type: {item.data((QtCore.Qt.UserRole)).getType()}, data value: {item.data((QtCore.Qt.UserRole)).getData()}")
        self.disableCorrectButtons()

        
class EllipsisConnectDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(EllipsisConnectDialog, self).__init__(parent)
        self.mydrivetab = MyDriveTab()
        self.communitytab = CommunityTab()
        self.mydrivetab.loginSignal.connect(self.handleLoginSignal)
        self.mydrivetab.logoutSignal.connect(self.handleLogoutSignal)
        self.setupUi(self)
        self.tabWidget.addTab(self.mydrivetab, "My Drive")
        self.tabWidget.addTab(self.communitytab, "Community Library")
    
    def handleLoginSignal(self, token):
        self.communitytab.loginToken = token
        self.communitytab.getCommunityList()
    
    def handleLogoutSignal(self):
        self.communitytab.loginToken = ""
        self.communitytab.getCommunityList()