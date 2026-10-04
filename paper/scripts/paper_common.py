"""Shared helpers for the paper scripts: repository import path, farm
connection, anonymisation and file locations.

Every script here must be launched through ``run_in_qgis_env.bat`` because
the plugin's support modules import ``qgis.PyQt`` at package level.
"""
import argparse
import hashlib
import json
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PAPER_DIR = os.path.dirname(SCRIPTS_DIR)
REPO_DIR = os.path.dirname(PAPER_DIR)
REPO_PARENT = os.path.dirname(REPO_DIR)
PACKAGE_NAME = os.path.basename(REPO_DIR)  # 'geodatafarm3'
DATA_DIR = os.path.join(PAPER_DIR, 'data')
FIGURES_DIR = os.path.join(PAPER_DIR, 'figures')
# Field-name mapping lives outside data/ so data/ can be shared while the
# mapping stays private.
MAPPING_FILE = os.path.join(PAPER_DIR, 'private_field_mapping.json')

if REPO_PARENT not in sys.path:
    sys.path.insert(0, REPO_PARENT)


def import_plugin_module(dotted):
    """Import ``<package>.<dotted>`` so the plugin's relative imports work."""
    import importlib
    return importlib.import_module('{}.{}'.format(PACKAGE_NAME, dotted))


def add_farm_arguments(parser):
    parser.add_argument('--farm', required=True, help='farm (database) name')
    parser.add_argument('--user', required=True, help='farm user name')
    parser.add_argument('--password', default=None,
                        help='plain-text farm password; prefer GDF_PASSWORD env var')
    parser.add_argument('--farm-id', default='farm01',
                        help='anonymised farm label used in the exports')
    parser.add_argument('--out', default=DATA_DIR, help='output directory')


def resolve_password(args):
    password = args.password or os.environ.get('GDF_PASSWORD')
    if not password:
        raise SystemExit('Give the farm password with --password or GDF_PASSWORD.')
    # create_new_farm._connect_to_db() stores the sha256 hex digest as the
    # database password, so the same transformation is applied here.
    return hashlib.sha256(password.encode()).hexdigest()


def start_qgis():
    """A headless QgsApplication; QT_QPA_PLATFORM=offscreen is set by the bat."""
    from qgis.core import QgsApplication
    app = QgsApplication([], False)
    app.initQgis()
    return app


def connect_db(args):
    DB = import_plugin_module('database_scripts.db').DB
    db = DB(dbname=args.farm, dbuser=args.user, dbpass=resolve_password(args),
            test_mode=True)
    if not db.set_conn():
        raise SystemExit('Could not connect to farm {}.'.format(args.farm))
    return db


class Anonymiser:
    """Stable field-name -> F01, F02 ... mapping, persisted privately."""

    def __init__(self, farm_id):
        self.farm_id = farm_id
        self.mapping = {}
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, encoding='utf-8') as handle:
                self.mapping = json.load(handle)
        self.mapping.setdefault(farm_id, {})

    def field_id(self, field_name):
        farm_map = self.mapping[self.farm_id]
        if field_name not in farm_map:
            farm_map[field_name] = 'F{:02d}'.format(len(farm_map) + 1)
        return farm_map[field_name]

    def save(self):
        with open(MAPPING_FILE, 'w', encoding='utf-8') as handle:
            json.dump(self.mapping, handle, indent=2, ensure_ascii=False)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path
