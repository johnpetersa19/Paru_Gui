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

#[derive(Debug)]
pub struct PKGBUILDAnalyzer {
    _function_re: Regex,
}

impl PKGBUILDAnalyzer {
    pub fn new() -> Self {
        Self {
            _function_re: Regex::new(r"(?m)^\s*(\w+)\s*\(\s*\)\s*\{").unwrap(),
        }
    }

    pub fn parse_pkgbuild_detailed(&self, pkgbuild_path: &str) -> Option<PkgbuildMetadata> {
        if !Path::new(pkgbuild_path).exists() {
            return None;
        }

        let content = fs::read_to_string(pkgbuild_path).ok()?;
        let mut metadata = PkgbuildMetadata {
            pkgname: "unknown".to_string(),
            pkgver: "unknown".to_string(),
            pkgrel: "1".to_string(),
            ..Default::default()
        };

        let lines: Vec<&str> = content.lines().collect();
        let mut in_function = false;
        let mut brace_count = 0;
        let mut current_func_name = String::new();
        let mut func_content = String::new();
        let mut func_start_line = 0;

        for (i, line) in lines.iter().enumerate() {
            let line_no_comment = if let Some(pos) = line.find('#') {
                &line[..pos]
            } else {
                line
            };
            let trimmed = line_no_comment.trim();

            if !in_function {
                if let Some(caps) = self._function_re.captures(trimmed) {
                    in_function = true;
                    current_func_name = caps[1].to_string();
                    func_content = String::new();
                    func_start_line = i + 1;
                    brace_count = trimmed.chars().filter(|&c| c == '{').count() as i32 - trimmed.chars().filter(|&c| c == '}').count() as i32;
                    continue;
                }

                // Parse global variables only when not in a function
                // Improved variable parsing
                if let Some(pos) = line_no_comment.find('=') {
                    let var_name = line_no_comment[..pos].trim();
                    let remaining = line_no_comment[pos + 1..].trim();
                    
                    if remaining.starts_with('(') {
                        // Array variable - handle balanced parentheses
                        let mut brace_count = 0;
                        let mut end_pos = None;
                        for (j, c) in remaining.chars().enumerate() {
                            if c == '(' { brace_count += 1; }
                            else if c == ')' {
                                brace_count -= 1;
                                if brace_count == 0 {
                                    end_pos = Some(j);
                                    break;
                                }
                            }
                        }
                        
                        if let Some(ep) = end_pos {
                            let raw_content = &remaining[1..ep];
                            let items: Vec<String> = self._parse_bash_array(raw_content);
                            match var_name {
                                "depends" => metadata.depends.extend(items),
                                "makedepends" => metadata.makedepends.extend(items),
                                "checkdepends" => metadata.checkdepends.extend(items),
                                "optdepends" => metadata.optdepends.extend(items),
                                "arch" => metadata.arch.extend(items),
                                "source" => metadata.source.extend(items),
                                _ => {}
                            }
                        }
                    } else {
                        // Single variable
                        let value = remaining.trim_matches(|c| c == '\'' || c == '"').to_string();
                        match var_name {
                            "pkgname" => metadata.pkgname = value,
                            "pkgver" => metadata.pkgver = value,
                            "pkgrel" => metadata.pkgrel = value,
                            "epoch" => metadata.epoch = Some(value),
                            "url" => metadata.url = Some(value),
                            "license" => metadata.license = Some(value),
                            _ => {}
                        }
                    }
                }
            } else {
                // Inside a function
                func_content.push_str(line);
                func_content.push('\n');
                
                brace_count += trimmed.chars().filter(|&c| c == '{').count() as i32;
                brace_count -= trimmed.chars().filter(|&c| c == '}').count() as i32;

                if brace_count <= 0 {
                    metadata.functions.insert(current_func_name.clone(), PkgbuildFunction {
                        name: current_func_name.clone(),
                        content: func_content.clone(),
                        start_line: func_start_line,
                        end_line: i + 1,
                    });
                    in_function = false;
                    current_func_name = String::new();
                    func_content = String::new();
                }
            }
        }

        // Resolve variables in source
        metadata.source = metadata.source.iter()
            .map(|s| s.replace("$pkgname", &metadata.pkgname).replace("$pkgver", &metadata.pkgver))
            .collect();

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

    fn _clean_quoted_string(&self, s: &str) -> String {
        let s = s.trim();
        if (s.starts_with('"') && s.ends_with('"')) || (s.starts_with('\'') && s.ends_with('\'')) {
            if s.len() >= 2 {
                return s[1..s.len()-1].to_string();
            }
        }
        s.to_string()
    }
}
