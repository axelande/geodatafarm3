"""Backwards-compatible shim for the old generate_taskdata module path.

The implementation was split into `generate_taskdata_widgets` and
`generate_taskdata_commands`. Tests and third-party code may still
import the old module path; this shim re-exports a compatible
`GenerateTaskDataWidget` subclass that preserves a minimal set of
attributes expected by callers (notably `show_generate_menu`).

Prefer importing from `generate_taskdata_widgets` and
`generate_taskdata_commands` directly in new code.
"""

from .generate_taskdata_widgets import GenerateTaskDataWidget as _GTW, distance


class GenerateTaskDataWidget(_GTW):
	"""Compatibility subclass exposing legacy attributes expected by callers.

	We add a no-op `show_generate_menu` to allow tests and callers to
	monkeypatch or call it; other behaviour is inherited from the
	modern implementation in `generate_taskdata_widgets`.
	"""

	def show_generate_menu(self, anchor_widget=None):
		# legacy hook — kept as a no-op for compatibility and testing
		return None


__all__ = ["GenerateTaskDataWidget", "distance"]