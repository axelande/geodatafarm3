from PyQt4.QtCore import QObject, pyqtSignal, pyqtSlot
from widgets.waiting_msg import WaitingMsg


class Waiting(QObject):
    """A class to open and close a Waiting window in its own thread.
    The idea was to have a GIF animation running here aswell..."""
    signalStatus = pyqtSignal(str)

    def __init__(self, wait_msg, parent=None):
        super(self.__class__, self).__init__(parent)
        self.wait_msg = wait_msg
        self.w = None

    start = pyqtSignal(str)
    @pyqtSlot()
    def start_work(self):
        """To start the waiting window"""
        self.w = WaitingMsg()
        self.w.LWatingMsgs.setText(self.wait_msg)
        self.w.show()
        self.w.exec_()

    @pyqtSlot()
    def stop_work(self):
        """To close the Waiting window"""
        self.w.done(0)