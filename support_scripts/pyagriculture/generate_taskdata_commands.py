from qgis.PyQt.QtWidgets import QDialog

from .create_recipe import CreateRecipe
from .meta_data_widgets import MetaData


class GenerateTaskCommands:
    """Separate command helpers for creating metadata dialogs.

    This class centralises the small set of actions that open other
    dialogs (recipe, farm, customer, worker, device). Keeping them
    here makes it easy to test or reuse without pulling in the full
    widget implementation.
    """
    def __init__(self, parent_gdf):
        self.parent_gdf = parent_gdf

    def _main_window(self):
        parent = getattr(self.parent_gdf, 'iface', None)
        if parent is None:
            return None
        try:
            return parent.mainWindow()
        except Exception:
            return None

    def create_new_recipe(self, parent=None, on_recipe_saved=None):
        """Open the CreateRecipe dialog.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget for the dialog.
        on_recipe_saved : callable, optional
            Callback function to call with the saved recipe path after the dialog closes.
        """
        main_win = self._main_window() or parent
        dlg = CreateRecipe(main_win if main_win is not None else None, parent_gdf=self.parent_gdf)
        # Avoid blocking modal exec() during tests
        if getattr(self.parent_gdf, 'test_mode', False):
            try:
                dlg.show()
            except Exception:
                pass
            return dlg

        exec_fn = getattr(dlg, 'exec', None)
        if callable(exec_fn):
            try:
                exec_fn()
                # After dialog closes, check if a recipe was saved and notify caller
                if dlg.saved_recipe_path and on_recipe_saved:
                    on_recipe_saved(dlg.saved_recipe_path)
                return dlg
            except Exception:
                pass
        try:
            dlg.show()
        except Exception:
            pass
        return dlg

    def create_farm(self, parent=None):
        main_win = self._main_window() or parent
        dlg = MetaData(main_win if main_win is not None else None, 'Farm', self.parent_gdf.schemas.get('FRM'))
        if getattr(self.parent_gdf, 'test_mode', False):
            try:
                dlg.show()
            except Exception:
                pass
            return dlg

        exec_fn = getattr(dlg, 'exec', None)
        if callable(exec_fn):
            try:
                exec_fn()
                return dlg
            except Exception:
                pass
        try:
            dlg.show()
        except Exception:
            pass
        return dlg

    def create_customer(self, parent=None):
        main_win = self._main_window() or parent
        dlg = MetaData(main_win if main_win is not None else None, 'Customer', self.parent_gdf.schemas.get('CTR'))
        if getattr(self.parent_gdf, 'test_mode', False):
            try:
                dlg.show()
            except Exception:
                pass
            return dlg

        exec_fn = getattr(dlg, 'exec', None)
        if callable(exec_fn):
            try:
                exec_fn()
                return dlg
            except Exception:
                pass
        try:
            dlg.show()
        except Exception:
            pass
        return dlg

    def create_worker(self, parent=None):
        main_win = self._main_window() or parent
        dlg = MetaData(main_win if main_win is not None else None, 'Worker', self.parent_gdf.schemas.get('WKR'))
        if getattr(self.parent_gdf, 'test_mode', False):
            try:
                dlg.show()
            except Exception:
                pass
            return dlg

        exec_fn = getattr(dlg, 'exec', None)
        if callable(exec_fn):
            try:
                exec_fn()
                return dlg
            except Exception:
                pass
        try:
            dlg.show()
        except Exception:
            pass
        return dlg

    def create_device(self, parent=None):
        main_win = self._main_window() or parent
        dlg = MetaData(main_win if main_win is not None else None, 'Device', self.parent_gdf.schemas.get('DVC'))
        if getattr(self.parent_gdf, 'test_mode', False):
            try:
                dlg.show()
            except Exception:
                pass
            return dlg

        exec_fn = getattr(dlg, 'exec', None)
        if callable(exec_fn):
            try:
                exec_fn()
                return dlg
            except Exception:
                pass
        try:
            dlg.show()
        except Exception:
            pass
        return dlg

    def open_widget_in_dialog(self, widget_class):
        """Utility to show a widget class inside a dialog.

        Returns the QDialog instance.
        """
        parent = self._main_window()
        dlg = QDialog(parent)
        w = widget_class(parent=dlg, parent_gdf=self.parent_gdf)
        from qgis.PyQt.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(dlg)
        layout.addWidget(w)
        dlg.setLayout(layout)
        # In test mode avoid blocking exec(); show non-modally instead.
        if getattr(self.parent_gdf, 'test_mode', False):
            try:
                dlg.show()
            except Exception:
                pass
            return dlg, w

        try:
            dlg.exec()
        except Exception:
            try:
                dlg.show()
            except Exception:
                pass
        return dlg, w
