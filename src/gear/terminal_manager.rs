use std::collections::HashMap;
use std::process::{Command, Child};
use std::env;
use which::which;
use shlex;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TerminalType {
    GnomeTerminal,
    Konsole,
    Xterm,
    Alacritty,
    Kitty,
    Terminator,
    Tilix,
    MateTerminal,
    XfceTerminal,
}

impl TerminalType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::GnomeTerminal => "gnome-terminal",
            Self::Konsole => "konsole",
            Self::Xterm => "xterm",
            Self::Alacritty => "alacritty",
            Self::Kitty => "kitty",
            Self::Terminator => "terminator",
            Self::Tilix => "tilix",
            Self::MateTerminal => "mate-terminal",
            Self::XfceTerminal => "xfce4-terminal",
        }
    }
}

#[derive(Debug)]
pub struct TerminalConfig {
    pub execute: Vec<String>,
    pub title: Vec<String>,
    pub working_dir: Vec<String>,
    pub hold: Vec<String>,
    pub new_window: Vec<String>,
    pub new_tab: Vec<String>,
}

#[derive(Debug)]
pub struct TerminalManager {
    pub system_terminal_emulator: String,
    pub terminal_type: Option<TerminalType>,
    terminal_configs: HashMap<String, TerminalConfig>,
}

impl TerminalManager {
    pub fn new() -> Self {
        let mut manager = Self {
            system_terminal_emulator: String::new(),
            terminal_type: None,
            terminal_configs: HashMap::new(),
        };
        manager._initialize_terminal_configs();
        manager._detect_system_terminal();
        manager
    }

    fn _initialize_terminal_configs(&mut self) {
        let configs = vec![
            (TerminalType::GnomeTerminal, TerminalConfig {
                execute: vec!["--".to_string(), "bash".to_string(), "-c".to_string()],
                title: vec!["--title".to_string()],
                working_dir: vec!["--working-directory".to_string()],
                hold: vec![],
                new_window: vec!["--window".to_string()],
                new_tab: vec!["--tab".to_string()],
            }),
            (TerminalType::Konsole, TerminalConfig {
                execute: vec!["-e".to_string(), "bash".to_string(), "-c".to_string()],
                title: vec!["-p".to_string(), "tabtitle".to_string()],
                working_dir: vec!["--workdir".to_string()],
                hold: vec!["--hold".to_string()],
                new_window: vec!["--new-window".to_string()],
                new_tab: vec!["--new-tab".to_string()],
            }),
            // Add more as needed...
        ];

        for (t, cfg) in configs {
            self.terminal_configs.insert(t.as_str().to_string(), cfg);
        }
    }

    fn _detect_system_terminal(&mut self) {
        if let Ok(term) = env::var("XDG_TERMINAL_EMULATOR") {
            if which(&term).is_ok() {
                self.system_terminal_emulator = term.clone();
                self.terminal_type = self._get_terminal_type(&term);
                return;
            }
        }

        let fallbacks = vec![
            TerminalType::Alacritty,
            TerminalType::Kitty,
            TerminalType::GnomeTerminal,
            TerminalType::Konsole,
            TerminalType::Xterm,
        ];

        for t in fallbacks {
            if which(t.as_str()).is_ok() {
                self.system_terminal_emulator = t.as_str().to_string();
                self.terminal_type = Some(t);
                return;
            }
        }

        self.system_terminal_emulator = "xterm".to_string();
        self.terminal_type = Some(TerminalType::Xterm);
    }

    fn _get_terminal_type(&self, name: &str) -> Option<TerminalType> {
        if name.contains("gnome-terminal") { Some(TerminalType::GnomeTerminal) }
        else if name.contains("konsole") { Some(TerminalType::Konsole) }
        else if name.contains("alacritty") { Some(TerminalType::Alacritty) }
        else if name.contains("kitty") { Some(TerminalType::Kitty) }
        else { None }
    }

    pub fn execute_command(
        &self,
        command: &[String],
        working_dir: Option<&str>,
        title: Option<&str>,
        hold_open: bool,
    ) -> Option<Child> {
        let terminal_cmd = self._build_terminal_command(command, working_dir, title, hold_open);
        
        let mut cmd = Command::new(&terminal_cmd[0]);
        cmd.args(&terminal_cmd[1..]);
        
        if let Some(dir) = working_dir {
            cmd.current_dir(dir);
        }

        cmd.spawn().ok()
    }

    fn _build_terminal_command(
        &self,
        command: &[String],
        working_dir: Option<&str>,
        title: Option<&str>,
        hold_open: bool,
    ) -> Vec<String> {
        let mut args = vec![self.system_terminal_emulator.clone()];
        
        if let Some(cfg) = self.terminal_configs.get(&self.system_terminal_emulator) {
            if let Some(t) = title {
                if !cfg.title.is_empty() {
                    args.extend(cfg.title.clone());
                    args.push(t.to_string());
                }
            }
            if let Some(dir) = working_dir {
                if !cfg.working_dir.is_empty() {
                    args.extend(cfg.working_dir.clone());
                    args.push(dir.to_string());
                }
            }
            if hold_open && !cfg.hold.is_empty() {
                args.extend(cfg.hold.clone());
            }
            
            if !cfg.execute.is_empty() {
                args.extend(cfg.execute.clone());
                let mut cmd_str = command.iter()
            .map(|s| shlex::try_quote(s).unwrap_or_else(|_| std::borrow::Cow::Borrowed(s)).into_owned())
            .collect::<Vec<_>>()
            .join(" ");
                if hold_open && cfg.hold.is_empty() {
                    cmd_str.push_str("; exec bash");
                }
                args.push(cmd_str);
            } else {
                args.extend(command.to_vec());
            }
        } else {
            args.extend(command.to_vec());
        }

        args
    }
}
