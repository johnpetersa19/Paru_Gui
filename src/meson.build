pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'paru_gui'
gnome = import('gnome')

resources = gnome.compile_resources('paru_gui',
  'paru_gui.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  source_dir: '.',
  dependencies: files(
    '../window.ui',
    'ui/screens/welcome_screen.ui',
    'ui/screens/content_view.ui',
    'ui/screens/pkgbuild_review.ui',
    'ui/screens/upstream_update.ui',
    'ui/components/empty_state.ui',
    'ui/components/error_dialog.ui',
    'ui/components/file_chooser_dialog.ui',
    'ui/components/Keyboard_Shortcuts.ui',
    'ui/components/search_bar.ui',
    'ui/style.css',
    'ui/image_fixes.css',
    'ui/screens/pkgbuild-review.css'
  )
)

paru_gui_sources = [
  'gear/__init__.py',
  'gear/error_handler.py',
  'gear/file_utils.py',
  'gear/history_manager.py',
  'gear/lazy_cache_manager.py',
  'gear/main.py',
  'gear/pkgbuild_analyzer.py',
  'gear/preferences_manager.py',
  'gear/sandboxing.py',
  'gear/security_analyzer.py',
  'gear/signature_verifier.py',
  'gear/terminal_manager.py',
  'gear/tour_guide.py',
  'gear/upstream_checker.py',
  '../window.py',
  'ui/__init__.py',
  'ui/components/__init__.py',
  'ui/components/command_assistant.py',
  'ui/components/empty_state.py',
  'ui/components/error_dialog.py',
  'ui/components/file_chooser_dialog.py',
  'ui/components/Keyboard_Shortcuts.ui',
  'ui/components/search_bar.py',
  'ui/dialogs/__init__.py',
  'ui/dialogs/conflict_resolver.py',
  'ui/dialogs/pkgbuild_builder.py',
  'ui/managers/__init__.py',
  'ui/managers/action_handlers.py',
  'ui/managers/content_view_manager.py',
  'ui/managers/file_operations.py',
  'ui/managers/preferences_dialog_manager.py',
  'ui/managers/search_manager.py',
  'ui/managers/ui_manager.py',
  'ui/screens/__init__.py',
  'ui/screens/content_view.py',
  'ui/screens/pkgbuild_review_dialog.py',
  'ui/screens/upstream_update.py',
  'ui/screens/welcome_screen.py',
]

install_data(paru_gui_sources, install_dir: moduledir)
install_subdir('ui', install_dir: moduledir)
install_subdir('gear', install_dir: moduledir)