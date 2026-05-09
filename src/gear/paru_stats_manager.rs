use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ParuStats {
    pub total_builds: u64,
    pub successful_builds: u64,
    pub failed_builds: u64,
    pub total_installs: u64,
    pub total_uninstalls: u64,
    pub total_updates: u64,
    pub package_counts: HashMap<String, u64>,
}

#[derive(Debug)]
pub struct ParuStatsManager {
    stats_path: String,
}

impl ParuStatsManager {
    pub fn new() -> Self {
        let stats_dir = dirs::data_dir()
            .map(|p| p.join("paru-gui"))
            .unwrap_or_else(|| Path::new("/tmp/paru-gui").to_path_buf());
        
        if !stats_dir.exists() {
            let _ = fs::create_dir_all(&stats_dir);
        }

        let stats_path = stats_dir.join("stats.json").to_string_lossy().to_string();

        Self { stats_path }
    }

    pub fn get_stats(&self) -> ParuStats {
        if let Ok(content) = fs::read_to_string(&self.stats_path) {
            serde_json::from_str(&content).unwrap_or_default()
        } else {
            ParuStats::default()
        }
    }

    pub fn save_stats(&self, stats: &ParuStats) -> Result<(), String> {
        let content = serde_json::to_string_pretty(stats).map_err(|e| e.to_string())?;
        fs::write(&self.stats_path, content).map_err(|e| e.to_string())
    }

    pub fn increment_build(&self, success: bool) {
        let mut stats = self.get_stats();
        stats.total_builds += 1;
        if success {
            stats.successful_builds += 1;
        } else {
            stats.failed_builds += 1;
        }
        let _ = self.save_stats(&stats);
    }

    pub fn increment_install(&self, pkgname: &str) {
        let mut stats = self.get_stats();
        stats.total_installs += 1;
        *stats.package_counts.entry(pkgname.to_string()).or_insert(0) += 1;
        let _ = self.save_stats(&stats);
    }

    pub fn increment_uninstall(&self) {
        let mut stats = self.get_stats();
        stats.total_uninstalls += 1;
        let _ = self.save_stats(&stats);
    }

    pub fn increment_update(&self) {
        let mut stats = self.get_stats();
        stats.total_updates += 1;
        let _ = self.save_stats(&stats);
    }
}
