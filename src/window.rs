/* window.rs
 *
 * Copyright 2026 Unknown
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

use gtk::prelude::*;
use adw::subclass::prelude::*;
use gtk::{gio, glib};
use std::cell::RefCell;
use crate::config::VERSION;

use crate::gear::preferences_manager::PreferencesManager;
use crate::gear::history_manager::HistoryManager;
use crate::gear::tour_guide::TourGuide;
use crate::gear::terminal_manager::TerminalManager;
use crate::gear::chroot_manager::ChrootManager;
use crate::gear::error_handler::ErrorHandler;
use crate::gear::file_utils::FileUtils;
use crate::gear::lazy_cache_manager::LazyCacheManager;
use crate::gear::paru_stats_manager::ParuStatsManager;
use crate::gear::pkgbuild_analyzer::PKGBUILDAnalyzer;
use crate::gear::repo_manager::RepoManager;
use crate::gear::sandboxing::SandboxManager;
use crate::gear::security_analyzer::SecurityAnalyzer;
use crate::gear::signature_verifier::SignatureVerifier;
use crate::gear::upstream_checker::UniversalUpstreamChecker;

use crate::ui::managers::ui_manager::UiManager;
use crate::ui::managers::action_handlers::ActionHandlers;
use crate::ui::managers::content_view_manager::ContentViewManager;
use crate::ui::managers::file_operations::FileOperations;
use crate::ui::managers::preferences_dialog_manager::PreferencesDialogManager;
use crate::ui::managers::search_manager::SearchManager;

mod imp {
    use super::*;

    #[derive(Debug, Default, gtk::CompositeTemplate)]
    #[template(resource = "/org/gnome/Example/window.ui")]
    pub struct ParuGuiWindow {
        // Template widgets
        #[template_child]
        pub main_stack: TemplateChild<gtk::Stack>,
        #[template_child]
        pub search_entry: TemplateChild<gtk::SearchEntry>,
        #[template_child]
        pub notification_revealer: TemplateChild<gtk::Revealer>,
        #[template_child]
        pub notification_label: TemplateChild<gtk::Label>,
        #[template_child]
        pub status_label: TemplateChild<gtk::Label>,
        #[template_child]
        pub status_spinner: TemplateChild<gtk::Spinner>,
        #[template_child]
        pub content_cards: TemplateChild<gtk::FlowBox>,
        #[template_child]
        pub recent_dirs_flowbox: TemplateChild<gtk::FlowBox>,

        // Backend Managers (Wrapped in RefCell for mutability in subclass methods)
        pub preferences: RefCell<Option<PreferencesManager>>,
        pub history: RefCell<Option<HistoryManager>>,
        pub tour_guide: RefCell<Option<TourGuide>>,
        pub terminal: RefCell<Option<TerminalManager>>,
        pub chroot: RefCell<Option<ChrootManager>>,
        pub error_handler: RefCell<Option<ErrorHandler>>,
        pub file_utils: RefCell<Option<FileUtils>>,
        pub lazy_cache: RefCell<Option<LazyCacheManager<String>>>,
        pub paru_stats: RefCell<Option<ParuStatsManager>>,
        pub pkgbuild_analyzer: RefCell<Option<PKGBUILDAnalyzer>>,
        pub repo_manager: RefCell<Option<RepoManager>>,
        pub sandbox_manager: RefCell<Option<SandboxManager>>,
        pub security_analyzer: RefCell<Option<SecurityAnalyzer>>,
        pub signature_verifier: RefCell<Option<SignatureVerifier>>,
        pub upstream_checker: RefCell<Option<UniversalUpstreamChecker>>,

        // UI Managers
        pub ui_manager: RefCell<Option<UiManager>>,
        pub action_handlers: RefCell<Option<ActionHandlers>>,
        pub content_view_manager: RefCell<Option<ContentViewManager>>,
        pub file_operations: RefCell<Option<FileOperations>>,
        pub preferences_dialog: RefCell<Option<PreferencesDialogManager>>,
        pub search_manager: RefCell<Option<SearchManager>>,
    }

    #[glib::object_subclass]
    impl ObjectSubclass for ParuGuiWindow {
        const NAME: &'static str = "ParuGuiWindow";
        type Type = super::ParuGuiWindow;
        type ParentType = adw::ApplicationWindow;

        fn class_init(klass: &mut Self::Class) {
            klass.bind_template();
            klass.bind_template_callbacks();
        }

        fn instance_init(obj: &glib::subclass::InitializingObject<Self>) {
            obj.init_template();
        }
    }

    #[gtk::template_callbacks]
    impl ParuGuiWindow {
        #[template_callback]
        fn on_select_file_clicked(&self, _button: &gtk::Button) {
            println!("Select file clicked");
            // Integration with FileOperations manager would go here
        }

        #[template_callback]
        fn on_select_folder_clicked(&self, _button: &gtk::Button) {
            println!("Select folder clicked");
        }

        #[template_callback]
        fn on_search_changed(&self, entry: &gtk::SearchEntry) {
            let _text = entry.text().to_string();
            // Integration with SearchManager would go here
        }

        #[template_callback]
        fn on_search_activate(&self, _entry: &gtk::SearchEntry) {
            println!("Search activated");
        }

        #[template_callback]
        fn on_system_packages_clicked(&self, _button: &gtk::Button) {
            self.main_stack.set_visible_child_name("content");
        }

        #[template_callback]
        fn on_preferences_clicked(&self, _button: &gtk::Button) {
            println!("Preferences clicked");
        }

        #[template_callback]
        fn on_tour_clicked(&self, _button: &gtk::Button) {
            if let Some(tg) = self.tour_guide.borrow().as_ref() {
                tg.restart_tour();
            }
        }

        #[template_callback]
        fn on_back_to_welcome_clicked(&self, _button: &gtk::Button) {
            self.main_stack.set_visible_child_name("welcome");
        }

        #[template_callback]
        fn on_nav_back_clicked(&self, _button: &gtk::Button) {
            println!("Nav back clicked");
        }

        #[template_callback]
        fn on_nav_forward_clicked(&self, _button: &gtk::Button) {
            println!("Nav forward clicked");
        }

        #[template_callback]
        fn on_refresh_content_clicked(&self, _button: &gtk::Button) {
            println!("Refresh content clicked");
        }

        #[template_callback]
        fn on_view_switcher_clicked(&self, _button: &gtk::Button) {
            println!("View switcher clicked");
        }

        #[template_callback]
        fn on_help_clicked(&self, _button: &gtk::Button) {
            println!("Help clicked");
        }

        #[template_callback]
        fn on_notification_response(&self, _info_bar: &glib::Object, _response_id: i32) {
            self.notification_revealer.set_reveal_child(false);
        }

        #[template_callback]
        fn on_stack_changed(&self, stack: &gtk::Stack, _param: &glib::ParamSpec) {
            if let Some(name) = stack.visible_child_name() {
                println!("Stack changed to: {}", name);
            }
        }

        #[template_callback]
        fn on_primary_action_clicked(&self, _button: &gtk::Button) {
            println!("Primary action clicked");
        }

        #[template_callback]
        fn on_cancel_operation_clicked(&self, _button: &gtk::Button) {
            println!("Cancel operation clicked");
        }

        #[template_callback]
        fn on_background_operation_clicked(&self, _button: &gtk::Button) {
            println!("Background operation clicked");
        }

        #[template_callback]
        fn on_refresh_updates_clicked(&self, _button: &gtk::Button) {
            println!("Refresh updates clicked");
        }
    }

    impl ObjectImpl for ParuGuiWindow {
        fn constructed(&self) {
            self.parent_constructed();

            // Initialize managers
            *self.preferences.borrow_mut() = Some(PreferencesManager::new());
            *self.history.borrow_mut() = HistoryManager::new(None).ok();
            *self.tour_guide.borrow_mut() = Some(TourGuide::new());
            *self.terminal.borrow_mut() = Some(TerminalManager::new());
            *self.chroot.borrow_mut() = Some(ChrootManager::new());
            *self.error_handler.borrow_mut() = Some(ErrorHandler::new(VERSION));
            *self.file_utils.borrow_mut() = Some(FileUtils::new());
            *self.lazy_cache.borrow_mut() = Some(LazyCacheManager::new(100, 3600));
            *self.paru_stats.borrow_mut() = Some(ParuStatsManager::new());
            *self.pkgbuild_analyzer.borrow_mut() = Some(PKGBUILDAnalyzer::new());
            *self.repo_manager.borrow_mut() = Some(RepoManager::new());
            *self.sandbox_manager.borrow_mut() = SandboxManager::new().ok();
            *self.security_analyzer.borrow_mut() = Some(SecurityAnalyzer::new());
            *self.signature_verifier.borrow_mut() = Some(SignatureVerifier::new(None));
            *self.upstream_checker.borrow_mut() = Some(UniversalUpstreamChecker::new());

            *self.ui_manager.borrow_mut() = Some(UiManager::new());
            *self.action_handlers.borrow_mut() = Some(ActionHandlers::new());
            *self.content_view_manager.borrow_mut() = Some(ContentViewManager::new());
            *self.file_operations.borrow_mut() = Some(FileOperations::new());
            *self.preferences_dialog.borrow_mut() = Some(PreferencesDialogManager::new());
            *self.search_manager.borrow_mut() = Some(SearchManager::new());

            println!("ParuGuiWindow constructed and managers initialized");
        }
    }
    impl WidgetImpl for ParuGuiWindow {}
    impl WindowImpl for ParuGuiWindow {}
    impl ApplicationWindowImpl for ParuGuiWindow {}
    impl AdwApplicationWindowImpl for ParuGuiWindow {}
}

glib::wrapper! {
    pub struct ParuGuiWindow(ObjectSubclass<imp::ParuGuiWindow>)
        @extends gtk::Widget, gtk::Window, gtk::ApplicationWindow, adw::ApplicationWindow,
        @implements gio::ActionGroup, gio::ActionMap;
}

impl ParuGuiWindow {
    pub fn new<P: IsA<gtk::Application>>(application: &P) -> Self {
        glib::Object::builder()
            .property("application", application)
            .build()
    }

    pub fn show_notification(&self, message: &str) {
        let imp = self.imp();
        imp.notification_label.set_label(message);
        imp.notification_revealer.set_reveal_child(true);
    }
}
