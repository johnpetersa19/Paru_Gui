use std::process::Command;
use std::path::Path;
use std::fs;
// use chrono::{DateTime, Utc, TimeZone};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SignatureStatus {
    Valid,
    Invalid,
    Expired,
    Revoked,
    Missing,
    Unknown,
    Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum KeyTrust {
    Undefined,
    Never,
    Marginal,
    Full,
    Ultimate,
    Unknown,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpgKey {
    pub key_id: String,
    pub fingerprint: String,
    pub user_id: String,
    pub email: String,
    pub creation_date: Option<i64>,
    pub expiration_date: Option<i64>,
    pub trust_level: KeyTrust,
    pub key_size: i32,
    pub algorithm: String,
    pub is_expired: bool,
    pub is_revoked: bool,
    pub subkeys: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureInfo {
    pub status: SignatureStatus,
    pub key_id: String,
    pub signer: String,
    pub timestamp: Option<i64>,
    pub fingerprint: String,
    pub trust_level: KeyTrust,
    pub error_message: Option<String>,
    pub signature_file: Option<String>,
}

#[derive(Debug)]
pub struct SignatureVerifier {
    pub gnupg_home: String,
}

impl SignatureVerifier {
    pub fn new(gnupg_home: Option<String>) -> Self {
        let home = gnupg_home.unwrap_or_else(|| {
            dirs::home_dir()
                .map(|p| p.join(".gnupg").to_string_lossy().to_string())
                .unwrap_or_else(|| "/tmp/.gnupg".to_string())
        });
        
        let verifier = Self { gnupg_home: home };
        verifier._ensure_gnupg_directory();
        verifier
    }

    fn _ensure_gnupg_directory(&self) {
        let path = Path::new(&self.gnupg_home);
        if !path.exists() {
            let _ = fs::create_dir_all(path);
            // In a real app, set permissions to 700
        }
    }

    fn _run_gpg_command(&self, args: &[&str]) -> (i32, String, String) {
        let output = Command::new("gpg")
            .arg("--homedir")
            .arg(&self.gnupg_home)
            .arg("--batch")
            .arg("--no-tty")
            .args(args)
            .output();

        match output {
            Ok(o) => (
                o.status.code().unwrap_or(-1),
                String::from_utf8_lossy(&o.stdout).to_string(),
                String::from_utf8_lossy(&o.stderr).to_string(),
            ),
            Err(e) => (-1, String::new(), e.to_string()),
        }
    }

    pub fn verify_file_signature(&self, file_path: &str, signature_path: Option<&str>) -> SignatureInfo {
        let mut args = vec!["--verify", "--status-fd", "1"];
        if let Some(sig) = signature_path {
            args.push(sig);
        }
        args.push(file_path);

        let (returncode, stdout, stderr) = self._run_gpg_command(&args);
        self._parse_verification_output(returncode, &stdout, &stderr, signature_path.unwrap_or(file_path))
    }

    fn _parse_verification_output(&self, _returncode: i32, stdout: &str, _stderr: &str, signature_file: &str) -> SignatureInfo {
        let mut info = SignatureInfo {
            status: SignatureStatus::Unknown,
            key_id: String::new(),
            signer: "Unknown".to_string(),
            timestamp: None,
            fingerprint: String::new(),
            trust_level: KeyTrust::Unknown,
            error_message: None,
            signature_file: Some(signature_file.to_string()),
        };

        for line in stdout.lines() {
            if line.starts_with("[GNUPG:] GOODSIG") {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 4 {
                    info.status = SignatureStatus::Valid;
                    info.key_id = parts[2].to_string();
                    info.signer = parts[3..].join(" ");
                }
            } else if line.starts_with("[GNUPG:] BADSIG") {
                info.status = SignatureStatus::Invalid;
                info.error_message = Some("Bad signature".to_string());
            } else if line.starts_with("[GNUPG:] ERRSIG") {
                info.status = SignatureStatus::Error;
                info.error_message = Some("Signature error".to_string());
            } else if line.starts_with("[GNUPG:] NOSIG") {
                info.status = SignatureStatus::Missing;
                info.error_message = Some("No signature found".to_string());
            }
        }

        info
    }
}
