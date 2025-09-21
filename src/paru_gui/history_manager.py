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
            limit: Maximum number of entries to export.
            offset: Number of entries to skip.
            format_json: If True, returns JSON format; otherwise, a readable format.

        Returns:
            A string representation of the history.
        """
        entries = self.get_history(limit=limit, offset=offset)
        
        if format_json:
            # Convert to JSON-serializable format
            json_data = []
            for entry in entries:
                json_data.append({
                    "id": entry.id,
                    "timestamp": entry.timestamp.isoformat(),
                    "action_type": entry.action_type.value,
                    "summary": entry.summary,
                    "status": entry.status.value,
                    "details": entry.details,
                    "is_undoable": entry.is_undoable,
                    "related_pkg": entry.related_pkg,
                    "user_initiated": entry.user_initiated
                })
            return json.dumps(json_data, indent=2)
        else:
            # Human-readable format
            lines = ["Paru GUI Action History"]
            lines.append("=" * 30)
            lines.append("")
            
            for entry in entries:
                lines.append(f"[{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {entry.action_type.value}")
                lines.append(f"  Status: {entry.status.value}")
                lines.append(f"  Summary: {entry.summary}")
                if entry.related_pkg:
                    lines.append(f"  Package: {entry.related_pkg}")
                if entry.details:
                    lines.append(f"  Details: {json.dumps(entry.details)}")
                lines.append("  " + "-" * 40)
                lines.append("")
            
            return "\n".join(lines)

    def clear_old_entries(self, days_to_keep: int = 30) -> int:
        """
        Removes history entries older than the specified number of days.

        Args:
            days_to_keep: Number of days of history to retain.

        Returns:
            Number of entries deleted.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        conn = None
        deleted_count = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"DELETE FROM {self.TABLE_NAME} WHERE timestamp < ?", (cutoff_date.isoformat(),))
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Deleted {deleted_count} history entries older than {days_to_keep} days.")
        except sqlite3.Error as e:
            logger.error(f"Error clearing old entries: {e}")
        finally:
            if conn:
                conn.close()
                
        return deleted_count

    def get_statistics(self) -> Dict[str, Any]:
        """
        Returns statistics about the action history.

        Returns:
            A dictionary with various statistics.
        """
        conn = None
        stats = {
            "total_entries": 0,
            "entries_by_type": {},
            "entries_by_status": {},
            "recent_activity": 0,  # Last 24 hours
            "undoable_actions": 0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total entries
            cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME}")
            stats["total_entries"] = cursor.fetchone()[0]
            
            # Entries by type
            cursor.execute(f"SELECT action_type, COUNT(*) FROM {self.TABLE_NAME} GROUP BY action_type")
            for row in cursor.fetchall():
                stats["entries_by_type"][row[0]] = row[1]
            
            # Entries by status
            cursor.execute(f"SELECT status, COUNT(*) FROM {self.TABLE_NAME} GROUP BY status")
            for row in cursor.fetchall():
                stats["entries_by_status"][row[0]] = row[1]
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME} WHERE timestamp >= ?", (recent_cutoff.isoformat(),))
            stats["recent_activity"] = cursor.fetchone()[0]
            
            # Undoable actions
            cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME} WHERE is_undoable = 1")
            stats["undoable_actions"] = cursor.fetchone()[0]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting statistics: {e}")
        finally:
            if conn:
                conn.close()
                
        return stats
