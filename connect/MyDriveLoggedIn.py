import os
import json
import urllib
from enum import Enum, auto

from PyQt5.QtGui import QIcon
import requests

from PyQt5.QtWidgets import QDialog

from qgis.PyQt import uic

from qgis.PyQt.QtCore import QSettings, pyqtSignal

from PyQt5 import QtCore

from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject

from qgis.PyQt.QtWidgets import QListWidgetItem, QMessageBox
from requests import api

from .util import *

class Action(Enum):
    STOPTIMESTAMP = auto()
    STOPMAPLAYER = auto()
    STOPGEOMETRYLAYER = auto()

class Type(Enum):
    TIMESTAMP = auto()
    MAPLAYER = auto()
    ACTION = auto()

class ViewMode(Enum):
    NORMAL = auto()
    WMS = auto()
    WMTS = auto()
    WFS = auto()
    WCS = auto()

class ViewSubMode(Enum):
    NONE = auto()
    TIMESTAMPS = auto()
    MAPLAYERS = auto()
    GEOMETRYLAYERS = auto()

def mapViewMode(str):
    if str == "wms":
        return ViewMode.WMS
    if str == "wmts":
        return ViewMode.WMTS
    if str == "wfs":
        return ViewMode.WFS
    if str == "wcs":
        return ViewMode.WCS

class MyDriveLoggedInTab(QDialog):
    """ The LoggedIn tab, giving users access to their drive. Used in combination with the MyDriveTab and the MyDriveLoginTab"""
    logoutSignal = pyqtSignal()
    def __init__(self):
        super(MyDriveLoggedInTab, self).__init__()
        uic.loadUi(os.path.join(TABSFOLDER, "MyDriveLoggedInTab.ui"), self)
        self.loginToken = ""
        self.loggedIn = False
        self.userInfo = {}
        self.selected = None
        self.level = 0
        self.path = "/"
        self.folderStack = []
        self.currentlySelectedMap = None
        self.currentlySelectedId = ""
        self.searching = False
        self.searchText = ""
        self.currentMetaData = None
        self.currentTimestampId = ""
        self.currentMapId = ""
        self.currentMode = ViewMode.NORMAL
        self.currentSubMode = ViewSubMode.NONE
        self.currentItem = None

        self.listWidget_mydrive.itemDoubleClicked.connect(self.onListWidgetClick)

        self.pushButton_logout.clicked.connect(self.logOut)
        self.pushButton_stopsearch.clicked.connect(self.stopSearch)
        self.pushButton_stopsearch.setEnabled(False)

        self.pushButton_wms.clicked.connect(lambda:self.onClickGet("wms"))
        self.pushButton_wmts.clicked.connect(lambda:self.onClickGet("wmts"))
        self.pushButton_wfs.clicked.connect(lambda:self.onClickGet("wfs"))
        self.pushButton_wcs.clicked.connect(lambda:self.onClickGet("wcs"))

        self.listWidget_mydrive_maps.itemClicked.connect(self.onMapItemClick)
        self.listWidget_mydrive_maps.itemDoubleClicked.connect(self.onMapItemDoubleClick)

        self.listWidget_mydrive_maps.itemSelectionChanged.connect(lambda:self.pushButton_wcs.setText("Get WCS"))

        self.lineEdit_search.textChanged.connect(self.onSearchChange)

        self.settings = QSettings('Ellipsis Drive', 'Ellipsis Drive Connect')
        self.disableCorrectButtons(True)
        self.populateListWithRoot()

    def fixBottomListWidget(self):
        log("fixBottomListWidget")
        log(self.currentMode)
        log(self.currentSubMode)

        self.clearMapsWidget()

        if (self.currentMode == ViewMode.NORMAL):
            self.getFolder(self.folderStack[-1])

        elif (self.currentMode == ViewMode.WMS or self.currentMode == ViewMode.WMTS):
            if (self.currentSubMode == ViewSubMode.TIMESTAMPS):
                timestamps = self.currentMetaData["timestamps"]
                maplayers = self.currentMetaData["mapLayers"]
                self.listWidget_mydrive_maps.addItem(toListItem(Action.STOPTIMESTAMP, ".."))
                for timestamp in timestamps:
                    self.listWidget_mydrive_maps.addItem(toListItem("timestamp", timestamp["id"], data=timestamp["id"], extra=maplayers))

            elif (self.currentSubMode == ViewSubMode.MAPLAYERS):
                self.currentTimestampId = self.currentItem.getData()
                self.listWidget_mydrive_maps.addItem(toListItem(Action.STOPMAPLAYER, "..", None))
                mapLayers = self.currentItem.getExtra()
                for mapLayer in mapLayers:
                    self.listWidget_mydrive_maps.addItem(toListItem("mapLayer", mapLayer["name"], mapLayer))
                    log("display timestamps wms")
        elif (self.currentMode == ViewMode.WFS):
                geometryLayers = self.currentMetaData["geometryLayers"]
                self.listWidget_mydrive_maps.addItem(toListItem(Action.STOPGEOMETRYLAYER, ".."))
                for geometryLayer in geometryLayers:
                    self.listWidget_mydrive_maps.addItem(toListItem("timestamp", geometryLayer["name"], data=geometryLayer["id"]))

        elif (self.currentMode == ViewMode.WCS):
            log(self.currentMetaData)
            pass
        

    def WMSDoubleClick(self, item):
        item = item.data((QtCore.Qt.UserRole))
        if item.getType() == Action.STOPTIMESTAMP:
            self.currentMode = ViewMode.NORMAL
            self.currentSubMode = ViewSubMode.NONE

        elif item.getType() == Action.STOPMAPLAYER:
            self.currentSubMode = ViewSubMode.TIMESTAMPS

        elif item.getType() == "timestamp":
            self.currentSubMode = ViewSubMode.MAPLAYERS
            self.currentItem = item

        elif item.getType() == "mapLayer":
            data = item.getData()
            ids = f"{self.currentTimestampId}_{data['id']}"
            mapid = self.currentMapId
            theurl = F"{DEVURL}/wms/{mapid}"
            actualurl = f"CRS=EPSG:3857&format=image/png&layers={ids}&styles&token={self.loginToken}&url={theurl}"
            rlayer = QgsRasterLayer(actualurl, "some layer name", 'WMS')
            if not rlayer.isValid():
                log("Layer failed to load!") 
            else:
                QgsProject.instance().addMapLayer(rlayer)

    def WMTSDoubleClick(self, item):
        item = item.data((QtCore.Qt.UserRole))
        if item.getType() == Action.STOPTIMESTAMP:
            self.currentMode = ViewMode.NORMAL
            self.currentSubMode = ViewSubMode.NONE

        elif item.getType() == Action.STOPMAPLAYER:
            self.currentSubMode = ViewSubMode.TIMESTAMPS

        elif item.getType() == "timestamp":
            self.currentSubMode = ViewSubMode.MAPLAYERS
            self.currentItem = item

        elif item.getType() == "mapLayer":
            data = item.getData()
            ids = f"{self.currentTimestampId}_{data['id']}"
            mapid = self.currentMapId
            theurl = F"{DEVURL}/wmts/{mapid}"
            actualurl = f"CRS=EPSG:3857&format=image/png&layers={ids}&styles&token={self.loginToken}&url={theurl}"
            rlayer = QgsRasterLayer(actualurl, "some layer name", 'WMTS')
            if not rlayer.isValid():
                log("Layer failed to load!") 
            else:
                QgsProject.instance().addMapLayer(rlayer)


    def WFSDoubleClick(self, item):
        text = item.text()
        item = item.data((QtCore.Qt.UserRole))
        
        if item.getType() == Action.STOPGEOMETRYLAYER:
            self.currentmode = ViewMode.NORMAL
            self.currentSubMode = ViewSubMode.NONE
        else:
            id = item.getData()
            mapid = self.currentMapId
            theurl = F"{DEVURL}/wfs/{mapid}"

            params = {
                'service': 'WFS',
                'version': '2.0.0',
                'request': 'GetFeature',
                'typename': 'ms:cities',
                'srsname': "EPSG:4326"
            }
            uri = f'{theurl}' + urllib.parse.unquote(urllib.parse.urlencode(params))
            rlayer = QgsVectorLayer(uri, text, 'WFS')

            if not rlayer.isValid():
                log("Layer failed to load!") 
            else:
                QgsProject.instance().addMapLayer(rlayer)

    def WCSDoubleClick(self, item):
        pass

    def onMapItemDoubleClick(self, item):
        if self.currentMode == ViewMode.NORMAL:
            return
        elif self.currentMode == ViewMode.WMS:
            self.WMSDoubleClick(item)
        elif self.currentMode == ViewMode.WMTS:
            self.WMTSDoubleClick(item)
        elif self.currentMode == ViewMode.WFS:
            self.WFSDoubleClick(item)
        elif self.currentMode == ViewMode.WCS:
            self.WCSDoubleClick(item)
        self.fixBottomListWidget()

    def onClickGet(self, mode):
        """ function called when 'Get WMS/WMTS/WFS/WCS' is clicked, edits the url textbox and displays instruction """
        self.currentMapId = self.currentlySelectedId
        self.currentMode = mapViewMode(mode)
        self.currentSubMode = ViewSubMode.NONE
        self.lineEdit_theurl.setText(getUrl(mode, self.currentlySelectedId, self.loginToken))
        self.label_instr.setText("Copy the following url:")
        self.currentMetaData = getMetadata(self.currentlySelectedId, self.loginToken)
        if self.currentMode == ViewMode.WMS or self.currentMode == ViewMode.WMTS or self.currentMode == ViewMode.WCS:
            self.currentSubMode = ViewSubMode.TIMESTAMPS
        elif self.currentMode == ViewMode.WFS:
            self.currentSubMode = ViewSubMode.GEOMETRYLAYERS
            pass
        self.fixBottomListWidget()

    def onRemoveClickGet(self):
        """ helper function called when the 'get url' text box should be emptied """
        self.lineEdit_theurl.setText("")
        self.label_instr.setText("")

    def stopSearch(self):
        """ handler for the Stop Search button: does what it says it does """
        self.searching = False
        self.searchText = ""
        self.pushButton_stopsearch.setEnabled(False)
        self.lineEdit_search.setText("")
        self.returnToNormal()

    def resetState(self):
        """ helper function to reset our state (used when logging out) """
        self.clearListWidget()
        self.loginToken = ""
        self.loggedIn = False
        self.userInfo = {}
        self.selected = None
        self.level = 0
        self.path = "/"
        self.folderStack = []
        self.currentlySelectedMap = None
        self.currentlySelectedId = ""
        self.searching = False
        self.searchText = ""
        self.onRemoveClickGet()

        self.disableCorrectButtons(True)
        self.populateListWithRoot()

    def returnToNormal(self):
        """ return from a search to the state we were in before we started searching """
        if len(self.folderStack) == 0:
            self.populateListWithRoot()
        else:
            self.getFolder(self.folderStack[-1], len(self.folderStack) == 1)

    @debounce(0.5)
    def performSearch(self):
        """ actually perform the search, using self.searchText as the string """
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
        """ handle changes of the search string """
        self.onRemoveClickGet()
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
        """ handler called when an item is clicked in the map/shape listwidget """
        self.onRemoveClickGet()
        if item.data((QtCore.Qt.UserRole)).getType() == "error":
            return
        self.currentlySelectedId = item.data((QtCore.Qt.UserRole)).getData()
        self.currentlySelectedMap = item
        #log(f"{item.text()}, data type: {item.data(QtCore.Qt.UserRole).getType()}")
        #log(f"{item.text()}, data type: {item.data(QtCore.Qt.UserRole).getType()}, data value: {item.data(QtCore.Qt.UserRole).getData()}")
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
        """ extends the current path string """
        if self.path == "/":
            self.path = ""
        self.setPath(f"{self.path}/{foldername}")

    def setPath(self, path):
        """ set the displayed path """
        self.path = path
        toolong = False
        newstr = ""
        if (len(path) > MAXPATHLEN):
            toolong = True
            folders = path.split("/")
            folders.reverse()
            newstr = folders.pop()
            for folder in folders:
                if len(newstr) + len(folder) < 40:
                    newstr = f"{folder}/{newstr}"
                else:
                    break;
        if toolong:
            self.label_path.setText(f"../{newstr}")            
        else:
            self.label_path.setText(f"{path}")

    def onNext(self):
        """ handler for the Next button, used for navigating the folder structure """
        #log("BEGIN")
        #log(self.folderStack)
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
        #log(f"level: {self.level} folderstack: {self.folderStack}")
        #log("END")
        # TODO using addToPath

    def onNextNormal(self):
        """ non-root onNext """
        pathId = self.selected.data(QtCore.Qt.UserRole).getData()
        if self.getFolder(pathId):
            self.folderStack.append(pathId)
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
            self.folderStack.append(root)
            self.addToPath(root)
            return True
        else:
            log("Error! onNextRoot: getFolder failed")
            log(f"root: {root}")
            return False

    def getFolder(self, id, isRoot=False):
        """ clears the listwidgets and fills them with the folders and maps in the specified folder (by folder id) """
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
        [self.listWidget_mydrive.addItem(convertMapdataToListItem(folderdata, True, errorLevel=getErrorLevel(folderdata))) for folderdata in folders["result"]]
        return True

    def onPrevious(self):
        """ handles walking back through te folder tree """
        #log("onPrevious start")
        #log(self.folderStack)
        self.level -= 1
        self.removeFromPath()
        self.selected = None
        self.currentlySelectedId = ""
        self.currentlySelectedMap = None

        if self.level == 0:
            self.populateListWithRoot()
            self.path = "/"
            self.folderStack = []
            self.disableCorrectButtons(True)
            #log(self.folderStack)
            #log("onPrevious level 0 end")
            return
        
        if self.level == 1:
            if (self.getFolder(self.folderStack[0], True)):
                self.folderStack.pop()
                self.disableCorrectButtons()
                #log(self.folderStack)
                #log("onPrevious level 1 end")
                return
            else:
                log("Error on getFolder!")

        
        if self.getFolder(self.folderStack[-2]):
            self.folderStack.pop()
            self.disableCorrectButtons()
            #log(self.folderStack)
            #log("onPrevious regular end")
        else:
            log("getFolder failed!")
        
    def clearFoldersWidget(self, isRoot = False):
        for _ in range(self.listWidget_mydrive.count()):
            self.listWidget_mydrive.takeItem(0)
        #no parent folder of the root folder, so don't display the ".." directory
        if  not isRoot:
            retitem = QListWidgetItem()
            retitem.setText("..")
            retitem.setData(QtCore.Qt.UserRole, ListData("return", "..", False))
            retitem.setIcon(QIcon(FOLDERICON))
            self.listWidget_mydrive.addItem(retitem)

    def clearMapsWidget(self):
        for _ in range(self.listWidget_mydrive_maps.count()):
            self.listWidget_mydrive_maps.takeItem(0)
        

    def clearListWidget(self, isRoot = False):
        """ clears list widgets"""
        self.clearFoldersWidget()
        self.clearMapsWidget()


    def onListWidgetClick(self, item):
        """ handler for clicks on items in the folder listwidget """
        self.onRemoveClickGet()
        if item.data((QtCore.Qt.UserRole)).getType() == "error":
            return
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
