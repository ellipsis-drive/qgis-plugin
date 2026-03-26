import time
import requests
from qgis.core import QgsTask, QgsApplication, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QObject, pyqtSignal
from requests.structures import CaseInsensitiveDict
from .util import *



class ApiPollingTask(QgsTask, QObject):
    """
    Background polling task that emits results via signals.
    """
    errorSignal = pyqtSignal(str)

    def __init__(self, uuid, callback):
        QgsTask.__init__(self, "API Polling Task", QgsTask.CanCancel)
        QObject.__init__(self)
        self.uuid = uuid


        self.callback = callback
    def run(self):
        while not self.isCanceled():
            headers = CaseInsensitiveDict()
            headers["Content-Type"] = "application/json"
            reqsuc, content = makeRequest(
                '/account/security/remoteSession/' + self.uuid + '/exercise', headers=headers, data={}, method="POST"
            )
            QgsMessageLog.logMessage(str(content), "MyPlugin", Qgis.Info)
            if reqsuc:

                self.callback(content['token'])
            else:
                pass


            time.sleep(3)
        return True


class PollingManager(QObject):
    """
    Singleton-style manager: start/stop polling from any widget.
    Widgets can provide a callback for a specific response.
    """
    resultSignal = pyqtSignal(dict)
    errorSignal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.task = None
        self.callback = None  # function to run when condition is met

    def startPolling(self, uuid,  callback):
        """
        Start polling the API. If stop_condition(data) returns True,
        the polling stops and callback(data) is run.
        """

        QgsMessageLog.logMessage("Polling starting with " + uuid, "MyPlugin", Qgis.Info)

        if self.task and not self.task.isCanceled():
            QgsMessageLog.logMessage("Polling already running", "MyPlugin", Qgis.Info)
            return self.task

        self.callback = callback

        self.task = ApiPollingTask(uuid, callback)

        QgsApplication.taskManager().addTask(self.task)
        QgsMessageLog.logMessage("Polling started", "MyPlugin", Qgis.Info)
        return self.task

    def _handleResult(self, data):
        self.resultSignal.emit(data)
        if self.stop_condition(data):
            # stop polling
            self.stopPolling()
            if self.callback:
                self.callback(data)

    def stopPolling(self):
        if self.task:
            self.task.cancel()
            self.task = None
            QgsMessageLog.logMessage("Polling stopped", "MyPlugin", Qgis.Info)



POLLING_MANAGER = PollingManager()