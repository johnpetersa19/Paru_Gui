use rusqlite::{params, Connection, Result};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::fs;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActionType {
    PkgbuildBuild,
    PackageInstall,
    PackageUninstall,
    PatchApply,
    CommandExecution,
    SecurityAlert,
    RiskIgnored,
    UiInteraction,
    SystemUpdate,
    CacheClean,
    UpstreamCheck,
    Other,
}

impl ActionType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::PkgbuildBuild => "PKGBUILD Build",
            Self::PackageInstall => "Package Install",
            Self::PackageUninstall => "Package Uninstall",
            Self::PatchApply => "Patch Apply",
            Self::CommandExecution => "Command Execution",
            Self::SecurityAlert => "Security Alert",
            Self::RiskIgnored => "Risk Ignored",
            Self::UiInteraction => "UI Interaction",
            Self::SystemUpdate => "System Update",
            Self::CacheClean => "Cache Clean",
            Self::UpstreamCheck => "Upstream Check",
            Self::Other => "Other",
        }
    }

    pub fn from_str(s: &str) -> Self {
        match s {
            "PKGBUILD Build" => Self::PkgbuildBuild,
            "Package Install" => Self::PackageInstall,
            "Package Uninstall" => Self::PackageUninstall,
            "Patch Apply" => Self::PatchApply,
            "Command Execution" => Self::CommandExecution,
            "Security Alert" => Self::SecurityAlert,
            "Risk Ignored" => Self::RiskIgnored,
            "UI Interaction" => Self::UiInteraction,
            "System Update" => Self::SystemUpdate,
            "Cache Clean" => Self::CacheClean,
            "Upstream Check" => Self::UpstreamCheck,
            _ => Self::Other,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActionStatus {
    Success,
    Failed,
    Warning,
    Info,
    Canceled,
    Undone,
}

impl ActionStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Success => "Success",
            Self::Failed => "Failed",
            Self::Warning => "Warning",
            Self::Info => "Info",
            Self::Canceled => "Canceled",
            Self::Undone => "Undone",
        }
    }

    pub fn from_str(s: &str) -> Self {
        match s {
            "Success" => Self::Success,
            "Failed" => Self::Failed,
            "Warning" => Self::Warning,
            "Info" => Self::Info,
            "Canceled" => Self::Canceled,
            "Undone" => Self::Undone,
            _ => Self::Info,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryEntry {
    pub id: Option<i64>,
    pub timestamp: DateTime<Utc>,
    pub action_type: ActionType,
    pub summary: String,
    pub status: ActionStatus,
    pub details: String, // JSON string
    pub is_undoable: bool,
    pub related_pkg: Option<String>,
    pub user_initiated: bool,
}

#[derive(Debug)]
pub struct HistoryManager {
    db_path: String,
}

impl HistoryManager {
    pub fn new(db_dir: Option<String>) -> Result<Self> {
        let path = if let Some(dir) = db_dir {
            Path::new(&dir).join("history.db")
        } else {
            let data_dir = dirs::data_dir()
                .map(|p| p.join("paru-gui"))
                .unwrap_or_else(|| Path::new("/tmp/paru-gui").to_path_buf());
            if !data_dir.exists() {
                let _ = fs::create_dir_all(&data_dir);
            }
            data_dir.join("history.db")
        };

        let manager = Self {
            db_path: path.to_string_lossy().to_string(),
        };
        manager._initialize_db()?;
        Ok(manager)
    }

    fn _initialize_db(&self) -> Result<()> {
        let conn = Connection::open(&self.db_path)?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                is_undoable INTEGER NOT NULL DEFAULT 0,
                related_pkg TEXT,
                user_initiated INTEGER NOT NULL DEFAULT 1
            )",
            [],
        )?;
        Ok(())
    }

    pub fn add_action(&self, entry: &HistoryEntry) -> Result<i64> {
        let conn = Connection::open(&self.db_path)?;
        conn.execute(
            "INSERT INTO actions (timestamp, action_type, summary, status, details, is_undoable, related_pkg, user_initiated)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            params![
                entry.timestamp.to_rfc3339(),
                entry.action_type.as_str(),
                entry.summary,
                entry.status.as_str(),
                entry.details,
                if entry.is_undoable { 1 } else { 0 },
                entry.related_pkg,
                if entry.user_initiated { 1 } else { 0 }
            ],
        )?;
        Ok(conn.last_insert_rowid())
    }

    pub fn get_history(&self, limit: i64, offset: i64) -> Result<Vec<HistoryEntry>> {
        let conn = Connection::open(&self.db_path)?;
        let mut stmt = conn.prepare(
            "SELECT id, timestamp, action_type, summary, status, details, is_undoable, related_pkg, user_initiated
             FROM actions ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )?;
        let rows = stmt.query_map(params![limit, offset], |row| {
            Ok(HistoryEntry {
                id: row.get(0)?,
                timestamp: DateTime::parse_from_rfc3339(&row.get::<_, String>(1)?)
                    .unwrap_or_else(|_| DateTime::parse_from_rfc3339("1970-01-01T00:00:00Z").unwrap())
                    .with_timezone(&Utc),
                action_type: ActionType::from_str(&row.get::<_, String>(2)?),
                summary: row.get(3)?,
                status: ActionStatus::from_str(&row.get::<_, String>(4)?),
                details: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
                is_undoable: row.get::<_, i32>(6)? != 0,
                related_pkg: row.get(7)?,
                user_initiated: row.get::<_, i32>(8)? != 0,
            })
        })?;

        let mut entries = Vec::new();
        for row in rows {
            entries.push(row?);
        }
        Ok(entries)
    }
}
