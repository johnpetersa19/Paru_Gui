use std::collections::HashMap;
use std::path::Path;
use std::process::{Command, Stdio};
// use std::io::{BufRead, BufReader};
use std::time::Instant;
use which::which;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IsolationLevel {
    Strict,
    Medium,
    Minimal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SandboxStatus {
    Ready,
    Running,
    Completed,
    Failed,
    Timeout,
}

#[derive(Debug, Clone)]
pub struct SandboxOptions {
    pub isolation_level: IsolationLevel,
    pub allow_network: bool,
    pub allow_home: bool,
    pub allow_x11: bool,
    pub allow_dbus: bool,
    pub working_dir: Option<String>,
    pub bind_paths: Vec<(String, String, Option<String>)>,
    pub env_vars: HashMap<String, String>,
    pub capabilities: Vec<String>,
    pub uid: Option<u32>,
    pub gid: Option<u32>,
    pub hostname: Option<String>,
    pub tmpfs_paths: Vec<String>,
    pub ro_bind_paths: Vec<(String, String)>,
    pub dev_bind_paths: Vec<(String, String)>,
}

impl Default for SandboxOptions {
    fn default() -> Self {
        Self {
            isolation_level: IsolationLevel::Medium,
            allow_network: false,
            allow_home: false,
            allow_x11: false,
            allow_dbus: false,
            working_dir: None,
            bind_paths: Vec::new(),
            env_vars: HashMap::new(),
            capabilities: Vec::new(),
            uid: None,
            gid: None,
            hostname: None,
            tmpfs_paths: Vec::new(),
            ro_bind_paths: Vec::new(),
            dev_bind_paths: Vec::new(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct SandboxResult {
    pub return_code: i32,
    pub stdout: String,
    pub stderr: String,
    pub status: SandboxStatus,
    pub execution_time: f64,
    pub warnings: Vec<String>,
    pub errors: Vec<String>,
}

#[derive(Debug)]
pub struct SandboxManager {
    // In a real app, you might want to track processes, but for now we'll keep it simple.
}

impl SandboxManager {
    pub fn new() -> Result<Self, String> {
        if which("bwrap").is_err() {
            return Err("bubblewrap (bwrap) is required but not found".to_string());
        }
        Ok(Self {})
    }

    pub fn run_sandboxed_command(
        &self,
        command: &[String],
        options: &SandboxOptions,
        _timeout: Option<u64>,
    ) -> SandboxResult {
        let start_time = Instant::now();
        let bwrap_args = self._build_bwrap_command(command, options);

        let mut process_cmd = Command::new(&bwrap_args[0]);
        process_cmd.args(&bwrap_args[1..])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        if let Some(ref dir) = options.working_dir {
            process_cmd.current_dir(dir);
        }

        let mut child = match process_cmd.spawn() {
            Ok(c) => c,
            Err(e) => return SandboxResult {
                return_code: -1,
                stdout: String::new(),
                stderr: e.to_string(),
                status: SandboxStatus::Failed,
                execution_time: start_time.elapsed().as_secs_f64(),
                warnings: Vec::new(),
                errors: vec![format!("Failed to spawn process: {}", e)],
            },
        };

        let result = if let Some(timeout_secs) = _timeout {
            let timeout_dur = std::time::Duration::from_secs(timeout_secs);
            let mut status = SandboxStatus::Running;
            let mut output_res = Option::None;

            while start_time.elapsed() < timeout_dur {
                match child.try_wait() {
                    Ok(Some(s)) => {
                        status = if s.success() { SandboxStatus::Completed } else { SandboxStatus::Failed };
                        output_res = Some(s);
                        break;
                    }
                    Ok(Option::None) => {
                        std::thread::sleep(std::time::Duration::from_millis(100));
                    }
                    Err(_e) => {
                        status = SandboxStatus::Failed;
                        break;
                    }
                }
            }

            if output_res.is_none() && status == SandboxStatus::Running {
                let _ = child.kill();
                status = SandboxStatus::Timeout;
            }
            
            // Collect output after wait/kill
            let output = child.wait_with_output().ok();
            (status, output)
        } else {
            let output = child.wait_with_output().ok();
            let status = match &output {
                Some(o) => if o.status.success() { SandboxStatus::Completed } else { SandboxStatus::Failed },
                Option::None => SandboxStatus::Failed,
            };
            (status, output)
        };

        let (status, output) = result;
        let stdout_str = output.as_ref().map(|o| String::from_utf8_lossy(&o.stdout).to_string()).unwrap_or_default();
        let stderr_str = output.as_ref().map(|o| String::from_utf8_lossy(&o.stderr).to_string()).unwrap_or_default();
        let return_code = output.as_ref().and_then(|o| o.status.code()).unwrap_or(-1);

        SandboxResult {
            return_code,
            stdout: stdout_str.clone(),
            stderr: stderr_str.clone(),
            status,
            execution_time: start_time.elapsed().as_secs_f64(),
            warnings: self._extract_warnings(&stdout_str, &stderr_str),
            errors: self._extract_errors(&stderr_str),
        }
    }

    fn _build_bwrap_command(&self, command: &[String], options: &SandboxOptions) -> Vec<String> {
        let mut args = vec!["bwrap".to_string(), "--unshare-all".to_string(), "--die-with-parent".to_string()];

        match options.isolation_level {
            IsolationLevel::Strict => {
                args.extend(vec![
                    "--unshare-user".to_string(),
                    "--unshare-ipc".to_string(),
                    "--unshare-pid".to_string(),
                    "--unshare-cgroup".to_string(),
                    "--no-new-privileges".to_string(),
                    "--cap-drop".to_string(), "ALL".to_string(),
                ]);
                for cap in &options.capabilities {
                    args.extend(vec!["--cap-add".to_string(), cap.clone()]);
                }
            }
            IsolationLevel::Medium => {
                args.extend(vec![
                    "--unshare-user".to_string(),
                    "--unshare-ipc".to_string(),
                    "--unshare-pid".to_string(),
                    "--unshare-net".to_string(),
                ]);
            }
            IsolationLevel::Minimal => {}
        }

        args.extend(vec!["--dev".to_string(), "/dev".to_string()]);
        args.extend(vec!["--proc".to_string(), "/proc".to_string()]);
        args.extend(vec!["--tmpfs".to_string(), "/tmp".to_string()]);
        args.extend(vec!["--tmpfs".to_string(), "/var/tmp".to_string()]);

        for tmpfs in &options.tmpfs_paths {
            args.extend(vec!["--tmpfs".to_string(), tmpfs.clone()]);
        }

        let essential_ro_binds = ["/usr", "/bin", "/lib", "/lib64", "/sbin", "/etc"];
        for path in essential_ro_binds {
            if Path::new(path).exists() {
                args.extend(vec!["--ro-bind".to_string(), path.to_string(), path.to_string()]);
            }
        }

        for (host, container) in &options.ro_bind_paths {
            if Path::new(host).exists() {
                args.extend(vec!["--ro-bind".to_string(), host.clone(), container.clone()]);
            }
        }

        for (host, container, flags) in &options.bind_paths {
            if Path::new(host).exists() {
                let bind_type = flags.as_deref().unwrap_or("--bind");
                args.extend(vec![bind_type.to_string(), host.clone(), container.clone()]);
            }
        }

        if options.allow_network {
            args.push("--share-net".to_string());
        } else {
            args.push("--unshare-net".to_string());
        }

        if options.allow_home {
            if let Some(home) = dirs::home_dir() {
                let h = home.to_string_lossy().to_string();
                args.extend(vec!["--bind".to_string(), h.clone(), h]);
            }
        } else {
            args.extend(vec!["--tmpfs".to_string(), "/home".to_string()]);
            args.extend(vec!["--mkdir".to_string(), "/home/sandbox".to_string()]);
            args.extend(vec!["--setenv".to_string(), "HOME".to_string(), "/home/sandbox".to_string()]);
        }

        if let Some(ref dir) = options.working_dir {
            args.extend(vec!["--bind".to_string(), dir.clone(), dir.clone()]);
            args.extend(vec!["--chdir".to_string(), dir.clone()]);
        } else {
            args.extend(vec!["--chdir".to_string(), "/tmp".to_string()]);
        }

        if let Some(uid) = options.uid {
            args.extend(vec!["--uid".to_string(), uid.to_string()]);
        }
        if let Some(gid) = options.gid {
            args.extend(vec!["--gid".to_string(), gid.to_string()]);
        }
        if let Some(ref hostname) = options.hostname {
            args.extend(vec!["--hostname".to_string(), hostname.clone()]);
        }

        args.extend(vec!["--setenv".to_string(), "PATH".to_string(), "/usr/bin:/bin:/usr/sbin:/sbin".to_string()]);

        for (key, val) in &options.env_vars {
            args.extend(vec!["--setenv".to_string(), key.clone(), val.clone()]);
        }

        args.push("--".to_string());
        args.extend(command.to_vec());

        args
    }

    fn _extract_warnings(&self, stdout: &str, stderr: &str) -> Vec<String> {
        let mut warnings = Vec::new();
        let combined = format!("{}{}", stdout, stderr);
        let patterns = ["warning:", "caution:", "deprecated", "bwrap:"];
        for line in combined.lines() {
            let line_lower = line.to_lowercase();
            if patterns.iter().any(|p| line_lower.contains(p)) {
                warnings.push(line.trim().to_string());
            }
        }
        warnings
    }

    fn _extract_errors(&self, stderr: &str) -> Vec<String> {
        let mut errors = Vec::new();
        let patterns = ["error:", "failed:", "cannot", "unable to", "not found"];
        for line in stderr.lines() {
            let line_lower = line.to_lowercase();
            if patterns.iter().any(|p| line_lower.contains(p)) {
                errors.push(line.trim().to_string());
            }
        }
        errors
    }
}
