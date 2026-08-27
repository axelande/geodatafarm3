"""User-definable journal fields per operation - the field list the
Add-data form renders, the manual save writes, and the spray-journal
report prints, all read from the farm's own database instead of a Python
literal.

Why this exists: what a spraying journal must contain is set by national
regulation, not by this plugin. Sweden's Jordbruksverket adds eight new
required items from 2026 (purpose, type of use, place of application,
EPPO code, growth stage, registration number, treated area, plus the
existing buffer-zone/pre-harvest-interval items), and the equivalent list
in another country is a different list. Hard-coding one country's set
into widgets/add_data_form.py's ``OPERATIONS`` would mean a plugin
release per regulation change and no way for a grower to record what
their own sprayer actually needs - water volume, nozzle type and
pressure being the three that prompted this.

So the field list is data: a :data:`TEMPLATES` entry seeds
``public.journal_fields``, and from then on that table *is* the
configuration. A user enables, disables, relabels, reorders and adds
fields (see widgets/journal_fields_dialog.py) without touching code.

Storage deliberately stays split in two:

* Fields whose ``key`` is already a real column on the operation's
  manual table (:data:`COLUMN_BACKED`) keep writing to that column.
  ``spray.manual.rate``, ``ferti.manual.nutrient`` and friends are read
  by the report generator, the crop simulation and the fertilizer-timing
  model; moving them would break all of those for no gain.
* Everything else goes into a single ``extra`` jsonb column, added
  lazily (:func:`ensure_extra_column`) with the same check-then-``ALTER
  TABLE`` idiom as database_scripts.db.ensure_ferti_nutrient_column.

The alternative - one real column per user-added field - is what
GeoDataFarm._save_other_from_form does for the "Other" operation, and it
shows the cost: arbitrary user text has to be mangled into an SQL
identifier (``check_text``), producing columns like ``opt1_unit1`` that
nothing can query by name and that no migration can ever clean up. jsonb
needs no schema change per field and no identifier sanitation, and
``extra->>'nozzle_type'`` is a perfectly ordinary thing to select.

A field the user never fills in is simply absent from ``extra`` - the
journal report renders it as an empty cell, exactly like the blank boxes
on Jordbruksverket's own paper form.
"""
from typing import Self

from psycopg2 import sql as pgsql
from psycopg2.extras import Json

from .__init__ import TR, check_text, db_rows

__author__ = 'Axel Horteborn'

_FIELDS_TABLE = 'journal_fields'
_SETTINGS_TABLE = 'journal_settings'

# Field types a journal field can have. Drives which widget the Add-data
# form builds (widgets/add_data_form.py _build_manual_fields) and nothing
# else - every value is stored as text/jsonb regardless, so changing a
# field's type never invalidates data already recorded under it.
TEXT = 'text'
NUMBER = 'number'
CHOICE = 'choice'
DATE = 'date'
BOOL = 'bool'
FIELD_TYPES = (TEXT, NUMBER, CHOICE, DATE, BOOL)

# The columns that physically exist on each operation's manual table (see
# database_scripts/create_new_farm.py add_tables). A journal field whose
# key is listed here writes to that column; anything else goes to the
# jsonb ``extra`` column - see the module docstring.
COLUMN_BACKED = {
    'plant': ('variety', 'spacing', 'seed_rate', 'saw_depth'),
    'ferti': ('variety', 'rate', 'nutrient', 'saw_depth'),
    'spray': ('variety', 'rate', 'wind_speed', 'wind_dir'),
    'harvest': ('total_yield', 'yield'),
    'soil': ('clay', 'humus', 'ph', 'rx'),
    'plowing': ('depth',),
    'harrowing': ('depth',),
}

# operation id -> schema-qualified manual table, for the operations whose
# rows can carry journal fields. Mirrors widgets/add_data_form.py's
# OPERATIONS[...]['table'] - kept here too so the report generator and
# the save path can look a table up without importing the widget module
# (which pulls in Qt).
MANUAL_TABLES = {
    'plant': 'plant.manual',
    'ferti': 'ferti.manual',
    'spray': 'spray.manual',
    'harvest': 'harvest.manual',
    'soil': 'soil.manual',
    'plowing': 'other.plowing_manual',
    'harrowing': 'other.harrowing_manual',
}

DEFAULT_TEMPLATE = 'generic'


class JournalField:
    """One configurable field on one operation's manual form."""

    __slots__ = ('operation', 'key', 'label', 'unit', 'field_type',
                 'choices', 'required', 'sort_order', 'enabled', 'builtin',
                 'remember')

    def __init__(self: Self, operation: str, key: str, label: str,
                 unit: "str | None" = None, field_type: str = TEXT,
                 choices: tuple = (), required: bool = False,
                 sort_order: int = 0, enabled: bool = True,
                 builtin: bool = True, remember: "bool | None" = None) -> None:
        self.operation = operation
        self.key = key
        self.label = label
        self.unit = unit or None
        self.field_type = field_type if field_type in FIELD_TYPES else TEXT
        self.choices = tuple(choices)
        self.required = bool(required)
        self.sort_order = int(sort_order)
        self.enabled = bool(enabled)
        self.builtin = bool(builtin)
        # None means "whatever suits this type" rather than a hard default,
        # so a template entry only has to say so when it wants the opposite
        # (see :func:`remembers_by_default`).
        self.remember = remembers_by_default(self.field_type) \
            if remember is None else bool(remember)

    @property
    def suggestible(self: Self) -> bool:
        """Whether this field should offer what was entered in it before.

        Both halves have to agree: the user left the field's "Remember"
        box ticked, *and* the field is one where a past value is a
        plausible next value. A date or a fixed choice list already has a
        better input of its own, so a history list there is clutter
        rather than help.
        """
        return self.remember and self.field_type in (TEXT, NUMBER)

    @property
    def storage(self: Self) -> str:
        """``'column'`` if this field writes to a real column on the
        operation's manual table, ``'extra'`` if it lives in the jsonb
        column - see the module docstring."""
        return 'column' if self.key in COLUMN_BACKED.get(self.operation, ()) else 'extra'

    def translated_label(self: Self) -> str:
        """The label as shown to the user.

        Built-in labels are English literals in :data:`TEMPLATES` and so
        are picked up by the .ts extraction; a label the user typed
        themselves has no translation and falls through unchanged, which
        is what ``QCoreApplication.translate`` does with an unknown
        source string anyway."""
        return TR('JournalFields').tr(self.label)

    def __repr__(self: Self) -> str:
        return f'<JournalField {self.operation}.{self.key}>'

    def __eq__(self: Self, other) -> bool:
        if not isinstance(other, JournalField):
            return NotImplemented
        return all(getattr(self, s) == getattr(other, s) for s in self.__slots__)


def remembers_by_default(field_type: str) -> bool:
    """Whether a field of this type starts out offering its own history.

    Free text and numbers do: on a spraying journal the operator, the
    nozzle, the pressure, the registration number and the buffer
    distances are the same entry most days, and retyping them is exactly
    the sort of friction that stops a journal being kept. A date is
    different every time, and a fixed choice list and a checkbox already
    are the shortlist.
    """
    return field_type in (TEXT, NUMBER)


def _f(key, label, unit=None, field_type=TEXT, choices=(), required=False,
       remember=None):
    """Terser spelling of a template entry - the operation and
    sort_order are filled in by :func:`template_fields`."""
    return dict(key=key, label=label, unit=unit, field_type=field_type,
                choices=tuple(choices), required=required, remember=remember)


# Yes/No rather than a bool for the fields Jordbruksverket's form asks to
# be answered in words ("ange Ja eller Nej"): an unticked checkbox can't
# tell "no" from "not answered yet", and on a journal that distinction is
# the difference between a documented decision and a gap.
_YES_NO = ('', 'Yes', 'No')

# 'generic' reproduces exactly the fields widgets/add_data_form.py has
# always shown, so a farm that never opens the journal-field settings
# sees no change at all. Every other template is opt-in.
_GENERIC = {
    'plant': [
        _f('variety', 'Variety'),
        _f('seed_rate', 'Seed rate', 'kg/ha', NUMBER),
        _f('spacing', 'Spacing', 'cm', NUMBER),
        _f('saw_depth', 'Sowing depth', 'cm', NUMBER)],
    'ferti': [
        _f('variety', 'Variety'),
        _f('nutrient', 'Nutrient', None, CHOICE, ('N', 'P', 'K', 'Mg', 'S', 'Na')),
        _f('rate', 'Rate', 'kg/ha', NUMBER),
        _f('saw_depth', 'Sowing depth', 'cm', NUMBER)],
    'spray': [
        _f('variety', 'Variety'),
        _f('rate', 'Rate', 'kg/ha', NUMBER),
        _f('wind_speed', 'Wind speed', 'm/s', NUMBER),
        _f('wind_dir', 'Wind direction', 'deg', NUMBER)],
    'harvest': [
        _f('yield', 'Yield', 'kg/ha', NUMBER),
        _f('total_yield', 'Total yield', 'tonnes', NUMBER)],
    'soil': [
        _f('clay', 'Clay', '%', NUMBER),
        _f('humus', 'Humus', '%', NUMBER),
        _f('ph', 'pH (0-14)', None, NUMBER),
        _f('rx', 'Average Rx', None, NUMBER)],
    'plowing': [_f('depth', 'Depth', 'cm', NUMBER)],
    'harrowing': [_f('depth', 'Depth', 'cm', NUMBER)],
}

# Jordbruksverket's documentation requirements for plant protection
# products as they stand from 2026, in the order of their own form, plus
# the three a sprayer operator needs and the regulation doesn't ask for
# (water volume, nozzle type, pressure - these sit under the form's
# optional "Ovrigt" row).
#
# ``variety`` and ``rate`` are reused rather than replaced: they are the
# existing spray.manual columns the report generator and the fertilizer
# /crop models already read, and for a spraying they have always meant
# "what was applied" and "how much" - here they just get the labels the
# regulation uses.
_SE_2026_SPRAY = [
    _f('purpose', 'Purpose of the treatment', None, CHOICE,
       ('', 'Weeds', 'Fungi', 'Insects', 'Growth regulation', 'Other'), required=True),
    _f('use_type', 'Type of use', None, CHOICE,
       ('', 'Field', 'Fruit growing', 'Golf course', 'Forest', 'Other'), required=True),
    # Place and treated area are filled in from the selected field
    # (:func:`autofill_values`), so a history list of them would only
    # repeat what the form already knows - unlike the operator, which is a
    # name and is usually the same one.
    _f('location', 'Place of application', None, TEXT, required=True,
       remember=False),
    _f('operator', 'Operator', None, TEXT, required=True),
    _f('eppo_code', 'Crop or situation (EPPO code)', None, TEXT, required=True),
    _f('bbch', 'Growth stage (BBCH)', None, TEXT, required=True),
    _f('variety', 'Plant protection product', None, TEXT, required=True),
    _f('reg_number', 'Registration number', None, TEXT, required=True),
    _f('rate', 'Dose', 'kg/ha or l/ha', NUMBER, required=True),
    _f('treated_area_ha', 'Treated area', 'ha', NUMBER, required=True,
       remember=False),
    _f('fixed_buffer_m', 'Fixed buffer zone', 'm', TEXT, required=True),
    _f('adapted_buffer_m', 'Adapted buffer zone', 'm', TEXT, required=True),
    _f('flowering_vegetation', 'Flowering vegetation', None, CHOICE, _YES_NO),
    _f('phi_days', 'Pre-harvest interval', 'days', NUMBER),
    _f('harvest_date', 'Harvest date', None, DATE),
    _f('spray_time', 'Time of day', None, TEXT),
    _f('water_volume_l_ha', 'Water volume', 'l/ha', NUMBER),
    _f('nozzle_type', 'Nozzle type', None, TEXT),
    _f('pressure_bar', 'Pressure', 'bar', NUMBER),
    _f('wind_speed', 'Wind speed', 'm/s', NUMBER),
    _f('wind_dir', 'Wind direction', 'deg', NUMBER),
    _f('temperature_c', 'Temperature', 'C', NUMBER),
]

# A template only has to say what it changes: template_fields falls back
# to 'generic' for any operation it doesn't list, so 'se_2026' is a
# spraying journal and leaves harvest, soil and the rest alone.
TEMPLATES = {
    'generic': _GENERIC,
    'se_2026': dict(_GENERIC, spray=_SE_2026_SPRAY),
}

# Shown in the settings dialog's template picker. Kept separate from
# TEMPLATES so the ordering is stable and the description is
# translatable at the call site.
TEMPLATE_LABELS = (
    ('generic', 'Generic (no national requirements)'),
    ('se_2026', 'Sweden - Jordbruksverket 2026'),
)


# Column names every manual row already uses for something else (see
# database_scripts/create_new_farm.py add_tables, and the INSERT in
# GeoDataFarm.save_add_data). A user-added field must not claim one of
# these as its key: a key that is column-backed writes straight to that
# column, so "Field" or "Other" would land the value in the row's own
# field/other column - or, for the ones the INSERT already lists, name
# the same column twice and fail the whole save.
RESERVED_KEYS = frozenset(
    ('field', 'crop', 'date_', 'date_text', 'other', 'table_', 'extra'))


def make_key(label: str, taken=()) -> str:
    """A storage key for a user-added field, derived from its label.

    Derived rather than typed because the label is what the user cares
    about; the key only has to be stable, unique within the operation,
    and safe to use both as a jsonb key and (for the built-in names) as
    an SQL identifier - hence ``check_text``, the same sanitiser the
    "Other" operation uses for its dynamic columns."""
    base = check_text(label).strip('_') or 'field'
    taken = set(taken) | RESERVED_KEYS
    key, n = base, 2
    while key in taken:
        key = f'{base}_{n}'
        n += 1
    return key


def template_fields(template: str, operation: str) -> list:
    """The :class:`JournalField` list a template defines for one
    operation, falling back to ``'generic'`` for an operation the
    template doesn't override (see :data:`TEMPLATES`)."""
    spec = TEMPLATES.get(template, _GENERIC).get(operation)
    if spec is None:
        spec = _GENERIC.get(operation, [])
    return [JournalField(operation=operation, sort_order=i * 10, builtin=True, **entry)
            for i, entry in enumerate(spec)]


# ---------------------------------------------------------------------
# Table creation / migration
# ---------------------------------------------------------------------
def ensure_tables(db) -> None:
    """Creates the journal-field and journal-settings tables if they
    don't exist yet - lazy, like every other table in this codebase (see
    support_scripts.crop_model_settings.ensure_settings_table).

    Cheap enough to call from every entry point that reads either table,
    which is what :func:`ensure_seeded` does."""
    db.execute_sql(pgsql.SQL(
        "CREATE TABLE IF NOT EXISTS public.{tbl} ("
        " operation text NOT NULL,"
        " field_key text NOT NULL,"
        " label text NOT NULL,"
        " unit text,"
        " field_type text NOT NULL DEFAULT 'text',"
        " choices text,"
        " required boolean NOT NULL DEFAULT false,"
        " sort_order integer NOT NULL DEFAULT 0,"
        " enabled boolean NOT NULL DEFAULT true,"
        " builtin boolean NOT NULL DEFAULT true,"
        " remember boolean NOT NULL DEFAULT true,"
        " PRIMARY KEY (operation, field_key))"
    ).format(tbl=pgsql.Identifier(_FIELDS_TABLE)))
    _ensure_field_column(db, 'remember', 'boolean NOT NULL DEFAULT true')
    db.execute_sql(pgsql.SQL(
        "CREATE TABLE IF NOT EXISTS public.{tbl} ("
        " setting_key text PRIMARY KEY,"
        " setting_value text)"
    ).format(tbl=pgsql.Identifier(_SETTINGS_TABLE)))


def _ensure_field_column(db, column: str, definition: str) -> None:
    """Adds one column to the journal-field table if a farm's copy was
    created before it existed - same check-then-``ALTER TABLE`` idiom as
    support_scripts.crop_model_settings._ensure_columns_exist.

    ``remember`` defaults to true rather than false so that a farm which
    already has a configured field list gets the history suggestions
    straight away instead of having to go and tick every box. It costs
    nothing on the types that ignore it - see
    :attr:`JournalField.suggestible`.
    """
    has_column = db_rows(db.execute_and_return(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'"
        " AND table_name = %s AND column_name = %s", params=(_FIELDS_TABLE, column)))
    if has_column:
        return
    db.execute_sql(pgsql.SQL("ALTER TABLE public.{tbl} ADD COLUMN IF NOT EXISTS {col} ").format(
        tbl=pgsql.Identifier(_FIELDS_TABLE), col=pgsql.Identifier(column))
        + pgsql.SQL(definition))


def ensure_extra_column(db, table: str) -> None:
    """Lazily adds the jsonb ``extra`` column to a manual table, for
    farms whose database was created before user-defined journal fields
    existed - same check-then-``ALTER TABLE`` idiom as
    database_scripts.db.ensure_ferti_nutrient_column, and safe to call
    every time a caller is about to read or write ``extra``.

    Rows written before the column existed simply have NULL there, which
    :func:`extra_of` reads as "no user-defined fields recorded", so
    every pre-existing row keeps behaving exactly as it did.

    Parameters
    ----------
    table: str
        Schema-qualified, e.g. ``'spray.manual'``.
    """
    schema, _, name = table.partition('.')
    has_column = db_rows(db.execute_and_return(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = %s"
        " AND table_name = %s AND column_name = 'extra'",
        params=(schema, name)))
    if has_column:
        return
    db.execute_sql(pgsql.SQL("ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS extra jsonb").format(
        tbl=pgsql.SQL('.').join(pgsql.Identifier(p) for p in (schema, name))))


def ensure_seeded(db, operation: str) -> None:
    """Makes sure ``operation`` has a field list, seeding it from the
    default template the first time.

    The "has it been seeded" marker is a :func:`get_setting` row rather
    than "does the table have rows for this operation": a user is
    allowed to disable or delete every field on an operation, and a
    row-count check would silently recreate the whole template the next
    time the form opened, undoing that."""
    ensure_tables(db)
    if get_setting(db, _template_key(operation)) is None:
        apply_template(db, operation, DEFAULT_TEMPLATE)


def _template_key(operation: str) -> str:
    return f'template:{operation}'


# ---------------------------------------------------------------------
# Settings key/value
# ---------------------------------------------------------------------
def get_setting(db, key: str, default=None):
    """Reads one journal-level setting (the active template per
    operation, the default operator name, ...)."""
    ensure_tables(db)
    rows = db_rows(db.execute_and_return(pgsql.SQL(
        "SELECT setting_value FROM public.{tbl} WHERE setting_key = %s"
    ).format(tbl=pgsql.Identifier(_SETTINGS_TABLE)), params=(key,)))
    return rows[0][0] if rows else default


def set_setting(db, key: str, value) -> None:
    """Writes one journal-level setting."""
    ensure_tables(db)
    db.execute_sql(pgsql.SQL(
        "INSERT INTO public.{tbl} (setting_key, setting_value) VALUES (%s, %s)"
        " ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value"
    ).format(tbl=pgsql.Identifier(_SETTINGS_TABLE)),
        params=(key, None if value is None else str(value)))


def active_template(db, operation: str) -> str:
    """Which template ``operation``'s field list was last reset from."""
    return get_setting(db, _template_key(operation), DEFAULT_TEMPLATE)


# ---------------------------------------------------------------------
# Reading / writing the field list
# ---------------------------------------------------------------------
def get_fields(db, operation: str, enabled_only: bool = True) -> list:
    """The configured :class:`JournalField` list for one operation, in
    display order.

    Parameters
    ----------
    enabled_only: bool
        ``True`` (the default) for the form and the report - they should
        only ever see fields the user kept. ``False`` for the settings
        dialog, which has to show the disabled ones in order to let them
        be switched back on.
    """
    ensure_seeded(db, operation)
    return _read_fields(db, operation, enabled_only)


def _read_fields(db, operation: str, enabled_only: bool = True) -> list:
    """The stored field list, without seeding first.

    Split out from :func:`get_fields` because :func:`apply_template` needs
    to know which fields the user added before it writes the template -
    and going through the seeding path to find that out would call back
    into apply_template on a farm that has never been seeded, which
    recurses until the stack runs out.
    """
    ensure_tables(db)
    sql = pgsql.SQL(
        "SELECT field_key, label, unit, field_type, choices, required,"
        " sort_order, enabled, builtin, remember FROM public.{tbl}"
        " WHERE operation = %s"
    ).format(tbl=pgsql.Identifier(_FIELDS_TABLE))
    if enabled_only:
        sql = sql + pgsql.SQL(" AND enabled")
    sql = sql + pgsql.SQL(" ORDER BY sort_order, field_key")
    fields = []
    for row in db_rows(db.execute_and_return(sql, params=(operation,))):
        (key, label, unit, field_type, choices, required, sort_order, enabled,
         builtin, remember) = row
        fields.append(JournalField(
            operation=operation, key=key, label=label, unit=unit,
            field_type=field_type, choices=_split_choices(choices),
            required=required, sort_order=sort_order, enabled=enabled,
            builtin=builtin, remember=remember))
    return fields


def _split_choices(choices) -> tuple:
    """Choices are stored newline-separated; an entry may legitimately be
    the empty string (that is how a CHOICE field offers "not answered" -
    see :data:`_YES_NO`), so the split must not filter blanks out."""
    if not choices:
        return ()
    return tuple(choices.split('\n'))


def _join_choices(choices) -> "str | None":
    return '\n'.join(choices) if choices else None


def save_fields(db, operation: str, fields) -> None:
    """Replaces ``operation``'s whole field list with ``fields``.

    Whole-list rather than per-row because that is what the settings
    dialog produces (reorder and delete are as much a part of an edit as
    changing a label), and doing it in one delete-then-insert keeps the
    stored sort_order in step with the order the user actually sees."""
    ensure_tables(db)
    db.execute_sql(pgsql.SQL("DELETE FROM public.{tbl} WHERE operation = %s").format(
        tbl=pgsql.Identifier(_FIELDS_TABLE)), params=(operation,))
    for i, field in enumerate(fields):
        db.execute_sql(pgsql.SQL(
            "INSERT INTO public.{tbl} (operation, field_key, label, unit, field_type,"
            " choices, required, sort_order, enabled, builtin, remember)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ).format(tbl=pgsql.Identifier(_FIELDS_TABLE)), params=(
            operation, field.key, field.label, field.unit, field.field_type,
            _join_choices(field.choices), field.required, i * 10,
            field.enabled, field.builtin, field.remember))


def apply_template(db, operation: str, template: str) -> list:
    """Resets ``operation``'s built-in fields to ``template``'s, keeping
    any the user added themselves.

    Custom fields survive a template change on purpose: a grower who
    added "nozzle type" because their sprayer needs it should not lose
    it by switching from the generic template to a national one - their
    fields are appended after the template's rather than merged into it,
    so the regulation's own ordering is preserved in the journal."""
    ensure_tables(db)
    custom = [f for f in _read_fields(db, operation, enabled_only=False) if not f.builtin]
    fields = template_fields(template, operation)
    known = {f.key for f in fields}
    fields.extend(f for f in custom if f.key not in known)
    save_fields(db, operation, fields)
    set_setting(db, _template_key(operation), template)
    return fields


# ---------------------------------------------------------------------
# Reading / writing a row's values
# ---------------------------------------------------------------------
def split_values(fields, values) -> tuple:
    """Splits form values into the real columns and the jsonb ``extra``
    payload - see the module docstring for why storage is split.

    Parameters
    ----------
    fields: list of JournalField
    values: dict
        keyed by field key, as produced by
        widgets.add_data_form.AddDataForm.values.

    Returns
    -------
    tuple of (dict, dict)
        ``(column_values, extra_values)``. Empty values are dropped from
        ``extra`` rather than stored as nulls, so a field the user left
        blank is simply absent - see :func:`extra_of`.
    """
    columns, extra = {}, {}
    for field in fields:
        value = values.get(field.key)
        if field.storage == 'column':
            columns[field.key] = value if value not in ('', None) else None
        elif value not in ('', None):
            extra[field.key] = value
    return columns, extra


def missing_required(fields, values) -> list:
    """The labels of every required field left blank, for the save path
    to name in its warning. Empty list means the row can be saved."""
    return [f.translated_label() for f in fields
            if f.required and values.get(f.key) in ('', None)]


def extra_of(row_value) -> dict:
    """Normalises a row's ``extra`` column to a dict.

    psycopg2 already decodes jsonb to a dict, but the column is NULL for
    every row written before :func:`ensure_extra_column` ran, and a
    caller iterating that would fail far from the cause - the same trap
    :func:`support_scripts.db_rows` exists to cover."""
    return row_value if isinstance(row_value, dict) else {}


def value_of(field, row_columns, extra) -> str:
    """One field's value for display, from wherever that field is
    stored.

    Parameters
    ----------
    field: JournalField
    row_columns: dict
        the manual row's real columns, keyed by column name.
    extra: dict
        the same row's decoded ``extra`` payload.
    """
    if field.storage == 'column':
        value = row_columns.get(field.key)
    else:
        value = extra.get(field.key)
    return '' if value is None else str(value)


def json_param(extra):
    """Wraps an ``extra`` dict for a jsonb placeholder. ``None`` for an
    empty payload, so a row with nothing user-defined stores NULL rather
    than an empty object and reads back the same as every pre-migration
    row."""
    return Json(extra) if extra else None


# ---------------------------------------------------------------------
# What was entered here before
# ---------------------------------------------------------------------
# How many past rows to look back over, and how many distinct values to
# offer per field. The window is generous because a farm records maybe a
# few dozen sprayings a season and the useful answer is "what do I
# normally put here", not "what did I put here last week"; the per-field
# cap is small because a drop-down stops being a shortcut once it needs
# scrolling.
SUGGESTION_ROWS = 300
SUGGESTIONS_PER_FIELD = 12


def recent_values(db, operation: str, fields, rows: int = SUGGESTION_ROWS,
                  per_field: int = SUGGESTIONS_PER_FIELD) -> dict:
    """What has been entered in each field before, most recent first.

    Read in one query over the operation's last ``rows`` rows rather than
    a ``SELECT DISTINCT`` per field: a configured journal runs to twenty
    fields, and twenty round trips every time the form opens is a visible
    pause for a list that is only a convenience. Three hundred rows of a
    manual table is nothing to fetch and the grouping is trivial in
    Python.

    Only fields that ask for it are included
    (:attr:`JournalField.suggestible`), so a date or a fixed choice list
    never appears here.

    Parameters
    ----------
    db: DB
    operation: str
    fields: list of JournalField
    rows: int
        How far back to look.
    per_field: int
        Most values to return for any one field.

    Returns
    -------
    dict
        ``{field_key: [value, ...]}``, only for fields that have history.
        A field nobody has filled in yet is absent rather than empty.
    """
    table = MANUAL_TABLES.get(operation)
    wanted = [f for f in fields if f.suggestible]
    if table is None or not wanted:
        return {}
    ensure_extra_column(db, table)
    column_keys = [f.key for f in wanted if f.storage == 'column']
    needs_extra = any(f.storage == 'extra' for f in wanted)
    select = [pgsql.SQL("extra")] if needs_extra else [pgsql.SQL("NULL")]
    select.extend(pgsql.Identifier(k) for k in column_keys)
    sql = (pgsql.SQL("SELECT ") + pgsql.SQL(', ').join(select)
           + pgsql.SQL(" FROM {tbl} ORDER BY date_ DESC NULLS LAST LIMIT %s").format(
               tbl=pgsql.SQL('.').join(pgsql.Identifier(p) for p in table.split('.'))))
    found = {}
    for row in db_rows(db.execute_and_return(sql, params=(rows,))):
        extra = extra_of(row[0])
        row_columns = dict(zip(column_keys, row[1:]))
        for field in wanted:
            value = value_of(field, row_columns, extra).strip()
            if not value:
                continue
            seen = found.setdefault(field.key, [])
            # Ordered by recency and de-duplicated in one pass: the rows
            # arrive newest first, so the first time a value shows up is
            # the last time it was used.
            if value not in seen and len(seen) < per_field:
                seen.append(value)
    return found


# ---------------------------------------------------------------------
# Values that shouldn't be typed by hand
# ---------------------------------------------------------------------
# Journal keys this module can fill in by itself, so the user isn't
# retyping something the database already knows. Jordbruksverket
# requires "place of application" and "size of the treated area" on
# every spraying; both follow from the field that was already selected
# on the form, and asking a grower to look them up would make an
# otherwise reasonable requirement feel like paperwork for its own sake.
AUTOFILL_KEYS = ('location', 'treated_area_ha', 'operator')

# Where the default operator name is kept (settable in the journal-field
# settings dialog) - the sprayer operator is the same person on most
# farms most days, so it is a farm setting with a per-row override
# rather than a field to retype every time.
DEFAULT_OPERATOR_KEY = 'default_operator'


def autofill_values(db, operation: str, field_name: "str | None") -> dict:
    """Values for :data:`AUTOFILL_KEYS` that can be derived from the
    selected field and the farm settings.

    Only keys the caller can actually use are returned; the caller is
    expected to fill *empty* widgets only, so a value the user typed is
    never overwritten (see GeoDataFarm._autofill_add_data_form).
    """
    values = {}
    operator = get_setting(db, DEFAULT_OPERATOR_KEY)
    if operator:
        values['operator'] = operator
    if not field_name:
        return values
    values['location'] = field_name
    area = db_rows(db.execute_and_return(
        "SELECT round((st_area(polygon::geography) / 10000)::numeric, 2)"
        " FROM fields WHERE field_name = %s", params=(field_name,)))
    if area and area[0][0] is not None:
        values['treated_area_ha'] = str(area[0][0])
    return values
