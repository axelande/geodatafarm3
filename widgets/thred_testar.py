from PyQt4 import QtGui, QtCore
import sys
import random


class Example(QtCore.QObject):
    signalStatus = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)

        # Create a gui object.
        self.gui = Window()

        # Setup the worker object and the worker_thread.
        self.worker = WorkerObject()
        self.worker_thread = QtCore.QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Make any cross object connections.
        self._connectSignals()

        self.gui.show()

    def _connectSignals(self):
        self.gui.button_start.clicked.connect(self.worker.startWork)
        self.gui.button_cancel.clicked.connect(self.forceWorkerReset)
        self.signalStatus.connect(self.gui.updateStatus)
        self.worker.signalStatus.connect(self.gui.updateStatus)

        self.parent().aboutToQuit.connect(self.forceWorkerQuit)

    def forceWorkerReset(self):
        if self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()

            self.signalStatus.emit('Idle.')
            self.worker_thread.start()

    def forceWorkerQuit(self):
        if self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()


class WorkerObject(QtCore.QObject):
    signalStatus = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)

    @QtCore.pyqtSlot()
    def startWork(self):
        for ii in range(7):
            number = random.randint(0,5000**ii)
            self.signalStatus.emit('Iteration: {}, Factoring: {}'.format(ii, number))
            factors = self.primeFactors(number)
            print('Number: ', number, 'Factors: ', factors)
        self.signalStatus.emit('Idle.')

    def primeFactors(self, n):
        i = 2
        factors = []
        while i * i <= n:
            if n % i:
                i += 1
            else:
                n //= i
                factors.append(i)
        if n > 1:
            factors.append(n)
        return factors


class Window(QtGui.QWidget):

    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.button_start = QtGui.QPushButton('Start', self)
        self.button_cancel = QtGui.QPushButton('Cancel', self)
        self.label_status = QtGui.QLabel('', self)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.button_start)
        layout.addWidget(self.button_cancel)
        layout.addWidget(self.label_status)

        self.setFixedSize(400, 200)

    @QtCore.pyqtSlot(str)
    def updateStatus(self, status):
        self.label_status.setText(status)


if __name__=='__main__':
    app = QtGui.QApplication(sys.argv)
    example = Example(app)
    sys.exit(app.exec_())