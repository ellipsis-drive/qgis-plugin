import os
import json
from PyQt5.QtGui import QIcon
import requests

from PyQt5.QtWidgets import QDialog

from qgis.PyQt import uic

from qgis.PyQt.QtCore import QSettings, pyqtSignal

from PyQt5 import QtCore

from qgis.PyQt.QtWidgets import QListWidgetItem, QMessageBox

from .util import *

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

        self.pushButton_wms.clicked.connect(lambda:self.lineEdit_theurl.setText(getUrl("wms", self.currentlySelectedId, self.loginToken)))
        self.pushButton_wmts.clicked.connect(lambda:self.lineEdit_theurl.setText(getUrl("wmts", self.currentlySelectedId, self.loginToken)))
        self.pushButton_wfs.clicked.connect(lambda:self.lineEdit_theurl.setText(getUrl("wfs", self.currentlySelectedId, self.loginToken)))
        self.pushButton_wcs.clicked.connect(lambda:self.lineEdit_theurl.setText(getUrl("wcs", self.currentlySelectedId, self.loginToken)))

        self.listWidget_mydrive_maps.itemClicked.connect(self.onMapItemClick)
        self.listWidget_mydrive_maps.itemSelectionChanged.connect(lambda:self.pushButton_wcs.setText("Get WCS"))

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
        self.lineEdit_theurl.setText("")
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
        self.lineEdit_theurl.setText("")
        self.pushButton_wcs.setText("Get WCS")
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
        log(WCSDisabled)
        """ helper function to fix the currently enabled buttons """
        self.pushButton_wms.setEnabled(False)
        self.pushButton_wmts.setEnabled(False)
        self.pushButton_wfs.setEnabled(False)
        self.pushButton_wcs.setEnabled(False)
        
        if disableAll or self.currentlySelectedMap is None:
            return

        if self.currentlySelectedMap.data(QtCore.Qt.UserRole).isShape():
            self.pushButton_wfs.setEnabled(True)
        else:
            self.pushButton_wms.setEnabled(True)
            self.pushButton_wmts.setEnabled(True)
            if (not WCSDisabled):
                self.pushButton_wcs.setEnabled(True)
        
        #TODO implement logic based on the selected map? or do that when a map is selected

    def onMapItemClick(self, item):
        self.lineEdit_theurl.setText("")
        if item.data((QtCore.Qt.UserRole)).getType() == "error":
            return
        self.currentlySelectedId = item.data((QtCore.Qt.UserRole)).getData()
        self.currentlySelectedMap = item
        log(f"{item.text()}, data type: {item.data(QtCore.Qt.UserRole).getType()}, data value: {item.data(QtCore.Qt.UserRole).getData()}")
        wcs = (item.data(QtCore.Qt.UserRole).getDisableWCS())
        if (wcs):
            self.pushButton_wcs.setText("Accesslevel too low")
        else:
            self.pushButton_wcs.setText("Get WCS")
        self.disableCorrectButtons(WCSDisabled = (item.data(QtCore.Qt.UserRole).getDisableWCS()))

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
        self.lineEdit_theurl.setText("")
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
