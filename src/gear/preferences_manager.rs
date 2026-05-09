use gtk::gio;
use std::collections::HashMap;
use gtk::gio::prelude::*;
// use adw::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EditorChoice {
    #[serde(rename = "system_default")]
    SystemDefault,
    #[serde(rename = "gedit")]
    Gedit,
    #[serde(rename = "nano")]
    Nano,
    #[serde(rename = "vim")]
    Vim,
    #[serde(rename = "emacs")]
    Emacs,
    #[serde(rename = "code")]
    VsCode,
    #[serde(rename = "atom")]
    Atom,
    #[serde(rename = "subl")]
    Sublime,
    #[serde(rename = "custom")]
    Custom,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UpstreamFrequency {
    #[serde(rename = "never")]
    Never,
    #[serde(rename = "daily")]
    Daily,
    #[serde(rename = "weekly")]
    Weekly,
    #[serde(rename = "monthly")]
    Monthly,
    #[serde(rename = "on_startup")]
    OnStartup,
    #[serde(rename = "manual")]
    Manual,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AURConfidenceLevel {
    #[serde(rename = "paranoid")]
    Paranoid,
    #[serde(rename = "conservative")]
    Conservative,
    #[serde(rename = "balanced")]
    Balanced,
    #[serde(rename = "trusting")]
    Trusting,
    #[serde(rename = "permissive")]
    Permissive,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ThemeMode {
    #[serde(rename = "system")]
    System,
    #[serde(rename = "light")]
    Light,
    #[serde(rename = "dark")]
    Dark,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UpdateNotificationLevel {
    #[serde(rename = "none")]
    None,
    #[serde(rename = "critical")]
    Critical,
    #[serde(rename = "important")]
    Important,
    #[serde(rename = "all")]
    All,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LogLevel {
    #[serde(rename = "debug")]
    Debug,
    #[serde(rename = "info")]
    Info,
    #[serde(rename = "warning")]
    Warning,
    #[serde(rename = "error")]
    Error,
}

#[derive(Debug)]
pub struct PreferencesManager {
    settings: Option<gio::Settings>,
}

impl PreferencesManager {
    const SCHEMA_ID: &'static str = "org.gnome.paru-gui";

    pub fn new() -> Self {
        let settings = gio::Settings::new(Self::SCHEMA_ID);
        Self { settings: Some(settings) }
    }

    fn _get_string(&self, key: &str, default: &str) -> String {
        self.settings.as_ref()
            .map(|s| s.string(key).to_string())
            .unwrap_or_else(|| default.to_string())
    }

    fn _set_string(&self, key: &str, value: &str) -> bool {
        self.settings.as_ref()
            .map(|s| s.set_string(key, value).is_ok())
            .unwrap_or(false)
    }

    fn _get_boolean(&self, key: &str, default: bool) -> bool {
        self.settings.as_ref()
            .map(|s| s.boolean(key))
            .unwrap_or(default)
    }

    fn _set_boolean(&self, key: &str, value: bool) -> bool {
        self.settings.as_ref()
            .map(|s| s.set_boolean(key, value).is_ok())
            .unwrap_or(false)
    }

    fn _get_int(&self, key: &str, default: i32) -> i32 {
        self.settings.as_ref()
            .map(|s| s.int(key))
            .unwrap_or(default)
    }

    fn _set_int(&self, key: &str, value: i32) -> bool {
        self.settings.as_ref()
            .map(|s| s.set_int(key, value).is_ok())
            .unwrap_or(false)
    }

    fn _get_strv(&self, key: &str) -> Vec<String> {
        self.settings.as_ref()
            .map(|s| s.strv(key).iter().map(|s| s.to_string()).collect())
            .unwrap_or_default()
    }

    fn _set_strv(&self, key: &str, value: &[&str]) -> bool {
        self.settings.as_ref()
            .map(|s| s.set_strv(key, value).is_ok())
            .unwrap_or(false)
    }

    // Properties
    pub fn first_run(&self) -> bool { self._get_boolean("first-run", true) }
    pub fn set_first_run(&self, value: bool) { self._set_boolean("first-run", value); }

    pub fn simplified_mode(&self) -> bool { self._get_boolean("simplified-mode", true) }
    pub fn set_simplified_mode(&self, value: bool) { self._set_boolean("simplified-mode", value); }

    pub fn default_editor(&self) -> EditorChoice {
        match self._get_string("default-editor", "gedit").as_str() {
            "system_default" => EditorChoice::SystemDefault,
            "gedit" => EditorChoice::Gedit,
            "nano" => EditorChoice::Nano,
            "vim" => EditorChoice::Vim,
            "emacs" => EditorChoice::Emacs,
            "code" => EditorChoice::VsCode,
            "atom" => EditorChoice::Atom,
            "subl" => EditorChoice::Sublime,
            _ => EditorChoice::Custom,
        }
    }
    pub fn set_default_editor(&self, value: EditorChoice) {
        let val = match value {
            EditorChoice::SystemDefault => "system_default",
            EditorChoice::Gedit => "gedit",
            EditorChoice::Nano => "nano",
            EditorChoice::Vim => "vim",
            EditorChoice::Emacs => "emacs",
            EditorChoice::VsCode => "code",
            EditorChoice::Atom => "atom",
            EditorChoice::Sublime => "subl",
            EditorChoice::Custom => "custom",
        };
        self._set_string("default-editor", val);
    }

    pub fn window_width(&self) -> i32 { self._get_int("window-width", 1200) }
    pub fn set_window_width(&self, value: i32) { self._set_int("window-width", value); }

    pub fn window_height(&self) -> i32 { self._get_int("window-height", 800) }
    pub fn set_window_height(&self, value: i32) { self._set_int("window-height", value); }

    pub fn recent_directories(&self) -> Vec<String> { self._get_strv("recent-directories") }
    pub fn set_recent_directories(&self, value: &[&str]) { self._set_strv("recent-directories", value); }

    pub fn max_recent_directories(&self) -> i32 { self._get_int("max-recent-directories", 10) }
    pub fn set_max_recent_directories(&self, value: i32) { self._set_int("max-recent-directories", value); }

    pub fn upstream_check_frequency(&self) -> i32 { self._get_int("upstream-check-frequency", 24) }
    pub fn set_upstream_check_frequency(&self, value: i32) { self._set_int("upstream-check-frequency", value); }

    pub fn upstream_ignore_prerelease(&self) -> bool { self._get_boolean("upstream-ignore-prerelease", true) }
    pub fn set_upstream_ignore_prerelease(&self, value: bool) { self._set_boolean("upstream-ignore-prerelease", value); }

    pub fn upstream_notify_security_only(&self) -> bool { self._get_boolean("upstream-notify-security-only", false) }
    pub fn set_upstream_notify_security_only(&self, value: bool) { self._set_boolean("upstream-notify-security-only", value); }

    pub fn aur_show_trust_icons(&self) -> bool { self._get_boolean("aur-show-trust-icons", true) }
    pub fn set_aur_show_trust_icons(&self, value: bool) { self._set_boolean("aur-show-trust-icons", value); }

    pub fn aur_confidence_level(&self) -> AURConfidenceLevel {
        match self._get_string("aur-confidence-level", "balanced").as_str() {
            "paranoid" => AURConfidenceLevel::Paranoid,
            "conservative" => AURConfidenceLevel::Conservative,
            "balanced" => AURConfidenceLevel::Balanced,
            "trusting" => AURConfidenceLevel::Trusting,
            "permissive" => AURConfidenceLevel::Permissive,
            _ => AURConfidenceLevel::Balanced,
        }
    }
    pub fn set_aur_confidence_level(&self, value: AURConfidenceLevel) {
        let val = match value {
            AURConfidenceLevel::Paranoid => "paranoid",
            AURConfidenceLevel::Conservative => "conservative",
            AURConfidenceLevel::Balanced => "balanced",
            AURConfidenceLevel::Trusting => "trusting",
            AURConfidenceLevel::Permissive => "permissive",
        };
        self._set_string("aur-confidence-level", val);
    }

    pub fn developer_mode(&self) -> bool { self._get_boolean("developer-mode", false) }
    pub fn set_developer_mode(&self, value: bool) { self._set_boolean("developer-mode", value); }

    pub fn clean_after_build(&self) -> bool { self._get_boolean("clean-after-build", true) }
    pub fn set_clean_after_build(&self, value: bool) { self._set_boolean("clean-after-build", value); }

    pub fn enable_sandboxing(&self) -> bool { self._get_boolean("enable-sandboxing", true) }
    pub fn set_enable_sandboxing(&self, value: bool) { self._set_boolean("enable-sandboxing", value); }

    pub fn theme_mode(&self) -> ThemeMode {
        match self._get_string("theme-mode", "system").as_str() {
            "light" => ThemeMode::Light,
            "dark" => ThemeMode::Dark,
            _ => ThemeMode::System,
        }
    }
    pub fn set_theme_mode(&self, value: ThemeMode) {
        let val = match value {
            ThemeMode::System => "system",
            ThemeMode::Light => "light",
            ThemeMode::Dark => "dark",
        };
        self._set_string("theme-mode", val);
    }

    pub fn log_level(&self) -> LogLevel {
        match self._get_string("log-level", "info").as_str() {
            "debug" => LogLevel::Debug,
            "info" => LogLevel::Info,
            "warning" => LogLevel::Warning,
            "error" => LogLevel::Error,
            _ => LogLevel::Info,
        }
    }
    pub fn set_log_level(&self, value: LogLevel) {
        let val = match value {
            LogLevel::Debug => "debug",
            LogLevel::Info => "info",
            LogLevel::Warning => "warning",
            LogLevel::Error => "error",
        };
        self._set_string("log-level", val);
    }

    pub fn add_recent_directory(&self, directory: &str) {
        let mut recent = self.recent_directories();
        if let Some(pos) = recent.iter().position(|d| d == directory) {
            recent.remove(pos);
        }
        recent.insert(0, directory.to_string());
        let max = self.max_recent_directories() as usize;
        if recent.len() > max {
            recent.truncate(max);
        }
        let refs: Vec<&str> = recent.iter().map(|s| s.as_str()).collect();
        self.set_recent_directories(&refs);
    }

    pub fn clear_recent_directories(&self) {
        self.set_recent_directories(&[]);
    }

    pub fn get_editor_command(&self) -> String {
        let editor = self.default_editor();
        match editor {
            EditorChoice::SystemDefault => std::env::var("EDITOR").unwrap_or_else(|_| "gedit".to_string()),
            EditorChoice::Custom => self._get_string("custom-editor-command", "gedit"),
            EditorChoice::Gedit => "gedit".to_string(),
            EditorChoice::Nano => "nano".to_string(),
            EditorChoice::Vim => "vim".to_string(),
            EditorChoice::Emacs => "emacs".to_string(),
            EditorChoice::VsCode => "code".to_string(),
            EditorChoice::Atom => "atom".to_string(),
            EditorChoice::Sublime => "subl".to_string(),
        }
    }

    pub fn reset_to_defaults(&self) -> bool {
        /*
        if let Some(settings) = &self.settings {
            for key in settings.keys() {
                settings.reset(&key);
            }
            return true;
        }
        */
        false
    }

    pub fn validate_preferences(&self) -> HashMap<String, Vec<String>> {
        let mut errors = HashMap::new();

        if self.window_width() < 800 {
            errors.entry("window".to_string()).or_insert_with(Vec::new).push("Window width must be at least 800 pixels".to_string());
        }

        if self.window_height() < 600 {
            errors.entry("window".to_string()).or_insert_with(Vec::new).push("Window height must be at least 600 pixels".to_string());
        }

        if self.upstream_check_frequency() < 0 {
            errors.entry("upstream".to_string()).or_insert_with(Vec::new).push("Check frequency cannot be negative".to_string());
        }

        errors
    }

    pub fn apply_theme(&self) {
        let theme = self.theme_mode();
        if theme == ThemeMode::System { return; }

        let style_manager = adw::StyleManager::default();
        match theme {
            ThemeMode::Dark => style_manager.set_color_scheme(adw::ColorScheme::ForceDark),
            ThemeMode::Light => style_manager.set_color_scheme(adw::ColorScheme::ForceLight),
            _ => style_manager.set_color_scheme(adw::ColorScheme::Default),
        }
    }
}
