use std::process::Command;
use std::path::Path;
use std::fs;

#[derive(Debug)]
pub struct ChrootManager {
    pub chroot_dir: String,
}

impl ChrootManager {
    pub fn new() -> Self {
        let default_dir = "/var/lib/paru-gui/chroot";
        Self { chroot_dir: default_dir.to_string() }
    }

    pub fn set_chroot_dir(&mut self, path: &str) {
        self.chroot_dir = path.to_string();
    }

    pub fn initialize_chroot(&self) -> Result<(), String> {
        if !Path::new(&self.chroot_dir).exists() {
            fs::create_dir_all(&self.chroot_dir).map_err(|e| e.to_string())?;
        }

        let output = Command::new("mkchrootpkg")
            .arg("-r")
            .arg(&self.chroot_dir)
            .arg("-I") // Initial build
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }

    pub fn build_in_chroot(&self, pkgbuild_dir: &str) -> Result<Vec<String>, String> {
        let pkg_dir = Path::new(pkgbuild_dir);
        if !pkg_dir.exists() {
            return Err(format!("PKGBUILD directory not found: {}", pkgbuild_dir));
        }

        let output = Command::new("makechrootpkg")
            .arg("-r")
            .arg(&self.chroot_dir)
            .arg("-c") // Clean build
            .current_dir(pkg_dir)
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            // Find generated packages
            let mut packages = Vec::new();
            if let Ok(entries) = fs::read_dir(pkg_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_file() && path.to_string_lossy().contains(".pkg.tar") {
                        packages.push(path.to_string_lossy().to_string());
                    }
                }
            }
            Ok(packages)
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }

    pub fn update_chroot(&self) -> Result<(), String> {
        let output = Command::new("arch-nspawn")
            .arg(format!("{}/root", self.chroot_dir))
            .arg("pacman")
            .arg("-Syu")
            .arg("--noconfirm")
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }
}
