use std::fs;
use std::path::Path;
use std::process::Command;
use std::collections::HashMap;
use regex::Regex;
use similar::{ChangeTag, TextDiff};

#[derive(Debug, Clone, Default)]
pub struct PkgbuildFunction {
    pub name: String,
    pub content: String,
    pub start_line: usize,
    pub end_line: usize,
}

#[derive(Debug, Clone, Default)]
pub struct PkgbuildMetadata {
    pub pkgname: String,
    pub pkgver: String,
    pub pkgrel: String,
    pub epoch: Option<String>,
    pub arch: Vec<String>,
    pub url: Option<String>,
    pub license: Option<String>,
    pub depends: Vec<String>,
    pub makedepends: Vec<String>,
    pub checkdepends: Vec<String>,
    pub optdepends: Vec<String>,
    pub source: Vec<String>,
    pub functions: HashMap<String, PkgbuildFunction>,
}

#[derive(Debug, Clone)]
pub struct PkgbuildComparisonResult {
    pub diff: String,
    pub has_changes: bool,
    pub critical_sections_changed: Vec<String>,
    pub version_diff: (String, String),
}

#[derive(Debug, Clone)]
pub struct DependencyAnalysisResult {
    pub package_name: String,
    pub current_pkgver: String,
    pub dependencies: HashMap<String, Vec<String>>,
    pub missing_deps: Vec<String>,
    pub installed_deps: Vec<String>,
    pub optional_deps_available: Vec<String>,
}

pub struct PKGBUILDAnalyzer {
    _array_var_re: Regex,
    _single_var_re: Regex,
    _function_re: Regex,
    _func_end_re: Regex,
}

impl PKGBUILDAnalyzer {
    pub fn new() -> Self {
        Self {
            _array_var_re: Regex::new(r"(?m)^\s*(\w+)\s*=\s*\(([^)]*)\)").unwrap(),
            _single_var_re: Regex::new(r"(?m)^\s*(\w+)\s*=\s*(.*?)\s*$").unwrap(),
            _function_re: Regex::new(r"(?m)^\s*(\w+)\s*\(\s*\)\s*\{").unwrap(),
            _func_end_re: Regex::new(r"(?m)^\s*\}").unwrap(),
        }
    }

    pub fn parse_pkgbuild_detailed(&self, pkgbuild_path: &str) -> Option<PkgbuildMetadata> {
        if !Path::new(pkgbuild_path).exists() {
            return None;
        }

        let content = fs::read_to_string(pkgbuild_path).ok()?;
        let content_no_comments = Regex::new(r"(?m)#.*$").unwrap().replace_all(&content, "").to_string();

        let mut metadata = PkgbuildMetadata {
            pkgname: "unknown".to_string(),
            pkgver: "unknown".to_string(),
            pkgrel: "1".to_string(),
            ..Default::default()
        };

        // Extract basic variables
        let var_names = vec!["pkgname", "pkgver", "pkgrel", "epoch", "url", "license", "arch"];
        for var_name in var_names {
            let pattern = format!(r"(?m)^\s*{}\s*=\s*(.*?)\s*$", var_name);
            if let Ok(re) = Regex::new(&pattern) {
                if let Some(caps) = re.captures(&content_no_comments) {
                    let value = caps[1].trim().trim_matches(|c| c == '\'' || c == '"' || c == '(' || c == ')').to_string();
                    match var_name {
                        "pkgname" => metadata.pkgname = value,
                        "pkgver" => metadata.pkgver = value,
                        "pkgrel" => metadata.pkgrel = value,
                        "epoch" => metadata.epoch = Some(value),
                        "url" => metadata.url = Some(value),
                        "license" => metadata.license = Some(value),
                        "arch" => metadata.arch = value.split_whitespace().map(|s| s.to_string()).collect(),
                        _ => {}
                    }
                }
            }
        }

        // Extract array variables
        for caps in self._array_var_re.captures_iter(&content_no_comments) {
            let var_name = &caps[1];
            let raw_content = &caps[2];
            let items: Vec<String> = raw_content.split_whitespace()
                .map(|s| s.trim_matches(|c| c == '\'' || c == '"').to_string())
                .filter(|s| !s.is_empty())
                .collect();

            match var_name {
                "depends" => metadata.depends.extend(items),
                "makedepends" => metadata.makedepends.extend(items),
                "checkdepends" => metadata.checkdepends.extend(items),
                "optdepends" => metadata.optdepends.extend(items),
                "source" => metadata.source.extend(items),
                _ => {}
            }
        }

        // Resolve variables in source
        metadata.source = metadata.source.iter()
            .map(|s| s.replace("$pkgname", &metadata.pkgname).replace("$pkgver", &metadata.pkgver))
            .collect();

        // Extract functions
        let lines: Vec<&str> = content.lines().collect();
        let mut in_function = false;
        let mut current_func_name = String::new();
        let mut func_content = String::new();
        let mut func_start_line = 0;

        for (i, line) in lines.iter().enumerate() {
            if let Some(caps) = self._function_re.captures(line) {
                if in_function {
                    metadata.functions.insert(current_func_name.clone(), PkgbuildFunction {
                        name: current_func_name.clone(),
                        content: func_content.clone(),
                        start_line: func_start_line,
                        end_line: i,
                    });
                }
                in_function = true;
                current_func_name = caps[1].to_string();
                func_content = String::new();
                func_start_line = i + 1;
            } else if in_function && self._func_end_re.is_match(line) {
                metadata.functions.insert(current_func_name.clone(), PkgbuildFunction {
                    name: current_func_name.clone(),
                    content: func_content.clone(),
                    start_line: func_start_line,
                    end_line: i + 1,
                });
                in_function = false;
                current_func_name = String::new();
                func_content = String::new();
            } else if in_function {
                func_content.push_str(line);
                func_content.push('\n');
            }
        }

        if in_function {
            metadata.functions.insert(current_func_name.clone(), PkgbuildFunction {
                name: current_func_name.clone(),
                content: func_content.clone(),
                start_line: func_start_line,
                end_line: lines.len(),
            });
        }

        Some(metadata)
    }

    pub fn compare_pkgbuilds(&self, local_path: &str, upstream_path: &str) -> Option<PkgbuildComparisonResult> {
        let local_content = fs::read_to_string(local_path).ok()?;
        let upstream_content = fs::read_to_string(upstream_path).ok()?;

        let diff = TextDiff::from_lines(&local_content, &upstream_content);
        let mut diff_str = String::new();
        for hunk in diff.unified_diff().iter_hunks() {
            for change in hunk.iter_changes() {
                match change.tag() {
                    ChangeTag::Delete => diff_str.push_str(&format!("-{}", change)),
                    ChangeTag::Insert => diff_str.push_str(&format!("+{}", change)),
                    ChangeTag::Equal => diff_str.push_str(&format!(" {}", change)),
                }
            }
        }

        let has_changes = !diff_str.is_empty();
        let mut critical_sections_changed = Vec::new();
        if has_changes {
            if diff_str.contains("source=") || diff_str.contains("prepare()") || diff_str.contains("package()") {
                critical_sections_changed.push("source".to_string());
                critical_sections_changed.push("prepare_function".to_string());
                critical_sections_changed.push("package_function".to_string());
            }
        }

        let local_meta = self.parse_pkgbuild_detailed(local_path);
        let upstream_meta = self.parse_pkgbuild_detailed(upstream_path);

        let local_ver = local_meta.map(|m| format!("{}-{}", m.pkgver, m.pkgrel)).unwrap_or_else(|| "N/A".to_string());
        let upstream_ver = upstream_meta.map(|m| format!("{}-{}", m.pkgver, m.pkgrel)).unwrap_or_else(|| "N/A".to_string());

        Some(PkgbuildComparisonResult {
            diff: diff_str,
            has_changes,
            critical_sections_changed,
            version_diff: (local_ver, upstream_ver),
        })
    }

    pub fn analyze_dependencies(&self, pkgbuild_path: &str) -> Option<DependencyAnalysisResult> {
        let metadata = self.parse_pkgbuild_detailed(pkgbuild_path)?;
        
        let mut result = DependencyAnalysisResult {
            package_name: metadata.pkgname.clone(),
            current_pkgver: metadata.pkgver.clone(),
            dependencies: HashMap::new(),
            missing_deps: Vec::new(),
            installed_deps: Vec::new(),
            optional_deps_available: Vec::new(),
        };

        result.dependencies.insert("depends".to_string(), metadata.depends.clone());
        result.dependencies.insert("makedepends".to_string(), metadata.makedepends.clone());
        result.dependencies.insert("checkdepends".to_string(), metadata.checkdepends.clone());
        result.dependencies.insert("optdepends".to_string(), metadata.optdepends.clone());

        let all_req_deps: Vec<String> = metadata.depends.iter().chain(metadata.makedepends.iter()).chain(metadata.checkdepends.iter()).cloned().collect();

        let installed_output = Command::new("pacman").args(["-Qq"]).output().ok()?;
        let installed_str = String::from_utf8_lossy(&installed_output.stdout);
        let installed_set: std::collections::HashSet<&str> = installed_str.lines().collect();

        for dep in all_req_deps {
            // Simple check (doesn't handle versioning yet)
            let dep_name = dep.split(|c| c == '>' || c == '<' || c == '=').next().unwrap_or(&dep).trim();
            if installed_set.contains(dep_name) {
                result.installed_deps.push(dep);
            } else {
                result.missing_deps.push(dep);
            }
        }

        for optdep in metadata.optdepends {
            let dep_name = optdep.split(|c| c == '>' || c == '<' || c == '=').next().unwrap_or(&optdep).trim();
            if installed_set.contains(dep_name) {
                result.optional_deps_available.push(optdep);
            }
        }

        Some(result)
    }

    pub fn verify_version_compatibility(&self, pkgbuild_path: &str) -> (bool, String) {
        let metadata = match self.parse_pkgbuild_detailed(pkgbuild_path) {
            Some(m) => m,
            None => return (false, "Could not parse PKGBUILD metadata.".to_string()),
        };

        let arch_output = Command::new("uname").arg("-m").output();
        let current_arch = arch_output.map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string()).unwrap_or_else(|_| "unknown".to_string());

        if !metadata.arch.contains(&"any".to_string()) && !metadata.arch.contains(&current_arch) {
            return (false, format!("Architecture '{}' not supported (supports: {:?})", current_arch, metadata.arch));
        }

        (true, "Version and architecture appear compatible.".to_string())
    }
}
