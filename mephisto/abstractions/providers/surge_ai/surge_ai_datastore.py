#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
import sqlite3
import threading
from typing import Any
from typing import Dict
from typing import Optional

import surge

from mephisto.abstractions.databases.local_database import is_unique_failure
from mephisto.abstractions.providers.surge_ai.provider_type import PROVIDER_TYPE
from mephisto.abstractions.providers.surge_ai.surge_ai_utils import get_surge_ai_api_key
from mephisto.utils.logger_core import get_logger

CREATE_REQUESTERS_TABLE = """
CREATE TABLE IF NOT EXISTS requesters (
    requester_id TEXT PRIMARY KEY UNIQUE,
    is_registered BOOLEAN
);
"""

CREATE_UNITS_TABLE = """
CREATE TABLE IF NOT EXISTS units (
    unit_id TEXT PRIMARY KEY UNIQUE,
    is_expired BOOLEAN
);
"""

CREATE_WORKERS_TABLE = """
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY UNIQUE,
    is_blocked BOOLEAN
);
"""

CREATE_QUALIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS qualifications (
    qualification_name TEXT PRIMARY KEY UNIQUE,
    requester_id TEXT,
    surge_ai_qualification_name TEXT,
    surge_ai_qualification_id TEXT,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY UNIQUE,
    arn_id TEXT,
    project_id TEXT NOT NULL,
    project_config_path TEXT NOT NULL,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    frame_height INTEGER NOT NULL DEFAULT 650
);
"""

logger = get_logger(name=__name__)


class SurgeAIDatastore:
    def __init__(self, datastore_root: str):
        """Initialize local storage of active agents, connect to the database"""
        self.session_storage: Dict[str, surge] = {}
        self.agent_data: Dict[str, Dict[str, Any]] = {}
        self.table_access_condition = threading.Condition()
        self.conn: Dict[int, sqlite3.Connection] = {}
        self.db_path = os.path.join(datastore_root, f"{PROVIDER_TYPE}.db")
        self.init_tables()
        self.datastore_root = datastore_root

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a singular database connection to be shared amongst all
        calls for a given thread.
        """
        curr_thread = threading.get_ident()
        if curr_thread not in self.conn or self.conn[curr_thread] is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.conn[curr_thread] = conn
        return self.conn[curr_thread]

    def init_tables(self) -> None:
        """
        Run all the table creation SQL queries to ensure the expected tables exist
        """
        with self.table_access_condition:
            conn = self._get_connection()
            conn.execute("PRAGMA foreign_keys = 1")
            c = conn.cursor()
            c.execute(CREATE_REQUESTERS_TABLE)
            c.execute(CREATE_UNITS_TABLE)
            c.execute(CREATE_WORKERS_TABLE)
            c.execute(CREATE_QUALIFICATIONS_TABLE)
            c.execute(CREATE_RUNS_TABLE)
            conn.commit()

    def ensure_requester_exists(self, requester_id: str) -> None:
        """Create a record of this requester if it doesn't exist"""
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """INSERT OR IGNORE INTO requesters(
                    requester_id,
                    is_registered
                ) VALUES (?, ?);""",
                (requester_id, False),
            )
            conn.commit()
            return None

    def set_requester_registered(self, requester_id: str, val: bool) -> None:
        """Set the requester registration status for the given id"""
        self.ensure_requester_exists(requester_id)
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """UPDATE requesters
                SET is_registered = ?
                WHERE requester_id = ?
                """,
                (val, requester_id),
            )
            conn.commit()
            return None

    def get_requester_registered(self, requester_id: str) -> bool:
        """Get the registration status of a requester"""
        self.ensure_requester_exists(requester_id)
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT is_registered from requesters
                WHERE requester_id = ?
                """,
                (requester_id,),
            )
            results = c.fetchall()
            return bool(results[0]["is_registered"])

    def ensure_worker_exists(self, worker_id: str) -> None:
        """Create a record of this worker if it doesn't exist"""
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """INSERT OR IGNORE INTO workers(
                    worker_id,
                    is_blocked
                ) VALUES (?, ?);""",
                (worker_id, False),
            )
            conn.commit()
            return None

    def set_worker_blocked(self, worker_id: str, val: bool) -> None:
        """Set the worker registration status for the given id"""
        self.ensure_worker_exists(worker_id)
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """UPDATE workers
                SET is_blocked = ?
                WHERE worker_id = ?
                """,
                (val, worker_id),
            )
            conn.commit()
            return None

    def get_worker_blocked(self, worker_id: str) -> bool:
        """Get the registration status of a worker"""
        self.ensure_worker_exists(worker_id)
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT is_blocked from workers
                WHERE worker_id = ?
                """,
                (worker_id,),
            )
            results = c.fetchall()
            return bool(results[0]["is_blocked"])

    def ensure_unit_exists(self, unit_id: str) -> None:
        """Create a record of this unit if it doesn't exist"""
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """INSERT OR IGNORE INTO units(
                    unit_id,
                    is_expired
                ) VALUES (?, ?);""",
                (unit_id, False),
            )
            conn.commit()
            return None

    def set_unit_expired(self, unit_id: str, val: bool) -> None:
        """Set the unit registration status for the given id"""
        self.ensure_unit_exists(unit_id)
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """UPDATE units
                SET is_expired = ?
                WHERE unit_id = ?
                """,
                (val, unit_id),
            )
            conn.commit()
            return None

    def get_unit_expired(self, unit_id: str) -> bool:
        """Get the registration status of a unit"""
        self.ensure_unit_exists(unit_id)
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT is_expired from units
                WHERE unit_id = ?
                """,
                (unit_id,),
            )
            results = c.fetchall()
            return bool(results[0]["is_expired"])

    def get_session_for_requester(self, requester_name: str) -> surge:
        """
        Either create a new session for the given requester or return
        the existing one if it has already been created
        """
        if requester_name not in self.session_storage:
            session = surge
            session.api_key = os.environ.get('SURGE_API_KEY', None) or get_surge_ai_api_key()
            self.session_storage[requester_name] = session

        return self.session_storage[requester_name]

    def get_client_for_requester(self, requester_name: str) -> Any:
        """
        Return the client for the given requester, which should allow
        direct calls to the Surge AI surface
        """
        return self.get_session_for_requester(requester_name)

    def get_qualification_mapping(self, qualification_name: str) -> Optional[sqlite3.Row]:
        """
        Get the mapping between Mephisto qualifications and Surge AI qualifications
        (Surger Teams https://app.surgehq.ai/docs/api#surger-teams)
        """
        with self.table_access_condition:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT * from qualifications
                WHERE qualification_name = ?
                """,
                (qualification_name,),
            )
            results = c.fetchall()
            if len(results) == 0:
                return None
            return results[0]

    def create_qualification_mapping(
        self,
        qualification_name: str,
        requester_id: str,
        surge_ai_qualification_name: str,
        surge_ai_qualification_id: str,
    ) -> None:
        """
        Create a mapping between mephisto qualification name and Surge AI
        qualification details in the local datastore.

        Repeat entries with the same `qualification_name` will be idempotent
        """
        try:
            with self.table_access_condition, self._get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    """
                    INSERT INTO qualifications(
                        qualification_name,
                        requester_id,
                        surge_ai_qualification_name,
                        surge_ai_qualification_id
                    ) VALUES (?, ?, ?, ?);
                    """,
                    (
                        qualification_name,
                        requester_id,
                        surge_ai_qualification_name,
                        surge_ai_qualification_id,
                    ),
                )
                return None

        except sqlite3.IntegrityError as e:
            if is_unique_failure(e):
                # Ignore attempt to add another mapping for an existing key
                qual = self.get_qualification_mapping(qualification_name)

                logger.debug(
                    f'Multiple Surge AI mapping creations for qualification {qualification_name}. '
                    f'Found existing one: {qual}. '
                )
                assert (qual is not None), 'Cannot be none given is_unique_failure on insert'

                cur_requester_id = qual['requester_id']
                cur_surge_ai_qualification_name = qual['surge_ai_qualification_name']

                if cur_requester_id != requester_id:
                    logger.warning(
                        f'Surge AI Qualification mapping create for {qualification_name} '
                        f'under requester {requester_id}, already exists under {cur_requester_id}.'
                    )

                if cur_surge_ai_qualification_name != surge_ai_qualification_name:
                    logger.warning(
                        f'Surge AI Qualification mapping create for {qualification_name} '
                        f'with Surge AI name {surge_ai_qualification_name}, '
                        f'already exists under {cur_surge_ai_qualification_name}.'
                    )

                return None
            else:
                raise e

    def register_run(
        self,
        run_id: str,
        project_id: str,
        project_config_path: str,
        frame_height: int = 0,
    ) -> None:
        """Register a new task run in the mturk table"""
        with self.table_access_condition, self._get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO runs(
                    run_id,
                    arn_id,
                    project_id,
                    project_config_path,
                    frame_height
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (run_id, "unused", project_id, project_config_path, frame_height),
            )
