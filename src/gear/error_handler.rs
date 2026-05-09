use std::collections::HashMap;
use std::fs;
use std::path::Path;
use chrono::Utc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ErrorLevel {
    Critical,
    High,
    Medium,
    Low,
    Info,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ErrorCategory {
    System,
    Network,
    Parsing,
    Security,
    UserInput,
    FileIo,
    Dependencies,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorReport {
    pub timestamp: String,
    pub error_id: String,
    pub level: ErrorLevel,
    pub category: ErrorCategory,
    pub title: String,
    pub message: String,
    pub context: String,
    pub stack_trace: Option<String>,
    pub user_action: Option<String>,
    pub system_info: HashMap<String, String>,
    pub suggested_actions: Vec<String>,
}

#[derive(Debug)]
pub struct ErrorHandler {
    pub app_version: String,
    error_history: Vec<ErrorReport>,
    error_counts: HashMap<String, usize>,
    log_file_path: String,
}

impl ErrorHandler {
    pub fn new(app_version: &str) -> Self {
        let log_dir = dirs::cache_dir()
            .map(|p| p.join("paru-gui"))
            .unwrap_or_else(|| Path::new("/tmp/paru-gui").to_path_buf());
        
        if !log_dir.exists() {
            let _ = fs::create_dir_all(&log_dir);
        }

        let log_file_path = log_dir.join("error_logs.md").to_string_lossy().to_string();

        Self {
            app_version: app_version.to_string(),
            error_history: Vec::new(),
            error_counts: HashMap::new(),
            log_file_path,
        }
    }

    pub fn handle_error(&mut self, level: ErrorLevel, category: ErrorCategory, title: &str, message: &str, context: &str) -> String {
        let error_id = format!("{:x}", md5::compute(format!("{}{}{}", title, message, context)));
        let error_id = &error_id[..8];

        let report = ErrorReport {
            timestamp: Utc::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            error_id: error_id.to_string(),
            level,
            category,
            title: title.to_string(),
            message: message.to_string(),
            context: context.to_string(),
            stack_trace: None,
            user_action: None,
            system_info: HashMap::new(),
            suggested_actions: Vec::new(),
        };

        self.error_history.push(report.clone());
        *self.error_counts.entry(error_id.to_string()).or_insert(0) += 1;

        self._log_to_file(&report);
        
        error_id.to_string()
    }

    pub fn critical(&mut self, category: ErrorCategory, title: &str, message: &str, context: &str) -> String {
        self.handle_error(ErrorLevel::Critical, category, title, message, context)
    }

    pub fn high(&mut self, category: ErrorCategory, title: &str, message: &str, context: &str) -> String {
        self.handle_error(ErrorLevel::High, category, title, message, context)
    }

    pub fn medium(&mut self, category: ErrorCategory, title: &str, message: &str, context: &str) -> String {
        self.handle_error(ErrorLevel::Medium, category, title, message, context)
    }

    pub fn low(&mut self, category: ErrorCategory, title: &str, message: &str, context: &str) -> String {
        self.handle_error(ErrorLevel::Low, category, title, message, context)
    }

    pub fn info(&mut self, category: ErrorCategory, title: &str, message: &str, context: &str) -> String {
        self.handle_error(ErrorLevel::Info, category, title, message, context)
    }

    pub fn get_error_counts(&self) -> &HashMap<String, usize> {
        &self.error_counts
    }

    fn _log_to_file(&self, report: &ErrorReport) {
        let mut content = format!("# [{:?}] {}\n\n", report.level, report.title);
        content.push_str(&format!("**Error ID:** `{}`\n", report.error_id));
        content.push_str(&format!("**Message:** {}\n", report.message));
        content.push_str(&format!("**Context:** {}\n\n", report.context));
        
        if let Ok(mut file) = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_file_path) {
                use std::io::Write;
                let _ = writeln!(file, "{}", content);
                let _ = writeln!(file, "---\n");
            }
    }
}
