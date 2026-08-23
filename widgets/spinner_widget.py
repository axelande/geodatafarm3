"""A small native "busy" spinner - QTimer + QPainter, no external image
asset needed (nothing to bundle/ship). Used to show that a background
QgsTask is running in place of content that isn't ready yet - see
database_scripts/crop_simulation.py's use of this during "Run simulation".
"""
import math

from qgis.PyQt.QtCore import QTimer, Qt
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtWidgets import QWidget

__author__ = 'Axel Horteborn'


class SpinnerWidget(QWidget):
    """A rotating ring of fading dots, redrawn by a QTimer.

    Call :meth:`start` when whatever this indicates begins, :meth:`stop`
    when it ends - neither touches anything outside this widget, so it's
    safe to use regardless of what's actually running in the background.
    """

    def __init__(self, parent=None, dot_count=12, interval_ms=80):
        super().__init__(parent)
        self._dot_count = dot_count
        self._lead_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._advance)
        self.setMinimumSize(60, 60)

    def start(self):
        self._lead_index = 0
        self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _advance(self):
        self._lead_index = (self._lead_index + 1) % self._dot_count
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        radius = side / 2.0 * 0.75
        dot_radius = max(2.0, side / 2.0 * 0.11)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(self._dot_count):
            angle = 2 * math.pi * i / self._dot_count
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            # How far this dot trails behind the lead dot, as a 0..1
            # fraction of a full lap - the fade that makes it read as
            # spinning rather than a static ring of dots.
            trail = ((self._lead_index - i) % self._dot_count) / self._dot_count
            alpha = max(30, int(255 * (1.0 - trail) ** 1.5))
            painter.setBrush(QColor(70, 130, 180, alpha))  # steel blue
            painter.drawEllipse(
                int(x - dot_radius), int(y - dot_radius),
                int(dot_radius * 2), int(dot_radius * 2))
        painter.end()
