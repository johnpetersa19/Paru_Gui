use gtk::prelude::*;
use adw::prelude::*;
use gtk::gio::Settings;
use std::sync::{Arc, Mutex};

#[derive(Debug)]
pub struct TourGuide {
    settings: Option<Settings>,
    current_tour_step: Arc<Mutex<i32>>,
    // We'll add more UI-related fields when integrating with the actual window
}

impl TourGuide {
    pub const SCHEMA_ID: &'static str = "org.gnome.paru-gui";
    pub const TOUR_COMPLETED_KEY: &'static str = "tour-completed";

    pub fn new() -> Self {
        let settings = Settings::new(Self::SCHEMA_ID);
        Self {
            settings: Some(settings),
            current_tour_step: Arc::new(Mutex::new(-1)),
        }
    }

    pub fn is_tour_completed(&self) -> bool {
        self.settings.as_ref()
            .map(|s| s.boolean(Self::TOUR_COMPLETED_KEY))
            .unwrap_or(false)
    }

    pub fn set_tour_completed(&self, completed: bool) {
        if let Some(s) = &self.settings {
            let _ = s.set_boolean(Self::TOUR_COMPLETED_KEY, completed);
        }
    }

    pub fn restart_tour(&self) {
        self.set_tour_completed(false);
        *self.current_tour_step.lock().unwrap() = 0;
        // In a real app, this would trigger UI signals
    }
}
