from qgis.PyQt.QtWidgets import QMessageBox


class MsgError(Exception):
	"""Small helper exception that also shows a QMessageBox for the user.

	Usage: raise MsgError('Something went wrong')
	This will raise an exception and display a message box. Works with
	both Qt5 and Qt6 (`exec` / `exec_`).
	"""

	def __init__(self, text):
		super().__init__(text)
		box = QMessageBox()
		box.setText(str(text))
		# exec() in Qt6, exec_() in some older Qt bindings
		try:
			box.exec()
		except TypeError:
			box.exec_()

