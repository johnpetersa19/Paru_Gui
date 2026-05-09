use std::fs;
use regex::Regex;
use serde::{Deserialize, Serialize};
use reqwest::blocking::Client;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UpdateSourceType {
    WebApi,
    HtmlScraping,
    RssFeed,
    FtpListing,
    ArchiveListing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UpdatePriority {
    Low,
    Normal,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpstreamUpdateInfo {
    pub pkgname: String,
    pub current_version: String,
    pub version: String,
    pub release_date: Option<String>,
    pub changelog_url: Option<String>,
    pub download_url: Option<String>,
    pub source_type: String,
    pub security_update: bool,
    pub priority: UpdatePriority,
}

#[derive(Debug)]
pub struct UpstreamSource {
    pub name: String,
    pub source_type: UpdateSourceType,
    pub url: String,
}

#[derive(Debug)]
pub struct UniversalUpstreamChecker {
    client: Client,
}

impl UniversalUpstreamChecker {
    pub fn new() -> Self {
        Self {
            client: Client::builder()
                .user_agent("paru-gui/2.7.0 (UpstreamChecker)")
                .timeout(std::time::Duration::from_secs(15))
                .build()
                .unwrap_or_else(|_| Client::new()),
        }
    }

    pub fn check_for_updates(&self, pkgbuild_path: &str) -> Option<UpstreamUpdateInfo> {
        let (pkgname, current_version, sources, project_url) = self._parse_pkgbuild(pkgbuild_path)?;
        
        let detected_sources = self._auto_detect_sources(&sources, project_url.as_deref());
        
        let mut best_update: Option<UpstreamUpdateInfo> = None;
        
        for source in detected_sources {
            if let Some(update) = self._check_source(&source, &pkgname, &current_version) {
                if self._is_newer_version(&current_version, &update.version) {
                    if best_update.as_ref().map_or(true, |best| self._is_newer_version(&best.version, &update.version)) {
                        best_update = Some(update);
                    }
                }
            }
        }

        best_update
    }

    fn _auto_detect_sources(&self, sources: &[String], project_url: Option<&str>) -> Vec<UpstreamSource> {
        let mut detected = Vec::new();
        let mut potential_urls = sources.to_vec();
        if let Some(url) = project_url {
            potential_urls.push(url.to_string());
        }

        for url in potential_urls {
            if url.contains("github.com") {
                let re = Regex::new(r"github\.com/([^/]+)/([^/]+)").unwrap();
                if let Some(caps) = re.captures(&url) {
                    let owner = &caps[1];
                    let repo = caps[2].trim_end_matches(".git");
                    detected.push(UpstreamSource {
                        name: "GitHub".to_string(),
                        source_type: UpdateSourceType::WebApi,
                        url: format!("https://api.github.com/repos/{}/{}/releases/latest", owner, repo),
                    });
                }
            } else if url.contains("gitlab") {
                let re = Regex::new(r"gitlab\.[\w\.-]+/([\w\.-]+(?:/[\w\.-]+)*)/([\w\.-]+?)(?:\.git)?$").unwrap();
                if let Some(caps) = re.captures(&url.trim_end_matches('/')) {
                    let host = url.split('/').nth(2).unwrap_or("gitlab.com");
                    let path = format!("{}/{}", &caps[1], &caps[2]);
                    let encoded_path = urlencoding::encode(&path);
                    detected.push(UpstreamSource {
                        name: "GitLab".to_string(),
                        source_type: UpdateSourceType::WebApi,
                        url: format!("https://{}/api/v4/projects/{}/releases/permalink/latest", host, encoded_path),
                    });
                }
            } else if url.contains("pypi.org") {
                let re = Regex::new(r"pypi\.org/project/([^/]+)").unwrap();
                if let Some(caps) = re.captures(&url) {
                    detected.push(UpstreamSource {
                        name: "PyPI".to_string(),
                        source_type: UpdateSourceType::WebApi,
                        url: format!("https://pypi.org/pypi/{}/json", &caps[1]),
                    });
                }
            } else if url.contains("npmjs.com") {
                let re = Regex::new(r"npmjs\.com/package/([^/]+)").unwrap();
                if let Some(caps) = re.captures(&url) {
                    detected.push(UpstreamSource {
                        name: "npm".to_string(),
                        source_type: UpdateSourceType::WebApi,
                        url: format!("https://registry.npmjs.org/{}/latest", &caps[1]),
                    });
                }
            } else if url.contains("crates.io") {
                let re = Regex::new(r"crates\.io/crates/([^/]+)").unwrap();
                if let Some(caps) = re.captures(&url) {
                    detected.push(UpstreamSource {
                        name: "Crates.io".to_string(),
                        source_type: UpdateSourceType::WebApi,
                        url: format!("https://crates.io/api/v1/crates/{}", &caps[1]),
                    });
                }
            }
            // Add more as needed...
        }

        detected
    }

    fn _check_source(&self, source: &UpstreamSource, pkgname: &str, current_version: &str) -> Option<UpstreamUpdateInfo> {
        match source.source_type {
            UpdateSourceType::WebApi => self._check_web_api(source, pkgname, current_version),
            _ => None,
        }
    }

    fn _check_web_api(&self, source: &UpstreamSource, pkgname: &str, current_version: &str) -> Option<UpstreamUpdateInfo> {
        let resp: serde_json::Value = self.client.get(&source.url).send().ok()?.json().ok()?;
        
        let mut version = None;
        let mut release_date = None;
        let mut changelog_url = None;
        let mut download_url = None;

        if let Some(v) = resp.get("tag_name") {
            version = v.as_str().map(|s| s.trim_start_matches(|c| c == 'v' || c == 'V').to_string());
            release_date = resp.get("published_at").or(resp.get("created_at")).and_then(|d| d.as_str().map(|s| s.to_string()));
            changelog_url = resp.get("html_url").and_then(|u| u.as_str().map(|s| s.to_string()));
            download_url = resp.get("tarball_url").and_then(|u| u.as_str().map(|s| s.to_string()));
        } else if let Some(info) = resp.get("info") {
            // PyPI
            version = info.get("version").and_then(|v| v.as_str().map(|s| s.to_string()));
            changelog_url = info.get("project_url").or(info.get("home_page")).and_then(|u| u.as_str().map(|s| s.to_string()));
        } else if let Some(v) = resp.get("version") {
            // npm
            version = v.as_str().map(|s| s.trim_start_matches(|c| c == 'v' || c == 'V').to_string());
        } else if let Some(_crate_info) = resp.get("crate") {
            // Crates.io
            if let Some(versions) = resp.get("versions").and_then(|v| v.as_array()) {
                if let Some(latest) = versions.get(0) {
                    version = latest.get("num").and_then(|n| n.as_str().map(|s| s.to_string()));
                    release_date = latest.get("created_at").and_then(|d| d.as_str().map(|s| s.to_string()));
                }
            }
        }

        if let Some(v) = version {
            return Some(UpstreamUpdateInfo {
                pkgname: pkgname.to_string(),
                current_version: current_version.to_string(),
                version: v,
                release_date,
                changelog_url,
                download_url,
                source_type: source.name.clone(),
                security_update: false,
                priority: UpdatePriority::Normal,
            });
        }

        None
    }

    fn _parse_pkgbuild(&self, path: &str) -> Option<(String, String, Vec<String>, Option<String>)> {
        let content = fs::read_to_string(path).ok()?;
        let mut pkgname = "unknown".to_string();
        let mut pkgver = "unknown".to_string();
        let mut sources = Vec::new();
        let mut project_url = None;

        let content_clean = Regex::new(r"(?m)#.*$").unwrap().replace_all(&content, "");

        for line in content_clean.lines() {
            let line = line.trim();
            if line.starts_with("pkgname=") {
                pkgname = line["pkgname=".len()..].trim_matches(|c| c == '\'' || c == '"').to_string();
            } else if line.starts_with("pkgver=") {
                pkgver = line["pkgver=".len()..].trim_matches(|c| c == '\'' || c == '"').to_string();
            } else if line.starts_with("url=") {
                project_url = Some(line["url=".len()..].trim_matches(|c| c == '\'' || c == '"').to_string());
            }
        }

        if let Some(caps) = Regex::new(r"source=\(([^)]*)\)").unwrap().captures(&content_clean) {
            for src in caps[1].lines() {
                let src = src.trim().trim_matches(|c| c == '\'' || c == '"');
                if !src.is_empty() {
                    let resolved = src.replace("$pkgname", &pkgname).replace("$pkgver", &pkgver);
                    sources.push(resolved);
                }
            }
        }

        Some((pkgname, pkgver, sources, project_url))
    }

    fn _is_newer_version(&self, current: &str, candidate: &str) -> bool {
        self._compare_versions(candidate, current) == std::cmp::Ordering::Greater
    }

    fn _compare_versions(&self, v1: &str, v2: &str) -> std::cmp::Ordering {
        let t1 = self._version_to_tuple(v1);
        let t2 = self._version_to_tuple(v2);
        t1.cmp(&t2)
    }

    fn _version_to_tuple(&self, version: &str) -> (i32, Vec<i32>, String) {
        let (epoch, rest) = if let Some((e, r)) = version.split_once(':') {
            (e.parse::<i32>().unwrap_or(0), r)
        } else {
            (0, version)
        };

        let rest = rest.trim_start_matches(|c: char| !c.is_numeric());
        let parts: Vec<i32> = rest.split(|c: char| !c.is_numeric())
            .filter(|s| !s.is_empty())
            .map(|s| s.parse::<i32>().unwrap_or(0))
            .collect();
        
        let suffix = rest.chars().skip_while(|c| c.is_numeric() || *c == '.').collect::<String>();
        
        (epoch, parts, suffix)
    }
}
