import os
import sqlite3
import json
import logging
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Basic logging configuration for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("history_manager")

class ActionType(Enum):
    """Defines categories for recorded actions."""
    PKGBUILD_BUILD = "PKGBUILD Build"
    PACKAGE_INSTALL = "Package Install"
    PACKAGE_UNINSTALL = "Package Uninstall"
    PATCH_APPLY = "Patch Apply"
    COMMAND_EXECUTION = "Command Execution"
    SECURITY_ALERT = "Security Alert"
    RISK_IGNORED = "Risk Ignored"
    UI_INTERACTION = "UI Interaction"
    SYSTEM_UPDATE = "System Update"
    CACHE_CLEAN = "Cache Clean"
    UPSTREAM_CHECK = "Upstream Check"
    OTHER = "Other"

class ActionStatus(Enum):
    """Defines the outcome status of an action."""
    SUCCESS = "Success"
    FAILED = "Failed"
    WARNING = "Warning"
    INFO = "Info"
    CANCELED = "Canceled"
    UNDONE = "Undone" # For conceptual undo

@dataclass
class HistoryEntry:
    """Represents a single entry in the action history."""
    id: Optional[int]
    timestamp: datetime
    action_type: ActionType
    summary: str
    status: ActionStatus
    details: Dict[str, Any] = field(default_factory=dict)
    is_undoable: bool = False # Flag for potential undo, with caveats
    related_pkg: Optional[str] = None # Package name related to the action
    user_initiated: bool = True # True if user explicitly triggered, False for auto-checks

class HistoryManager:
    """
    Manages the persistence, retrieval, and conceptual undo of application actions.
    Uses SQLite for efficient local storage.
    """

    DB_NAME = "history.db"
    TABLE_NAME = "actions"
    MAX_UNDO_HOURS = 24

    def __init__(self, db_dir: Optional[str] = None):
        self.db_path = self._get_db_path(db_dir)
        self._initialize_db()
        logger.info(f"HistoryManager initialized. DB Path: {self.db_path}")

    def _get_db_path(self, db_dir: Optional[str]) -> str:
        """Determines the path for the SQLite database."""
        if db_dir:
            if not os.path.isdir(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            return os.path.join(db_dir, self.DB_NAME)

        # Default to ~/.local/share/paru-gui for user data
        xdg_data_home = os.environ.get('XDG_DATA_HOME')
        if xdg_data_home:
            app_data_dir = os.path.join(xdg_data_home, "paru-gui")
        else:
            app_data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "paru-gui")

        os.makedirs(app_data_dir, exist_ok=True)
        return os.path.join(app_data_dir, self.DB_NAME)

    def _initialize_db(self):
        """Connects to the database and creates the actions table if it doesn't exist."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    is_undoable INTEGER NOT NULL DEFAULT 0,
                    related_pkg TEXT,
                    user_initiated INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def add_action(self, action: HistoryEntry) -> Optional[int]:
        """
        Adds a new action entry to the history database.

        Args:
            action: A HistoryEntry object containing details of the action.

        Returns:
            The ID of the newly added entry, or None if an error occurred.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"""
                INSERT INTO {self.TABLE_NAME}
                (timestamp, action_type, summary, status, details, is_undoable, related_pkg, user_initiated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.timestamp.isoformat(),
                action.action_type.value,
                action.summary,
                action.status.value,
                json.dumps(action.details), # Store details as JSON string
                1 if action.is_undoable else 0,
                action.related_pkg,
                1 if action.user_initiated else 0
            ))
            conn.commit()
            action_id = cursor.lastrowid
            logger.debug(f"Action '{action.summary}' added with ID: {action_id}")
            return action_id
        except sqlite3.Error as e:
            logger.error(f"Error adding action '{action.summary}' to history: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_history(self,
                    limit: int = 100,
                    offset: int = 0,
                    action_type: Optional[ActionType] = None,
                    related_pkg: Optional[str] = None,
                    min_timestamp: Optional[datetime] = None,
                    status: Optional[ActionStatus] = None,
                    user_initiated: Optional[bool] = None
                    ) -> List[HistoryEntry]:
        """
        Retrieves action history entries from the database.

        Args:
            limit: Maximum number of entries to retrieve.
            offset: Number of entries to skip (for pagination).
            action_type: Filter by specific action type.
            related_pkg: Filter by package name.
            min_timestamp: Only retrieve actions after this timestamp.
            status: Filter by action status.
            user_initiated: Filter by whether the action was user-initiated.

        Returns:
            A list of HistoryEntry objects, ordered by timestamp descending.
        """
        conn = None
        entries: List[HistoryEntry] = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = f"SELECT id, timestamp, action_type, summary, status, details, is_undoable, related_pkg, user_initiated FROM {self.TABLE_NAME} WHERE 1=1"
            params: List[Any] = []

            if action_type:
                query += " AND action_type = ?"
                params.append(action_type.value)
            if related_pkg:
                query += " AND related_pkg LIKE ?" # Use LIKE for partial matching
                params.append(f"%{related_pkg}%")
            if min_timestamp:
                query += " AND timestamp >= ?"
                params.append(min_timestamp.isoformat())
            if status:
                query += " AND status = ?"
                params.append(status.value)
            if user_initiated is not None:
                query += " AND user_initiated = ?"
                params.append(1 if user_initiated else 0)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                entries.append(HistoryEntry(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    action_type=ActionType(row[2]),
                    summary=row[3],
                    status=ActionStatus(row[4]),
                    details=json.loads(row[5]) if row[5] else {},
                    is_undoable=bool(row[6]),
                    related_pkg=row[7],
                    user_initiated=bool(row[8])
                ))
        except sqlite3.Error as e:
            logger.error(f"Error retrieving history: {e}")
        finally:
            if conn:
                conn.close()
        return entries

    def get_undoable_actions(self) -> List[HistoryEntry]:
        """
        Retrieves actions marked as undoable within the last MAX_UNDO_HOURS.
        These actions are typically non-destructive UI changes or temporary operations.

        Returns:
            A list of HistoryEntry objects for potentially undoable actions.
        """
        min_timestamp = datetime.utcnow() - timedelta(hours=self.MAX_UNDO_HOURS)
        return self.get_history(
            min_timestamp=min_timestamp,
            is_undoable=True,
            status=ActionStatus.SUCCESS # Only show successful, non-undone actions
        )

    def undo_action(self, action_id: int) -> bool:
        """
        Attempts to "undo" a specific action by marking its status as UNDONE.
        NOTE: This is a conceptual undo within the history log. It does NOT
        revert actual system changes. Real system rollbacks are complex and
        often require system snapshots or specific package manager commands.

        Args:
            action_id: The ID of the action to mark as undone.

        Returns:
            True if the action was marked as UNDONE, False otherwise.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # First, check if the action is actually undoable and within time limit
            cursor.execute(f"SELECT is_undoable, timestamp, status FROM {self.TABLE_NAME} WHERE id = ?", (action_id,))
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Action with ID {action_id} not found.")
                return False

            is_undoable_db, timestamp_str, status_db = row
            if not is_undoable_db:
                logger.warning(f"Action with ID {action_id} is not marked as 'is_undoable'. Cannot proceed with conceptual undo.")
                return False

            action_timestamp = datetime.fromisoformat(timestamp_str)
            if datetime.utcnow() - action_timestamp > timedelta(hours=self.MAX_UNDO_HOURS):
                logger.warning(f"Action with ID {action_id} is outside the {self.MAX_UNDO_HOURS}-hour undo window.")
                return False

            if status_db == ActionStatus.UNDONE.value:
                logger.info(f"Action with ID {action_id} is already marked as UNDONE.")
                return True # Already undone, so consider it successful

            cursor.execute(f"UPDATE {self.TABLE_NAME} SET status = ? WHERE id = ?", (ActionStatus.UNDONE.value, action_id))
            conn.commit()
            logger.info(f"Action ID {action_id} marked as UNDONE (conceptual rollback).")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error marking action ID {action_id} as UNDONE: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def export_history_to_string(self,
                                 limit: int = 500,
                                 offset: int = 0,
                                 format_json: bool = False
                                 ) -> str:
        """
        Exports history entries to a human-readable string.

        Args:
            limit: Maximum number of entries.
            offset: Offset for pagination.
            format_json: If True, exports full JSON for each entry; otherwise, a summary.

        Returns:
            A string containing the formatted history.
        """
        entries = self.get_history(limit=limit, offset=offset)
        if not entries:
            return "No history available."

        output_lines: List[str] = [f"--- History Export ({datetime.utcnow().isoformat()}) ---"]
        for entry in entries:
            if format_json:
                # Use default=str to handle datetime objects correctly during JSON serialization
                output_lines.append(json.dumps(entry.__dict__, default=str, indent=2))
            else:
                output_lines.append(f"[{entry.timestamp.isoformat()}] [{entry.action_type.value}] {entry.summary} (Status: {entry.status.value})")
                if entry.related_pkg:
                    output_lines.append(f"  Package: {entry.related_pkg}")
                if entry.details:
                    # Only show key details, not entire JSON unless format_json is true
                    detail_summary = ", ".join([f"{k}: {str(v)[:50]}" for k, v in entry.details.items() if k in ["command", "file", "error"]])
                    if detail_summary:
                        output_lines.append(f"  Details: {detail_summary}")
                if entry.is_undoable:
                    output_lines.append(f"  [Undoable: YES]")
            output_lines.append("-" * 60)
        return "\n".join(output_lines)

    def export_history_to_file(self,
                               file_path: str,
                               limit: int = 500,
                               offset: int = 0,
                               format_json: bool = False
                               ) -> bool:
        """
        Exports history entries to a specified file.

        Args:
            file_path: The full path to the output file.
            limit: Maximum number of entries.
            offset: Offset for pagination.
            format_json: If True, exports full JSON for each entry.

        Returns:
            True if export was successful, False otherwise.
        """
        try:
            history_string = self.export_history_to_string(limit=limit, offset=offset, format_json=format_json)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(history_string)
            logger.info(f"History exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting history to file {file_path}: {e}")
            return False

    def _clean_old_history(self, older_than_days: int = 90):
        """
        Removes history entries older than a specified number of days.
        This could be run periodically as a background task.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            cursor.execute(f"DELETE FROM {self.TABLE_NAME} WHERE timestamp < ?", (cutoff_date.isoformat(),))
            conn.commit()
            logger.info(f"Cleaned {cursor.rowcount} old history entries older than {older_than_days} days.")
        except sqlite3.Error as e:
            logger.error(f"Error cleaning old history: {e}")
        finally:
            if conn:
                conn.close()

# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG) # Enable DEBUG logs for testing

    # Use a temporary directory for testing
    test_db_dir = "/tmp/paru_gui_history_test"
    if not os.path.exists(test_db_dir):
        os.makedirs(test_db_dir)

    history_manager = HistoryManager(db_dir=test_db_dir)

    # --- Add some actions ---
    print("\n--- Adding Actions ---")
    action1_id = history_manager.add_action(HistoryEntry(
        id=None, timestamp=datetime.utcnow() - timedelta(days=1, hours=2),
        action_type=ActionType.PKGBUILD_BUILD, summary="Built 'firefox-git'",
        status=ActionStatus.SUCCESS, related_pkg="firefox-git",
        details={"path": "/home/user/aur/firefox-git", "command": "makepkg -s"}
    ))
    action2_id = history_manager.add_action(HistoryEntry(
        id=None, timestamp=datetime.utcnow() - timedelta(hours=1),
        action_type=ActionType.PACKAGE_INSTALL, summary="Installed 'nginx-mainline'",
        status=ActionStatus.SUCCESS, related_pkg="nginx-mainline",
        details={"file": "/tmp/nginx.pkg.tar.zst", "command": "pacman -U"},
        is_undoable=True # Potentially undoable (pacman -R)
    ))
    action3_id = history_manager.add_action(HistoryEntry(
        id=None, timestamp=datetime.utcnow() - timedelta(minutes=30),
        action_type=ActionType.SECURITY_ALERT, summary="High risk in 'malicious-pkg'",
        status=ActionStatus.WARNING, related_pkg="malicious-pkg",
        details={"risk_level": "CRITICAL", "line": 15, "description": "sudo rm -rf /"},
        is_undoable=False # Security alerts are not undoable operations
    ))
    action4_id = history_manager.add_action(HistoryEntry(
        id=None, timestamp=datetime.utcnow() - timedelta(minutes=10),
        action_type=ActionType.RISK_IGNORED, summary="Ignored risk for 'malicious-pkg'",
        status=ActionStatus.INFO, related_pkg="malicious-pkg",
        details={"original_alert_id": action3_id, "user_choice": "proceed"},
        is_undoable=True # User choice can be 'undone' to re-flag
    ))
    action5_id = history_manager.add_action(HistoryEntry(
        id=None, timestamp=datetime.utcnow() - timedelta(minutes=5),
        action_type=ActionType.SYSTEM_UPDATE, summary="Updated system packages",
        status=ActionStatus.FAILED,
        details={"command": "paru -Syu", "error": "Network error", "stderr": "curl: (6) Could not resolve host"},
        is_undoable=False # System updates are not undoable
    ))
    action6_id = history_manager.add_action(HistoryEntry(
        id=None, timestamp=datetime.utcnow() - timedelta(days=5), # Older entry
        action_type=ActionType.UI_INTERACTION, summary="Opened welcome screen",
        status=ActionStatus.INFO, user_initiated=False,
        is_undoable=True
    ))

    # --- Retrieve History ---
    print("\n--- Retrieving All History (last 5) ---")
    all_history = history_manager.get_history(limit=5)
    for entry in all_history:
        print(f"ID: {entry.id}, Time: {entry.timestamp}, Type: {entry.action_type.value}, Summary: {entry.summary}, Status: {entry.status.value}, Pkg: {entry.related_pkg}, Undoable: {entry.is_undoable}")

    # --- Retrieve Undoable Actions (last 24 hours) ---
    print(f"\n--- Retrieving Undoable Actions (last {history_manager.MAX_UNDO_HOURS} hours) ---")
    undoable_actions = history_manager.get_undoable_actions()
    if undoable_actions:
        for entry in undoable_actions:
            print(f"ID: {entry.id}, Time: {entry.timestamp}, Type: {entry.action_type.value}, Summary: {entry.summary}, Pkg: {entry.related_pkg}")
    else:
        print("No undoable actions found in the last 24 hours.")

    # --- Attempt to Undo an Action ---
    if action2_id:
        print(f"\n--- Attempting to UNDO Action ID {action2_id} (Install 'nginx-mainline') ---")
        if history_manager.undo_action(action2_id):
            print(f"Action {action2_id} conceptually undone.")
            # Verify status changed
            undone_entry = history_manager.get_history(limit=1, min_timestamp=datetime.fromtimestamp(0), related_pkg="nginx-mainline")
            if undone_entry and undone_entry[0].id == action2_id:
                print(f"Verified status is now: {undone_entry[0].status.value}")
        else:
            print(f"Failed to conceptually undo action {action2_id}.")

    # --- Export History ---
    print("\n--- Exporting History to String (summary) ---")
    summary_export = history_manager.export_history_to_string(limit=3)
    print(summary_export)

    print("\n--- Exporting History to String (JSON) ---")
    json_export = history_manager.export_history_to_string(limit=1, format_json=True)
    print(json_export)

    export_file_path = os.path.join(test_db_dir, "paru_gui_history.txt")
    if history_manager.export_history_to_file(export_file_path):
        print(f"\nHistory successfully exported to {export_file_path}")
    else:
        print("\nFailed to export history to file.")

    # --- Clean Old History ---
    print("\n--- Cleaning Old History (entries older than 3 days) ---")
    history_manager._clean_old_history(older_than_days=3)
    print("Old history cleaning attempted. Check logs for details.")

    # --- Final check after clean ---
    print("\n--- Final History Check ---")
    final_history = history_manager.get_history(limit=5)
    for entry in final_history:
        print(f"ID: {entry.id}, Time: {entry.timestamp}, Type: {entry.action_type.value}, Summary: {entry.summary}")


    # Clean up test database and directory
    try:
        os.remove(history_manager.db_path)
        if os.path.exists(export_file_path): # Check if it was created and exists before trying to remove
            os.remove(export_file_path)
        os.rmdir(test_db_dir)
        print(f"\nCleaned up test directory: {test_db_dir}")
    except OSError as e:
        print(f"Error cleaning up test directory: {e}")
