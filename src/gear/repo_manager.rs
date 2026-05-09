use std::process::Command;
use std::path::Path;
use std::fs;

#[derive(Debug, Clone)]
pub struct LocalRepo {
    pub name: String,
    pub path: String,
    pub db_name: String,
}

#[derive(Debug)]
pub struct RepoManager {
    pub repos: Vec<LocalRepo>,
}

impl RepoManager {
    pub fn new() -> Self {
        // In a real app, load from config
        Self { repos: Vec::new() }
    }

    pub fn add_repo(&mut self, name: &str, path: &str) -> Result<(), String> {
        let repo_path = Path::new(path);
        if !repo_path.exists() {
            fs::create_dir_all(repo_path).map_err(|e| e.to_string())?;
        }

        let db_name = format!("{}.db.tar.gz", name);
        self.repos.push(LocalRepo {
            name: name.to_string(),
            path: path.to_string(),
            db_name,
        });
        Ok(())
    }

    pub fn add_package_to_repo(&self, repo_name: &str, package_path: &str) -> Result<(), String> {
        let repo = self.repos.iter().find(|r| r.name == repo_name)
            .ok_or_else(|| format!("Repo not found: {}", repo_name))?;

        let pkg_path = Path::new(package_path);
        if !pkg_path.exists() {
            return Err(format!("Package file not found: {}", package_path));
        }

        // Copy package to repo directory
        let dest_path = Path::new(&repo.path).join(pkg_path.file_name().unwrap());
        fs::copy(pkg_path, &dest_path).map_err(|e| e.to_string())?;

        // Update repo database
        let output = Command::new("repo-add")
            .arg(Path::new(&repo.path).join(&repo.db_name))
            .arg(dest_path)
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }

    pub fn remove_package_from_repo(&self, repo_name: &str, pkgname: &str) -> Result<(), String> {
        let repo = self.repos.iter().find(|r| r.name == repo_name)
            .ok_or_else(|| format!("Repo not found: {}", repo_name))?;

        let output = Command::new("repo-remove")
            .arg(Path::new(&repo.path).join(&repo.db_name))
            .arg(pkgname)
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }
}
