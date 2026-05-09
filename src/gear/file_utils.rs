use std::fs;
use std::path::Path;
use std::process::Command;
use std::collections::HashMap;
use std::sync::OnceLock;
use regex::Regex;
use serde::{Deserialize, Serialize};
use tempfile::TempDir;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PackageType {
    #[serde(rename = "binary")]
    Binary,
    #[serde(rename = "source")]
    Source,
    #[serde(rename = "split")]
    Split,
    #[serde(rename = "group")]
    Group,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SecurityLevel {
    #[serde(rename = "safe")]
    Safe,
    #[serde(rename = "caution")]
    Caution,
    #[serde(rename = "warning")]
    Warning,
    #[serde(rename = "danger")]
    Danger,
}

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct FileItem {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    pub file_type: String,
    pub size: u64,
    pub modified_time: f64,
}

impl FileItem {
    #[allow(dead_code)]
    pub fn get_icon_name(&self) -> String {
        if self.is_dir {
            return "folder-symbolic".to_string();
        }
        match self.file_type.as_str() {
            "PKGBUILD" => "text-x-script-symbolic".to_string(),
            "PACKAGE" => "package-x-generic-symbolic".to_string(),
            "PATCH" => "text-x-patch-symbolic".to_string(),
            _ => "text-x-generic-symbolic".to_string(),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct PKGBUILDInfo {
    pub pkgname: String,
    pub pkgver: String,
    pub pkgrel: String,
    pub pkgdesc: String,
    pub arch: Vec<String>,
    pub url: String,
    pub license: Vec<String>,
    pub depends: Vec<String>,
    pub makedepends: Vec<String>,
    pub optdepends: Vec<String>,
    pub provides: Vec<String>,
    pub conflicts: Vec<String>,
    pub replaces: Vec<String>,
    pub source: Vec<String>,
    pub sha256sums: Vec<String>,
    pub md5sums: Vec<String>,
    pub sha512sums: Vec<String>,
    pub backup: Vec<String>,
    pub options: Vec<String>,
    pub install: String,
    pub changelog: String,
    pub validpgpkeys: Vec<String>,
    pub epoch: String,
    pub groups: Vec<String>,
    pub has_build_function: bool,
    pub has_package_function: bool,
    pub has_prepare_function: bool,
    pub has_check_function: bool,
    pub is_valid: bool,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
    pub security_level: SecurityLevel,
    pub file_path: String,
}

impl Default for SecurityLevel {
    fn default() -> Self {
        SecurityLevel::Safe
    }
}

#[derive(Debug, Clone, Default)]
pub struct PackageInfo {
    pub pkgname: String,
    pub pkgbase: String,
    pub pkgver: String,
    pub pkgdesc: String,
    pub arch: String,
    pub url: String,
    pub license: Vec<String>,
    pub groups: Vec<String>,
    pub provides: Vec<String>,
    pub depends: Vec<String>,
    pub optdepends: Vec<String>,
    pub makedepends: Vec<String>,
    pub conflicts: Vec<String>,
    pub replaces: Vec<String>,
    pub backup: Vec<String>,
    pub packager: String,
    pub builddate: String,
    pub installdate: String,
    pub size: u64,
    pub reason: i32,
    pub validation: Vec<String>,
    pub files: Vec<String>,
    pub file_count: usize,
    pub compressed_size: u64,
    pub package_type: PackageType,
    pub is_valid: bool,
    pub errors: Vec<String>,
    pub file_path: String,
}

impl Default for PackageType {
    fn default() -> Self {
        PackageType::Binary
    }
}

#[derive(Debug, Default)]
pub struct FileUtils {
    pub supported_compressions: Vec<String>,
}

impl FileUtils {
    pub fn new() -> Self {
        Self {
            supported_compressions: vec![
                ".xz".to_string(),
                ".zst".to_string(),
                ".gz".to_string(),
                ".bz2".to_string(),
            ],
        }
    }

    pub fn analyze_pkgbuild(&self, pkgbuild_path: &str) -> PKGBUILDInfo {
        let mut info = PKGBUILDInfo {
            file_path: pkgbuild_path.to_string(),
            ..Default::default()
        };

        let path = Path::new(pkgbuild_path);
        if !path.exists() {
            info.errors.push("PKGBUILD file not found".to_string());
            return info;
        }

        let content = match fs::read_to_string(path) {
            Ok(c) => c,
            Err(e) => {
                info.errors.push(format!("Failed to read file: {}", e));
                return info;
            }
        };

        info = self._parse_pkgbuild_content(&content, info);
        info = self._validate_pkgbuild(info);
        // Security analysis should be handled by SecurityAnalyzer separately or 
        // through a coordinator to avoid logic duplication.

        info
    }

    fn _parse_pkgbuild_content(&self, content: &str, mut info: PKGBUILDInfo) -> PKGBUILDInfo {
        static SINGLE_PATTERNS: OnceLock<HashMap<&'static str, Regex>> = OnceLock::new();
        let single_patterns = SINGLE_PATTERNS.get_or_init(|| {
            let mut m = HashMap::new();
            let singles = [
                ("pkgname", r"(?m)^\s*pkgname=(.+?)$"),
                ("pkgver", r"(?m)^\s*pkgver=(.+?)$"),
                ("pkgrel", r"(?m)^\s*pkgrel=(.+?)$"),
                ("pkgdesc", r"(?m)^\s*pkgdesc=(.+?)$"),
                ("url", r"(?m)^\s*url=(.+?)$"),
                ("install", r"(?m)^\s*install=(.+?)$"),
                ("changelog", r"(?m)^\s*changelog=(.+?)$"),
                ("epoch", r"(?m)^\s*epoch=(.+?)$"),
                ("pkgbase", r"(?m)^\s*pkgbase=(.+?)$"),
            ];
            for (k, v) in singles {
                m.insert(k, Regex::new(v).unwrap());
            }
            m
        });

        for (field, re) in single_patterns {
            if let Some(caps) = re.captures(content) {
                let val = self._clean_quoted_string(&caps[1]);
                match *field {
                    "pkgname" => info.pkgname = val,
                    "pkgver" => info.pkgver = val,
                    "pkgrel" => info.pkgrel = val,
                    "pkgdesc" => info.pkgdesc = val,
                    "url" => info.url = val,
                    "install" => info.install = val,
                    "changelog" => info.changelog = val,
                    "epoch" => info.epoch = val,
                    _ => {}
                }
            }
        }

        static ARRAY_PATTERNS: OnceLock<HashMap<&'static str, Regex>> = OnceLock::new();
        let array_patterns = ARRAY_PATTERNS.get_or_init(|| {
            let mut m = HashMap::new();
            let arrays = [
                ("arch", r"(?s)arch=\((.*?)\)"),
                ("license", r"(?s)license=\((.*?)\)"),
                ("depends", r"(?s)depends=\((.*?)\)"),
                ("makedepends", r"(?s)makedepends=\((.*?)\)"),
                ("optdepends", r"(?s)optdepends=\((.*?)\)"),
                ("provides", r"(?s)provides=\((.*?)\)"),
                ("conflicts", r"(?s)conflicts=\((.*?)\)"),
                ("replaces", r"(?s)replaces=\((.*?)\)"),
                ("source", r"(?s)source=\((.*?)\)"),
                ("sha256sums", r"(?s)sha256sums=\((.*?)\)"),
                ("md5sums", r"(?s)md5sums=\((.*?)\)"),
                ("sha512sums", r"(?s)sha512sums=\((.*?)\)"),
                ("backup", r"(?s)backup=\((.*?)\)"),
                ("options", r"(?s)options=\((.*?)\)"),
                ("groups", r"(?s)groups=\((.*?)\)"),
                ("validpgpkeys", r"(?s)validpgpkeys=\((.*?)\)"),
            ];
            for (k, v) in arrays {
                m.insert(k, Regex::new(v).unwrap());
            }
            m
        });

        for (field, re) in array_patterns {
            if let Some(caps) = re.captures(content) {
                let items = self._parse_bash_array(&caps[1]);
                match *field {
                    "arch" => info.arch = items,
                    "license" => info.license = items,
                    "depends" => info.depends = items,
                    "makedepends" => info.makedepends = items,
                    "optdepends" => info.optdepends = items,
                    "provides" => info.provides = items,
                    "conflicts" => info.conflicts = items,
                    "replaces" => info.replaces = items,
                    "source" => info.source = items,
                    "sha256sums" => info.sha256sums = items,
                    "md5sums" => info.md5sums = items,
                    "sha512sums" => info.sha512sums = items,
                    "backup" => info.backup = items,
                    "options" => info.options = items,
                    "groups" => info.groups = items,
                    "validpgpkeys" => info.validpgpkeys = items,
                    _ => {}
                }
            }
        }

        static FUNC_PATTERNS: OnceLock<Vec<(&'static str, Regex)>> = OnceLock::new();
        let func_patterns = FUNC_PATTERNS.get_or_init(|| {
            vec![
                ("build", Regex::new(r"(?m)^build\s*\(\s*\)\s*\{").unwrap()),
                ("package", Regex::new(r"(?m)^package(?:_[\w]+)?\s*\(\s*\)\s*\{").unwrap()),
                ("prepare", Regex::new(r"(?m)^prepare\s*\(\s*\)\s*\{").unwrap()),
                ("check", Regex::new(r"(?m)^check\s*\(\s*\)\s*\{").unwrap()),
            ]
        });

        for (field, re) in func_patterns {
            let has_func = re.is_match(content);
            match *field {
                "build" => info.has_build_function = has_func,
                "package" => info.has_package_function = has_func,
                "prepare" => info.has_prepare_function = has_func,
                "check" => info.has_check_function = has_func,
                _ => {}
            }
        }

        info
    }

    fn _validate_pkgbuild(&self, mut info: PKGBUILDInfo) -> PKGBUILDInfo {
        if info.pkgname.is_empty() { info.errors.push("Missing required field: pkgname".to_string()); }
        if info.pkgver.is_empty() { info.errors.push("Missing required field: pkgver".to_string()); }
        if info.pkgrel.is_empty() { info.errors.push("Missing required field: pkgrel".to_string()); }

        if info.arch.is_empty() {
            info.warnings.push("No architecture specified".to_string());
        } else if !info.arch.contains(&"any".to_string()) && !info.arch.iter().any(|a| vec!["x86_64", "i686", "arm", "armv7h", "aarch64"].contains(&a.as_str())) {
            info.warnings.push("Unusual architecture specification".to_string());
        }

        if info.license.is_empty() {
            info.warnings.push("No license specified".to_string());
        }

        if !info.source.is_empty() && info.sha256sums.is_empty() && info.md5sums.is_empty() && info.sha512sums.is_empty() {
            info.warnings.push("Source files without checksums".to_string());
        }

        if !info.has_build_function && !info.has_package_function {
            info.warnings.push("No build() or package() function found".to_string());
        }

        info.is_valid = info.errors.is_empty();
        info
    }

    // Removed _analyze_security to avoid duplication with SecurityAnalyzer

    fn _clean_quoted_string(&self, s: &str) -> String {
        let s = s.trim();
        if (s.starts_with('"') && s.ends_with('"')) || (s.starts_with('\'') && s.ends_with('\'')) {
            if s.len() >= 2 {
                return s[1..s.len()-1].to_string();
            }
        }
        s.to_string()
    }

    fn _parse_bash_array(&self, array_content: &str) -> Vec<String> {
        let mut items = Vec::new();
        let mut current_item = String::new();
        let mut in_quotes = false;
        let mut quote_char = None;

        for char in array_content.chars() {
            if !in_quotes {
                if char == '"' || char == '\'' {
                    in_quotes = true;
                    quote_char = Some(char);
                } else if char.is_whitespace() {
                    if !current_item.trim().is_empty() {
                        items.push(self._clean_quoted_string(&current_item));
                        current_item = String::new();
                    }
                } else {
                    current_item.push(char);
                }
            } else {
                if Some(char) == quote_char {
                    in_quotes = false;
                    quote_char = None;
                } else {
                    current_item.push(char);
                }
            }
        }

        if !current_item.trim().is_empty() {
            items.push(self._clean_quoted_string(&current_item));
        }

        items.into_iter().filter(|s| !s.is_empty()).collect()
    }
    
    pub fn analyze_package(&self, package_path: &str) -> PackageInfo {
        let mut info = PackageInfo {
            file_path: package_path.to_string(),
            ..Default::default()
        };

        if !Path::new(package_path).exists() {
            info.errors.push("Package file not found".to_string());
            return info;
        }

        if !self._is_valid_package_file(package_path) {
            info.errors.push("Invalid package file format".to_string());
            return info;
        }

        match fs::metadata(package_path) {
            Ok(m) => info.compressed_size = m.len(),
            Err(e) => {
                info.errors.push(format!("Failed to get file size: {}", e));
                return info;
            }
        }

        if let Ok(temp_dir) = TempDir::new() {
            if let Some(pkginfo_content) = self._extract_pkginfo(package_path, temp_dir.path()) {
                info = self._parse_pkginfo_content(&pkginfo_content, info);
            } else {
                info.errors.push("Failed to extract .PKGINFO".to_string());
                return info;
            }

            if let Some(file_list) = self._extract_file_list(package_path) {
                info.file_count = file_list.len();
                info.files = file_list;
            }
        }

        info.is_valid = info.errors.is_empty();
        info
    }

    fn _is_valid_package_file(&self, file_path: &str) -> bool {
        let path = Path::new(file_path);
        if !path.is_file() { return false; }
        let filename = path.file_name().unwrap_or_default().to_string_lossy();
        self.supported_compressions.iter().any(|ext| filename.ends_with(&format!(".pkg.tar{}", ext)))
    }

    fn _extract_pkginfo(&self, package_path: &str, temp_dir: &Path) -> Option<String> {
        let output = Command::new("tar")
            .args(["--extract", "--file", package_path, "--directory", temp_dir.to_str().unwrap(), ".PKGINFO"])
            .output()
            .ok()?;

        if output.status.success() {
            let pkginfo_path = temp_dir.join(".PKGINFO");
            return fs::read_to_string(pkginfo_path).ok();
        }
        None
    }

    fn _extract_file_list(&self, package_path: &str) -> Option<Vec<String>> {
        let output = Command::new("tar")
            .args(["--list", "--file", package_path])
            .output()
            .ok()?;

        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            return Some(stdout.lines()
                .map(|l| l.trim().to_string())
                .filter(|l| !l.is_empty() && !l.starts_with('.'))
                .collect());
        }
        None
    }

    fn _parse_pkginfo_content(&self, content: &str, mut info: PackageInfo) -> PackageInfo {
        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') { continue; }
            if let Some((key, value)) = line.split_once('=') {
                let key = key.trim();
                let value = value.trim();
                match key {
                    "pkgname" => info.pkgname = value.to_string(),
                    "pkgbase" => info.pkgbase = value.to_string(),
                    "pkgver" => info.pkgver = value.to_string(),
                    "pkgdesc" => info.pkgdesc = value.to_string(),
                    "arch" => info.arch = value.to_string(),
                    "url" => info.url = value.to_string(),
                    "packager" => info.packager = value.to_string(),
                    "builddate" => info.builddate = value.to_string(),
                    "installdate" => info.installdate = value.to_string(),
                    "size" => info.size = value.parse().unwrap_or(0),
                    "reason" => info.reason = value.parse().unwrap_or(0),
                    "license" | "groups" | "provides" | "depends" | "optdepends" | "makedepends" | "conflicts" | "replaces" | "backup" | "validation" => {
                        let list = match key {
                            "license" => &mut info.license,
                            "groups" => &mut info.groups,
                            "provides" => &mut info.provides,
                            "depends" => &mut info.depends,
                            "optdepends" => &mut info.optdepends,
                            "makedepends" => &mut info.makedepends,
                            "conflicts" => &mut info.conflicts,
                            "replaces" => &mut info.replaces,
                            "backup" => &mut info.backup,
                            "validation" => &mut info.validation,
                            _ => unreachable!(),
                        };
                        list.push(value.to_string());
                    }
                    _ => {}
                }
            }
        }
        info.is_valid = !info.pkgname.is_empty() && !info.pkgver.is_empty();
        info
    }
}
