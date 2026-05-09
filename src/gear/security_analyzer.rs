use std::collections::HashMap;
use std::fs;
use regex::Regex;
use serde::{Deserialize, Serialize};
use reqwest::blocking::Client;
// use chrono::{DateTime, Utc, Duration};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum RiskLevel {
    None = 0,
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectedRisk {
    pub level: RiskLevel,
    pub description: String,
    pub line_number: Option<usize>,
    pub snippet: Option<String>,
    pub category: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CVEResult {
    pub cve_id: String,
    pub description: String,
    pub severity: String,
    pub published_date: String,
    pub affected_versions: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PkgbuildSecurityAnalysisResult {
    pub pkgname: String,
    pub pkgver: String,
    pub overall_trust_score: f64,
    pub overall_trust_level: RiskLevel,
    pub detected_risks: Vec<DetectedRisk>,
    pub heatmap_lines: Vec<(usize, RiskLevel, String)>,
    pub aur_info: HashMap<String, String>,
    pub cve_results: Vec<CVEResult>,
    pub pgp_validation_results: HashMap<String, serde_json::Value>,
    pub raw_pkgbuild_content: String,
    pub security_suggestions: Vec<String>,
}

pub struct SecurityAnalyzer {
    dangerous_patterns: Vec<Regex>,
    insecure_patterns: Vec<(Regex, RiskLevel, String)>,
    trusted_domains: Vec<String>,
    client: Client,
}

impl SecurityAnalyzer {
    pub fn new() -> Self {
        Self {
            dangerous_patterns: vec![
                Regex::new(r"(?i)\bsudo\s+(rm|mv|cp)\s+-?rf?\s*/").unwrap(),
                Regex::new(r"(?i)\b(chown|chmod)\s+-?R?\s*root\s*/").unwrap(),
                Regex::new(r"(?i)\bmkfs\b").unwrap(),
                Regex::new(r"(?i)\bdd\s+if=/dev/zero").unwrap(),
                Regex::new(r"(?i)\b(curl|wget)\s+.*?\|\s*(bash|sh|zsh)\b").unwrap(),
            ],
            insecure_patterns: vec![
                (Regex::new(r#"(?i)sha\d+sums=\([^)]*['"]SKIP['"][^)]*\)"#).unwrap(), RiskLevel::High, "Checksum verification skipped".to_string()),
                (Regex::new(r"(?i)--disable-ssl-verify").unwrap(), RiskLevel::High, "SSL verification disabled".to_string()),
                (Regex::new(r"(?i)--no-check-certificate").unwrap(), RiskLevel::High, "Certificate checking disabled".to_string()),
            ],
            trusted_domains: vec![
                "github.com".to_string(), "gitlab.com".to_string(), "aur.archlinux.org".to_string(),
                "archlinux.org".to_string(), "kernel.org".to_string(),
            ],
            client: Client::new(),
        }
    }

    pub fn analyze_pkgbuild(&self, pkgbuild_path: &str) -> PkgbuildSecurityAnalysisResult {
        let content = fs::read_to_string(pkgbuild_path).unwrap_or_default();
        let mut result = PkgbuildSecurityAnalysisResult {
            pkgname: "unknown".to_string(),
            pkgver: "unknown".to_string(),
            overall_trust_score: 1.0,
            overall_trust_level: RiskLevel::None,
            detected_risks: Vec::new(),
            heatmap_lines: Vec::new(),
            aur_info: HashMap::new(),
            cve_results: Vec::new(),
            pgp_validation_results: HashMap::new(),
            raw_pkgbuild_content: content.clone(),
            security_suggestions: Vec::new(),
        };

        // Static Analysis
        self._analyze_static_content(&content, &mut result);
        
        // Final Score Calculation (Simplified)
        self._calculate_overall_trust(&mut result);

        result
    }

    fn _analyze_static_content(&self, content: &str, result: &mut PkgbuildSecurityAnalysisResult) {
        for (i, line) in content.lines().enumerate() {
            let line_num = i + 1;
            if line.trim().starts_with('#') { continue; }

            for re in &self.dangerous_patterns {
                if re.is_match(line) {
                    result.detected_risks.push(DetectedRisk {
                        level: RiskLevel::Critical,
                        description: format!("Dangerous command: {}", line.trim()),
                        line_number: Some(line_num),
                        snippet: Some(line.to_string()),
                        category: "Command".to_string(),
                    });
                    result.heatmap_lines.push((line_num, RiskLevel::Critical, "Dangerous command".to_string()));
                }
            }

            for (re, level, desc) in &self.insecure_patterns {
                if re.is_match(line) {
                    result.detected_risks.push(DetectedRisk {
                        level: *level,
                        description: desc.clone(),
                        line_number: Some(line_num),
                        snippet: Some(line.to_string()),
                        category: "Security".to_string(),
                    });
                    result.heatmap_lines.push((line_num, *level, desc.clone()));
                }
            }
        }
    }

    fn _calculate_overall_trust(&self, result: &mut PkgbuildSecurityAnalysisResult) {
        let mut score: f64 = 1.0;
        for risk in &result.detected_risks {
            match risk.level {
                RiskLevel::Critical => score -= 0.5,
                RiskLevel::High => score -= 0.2,
                RiskLevel::Medium => score -= 0.1,
                RiskLevel::Low => score -= 0.05,
                RiskLevel::None => {}
            }
        }
        result.overall_trust_score = score.max(0.0);
        result.overall_trust_level = if score >= 0.8 { RiskLevel::None }
            else if score >= 0.6 { RiskLevel::Low }
            else if score >= 0.3 { RiskLevel::Medium }
            else if score >= 0.1 { RiskLevel::High }
            else { RiskLevel::Critical };
    }
}
