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
    'ui/components/help-overlay.ui',
    'ui/components/search_bar.ui',
    'ui/style.css',
    'ui/screens/pkgbuild-review.css'
  )
)

python = import('python')
py_path = python.find_installation('python3').full_path()

conf = configuration_data()
conf.set('PYTHON', py_path)
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'paru_gui.in',
  output: 'paru_gui',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

paru_gui_sources = [
  'paru_gui/__init__.py',
  'paru_gui/error_handler.py',
  'paru_gui/file_utils.py',
  'paru_gui/history_manager.py',
  'paru_gui/lazy_cache_manager.py',
  'paru_gui/main.py',
  'paru_gui/pkgbuild_analyzer.py',
  'paru_gui/preferences_manager.py',
  'paru_gui/sandboxing.py',
  'paru_gui/security_analyzer.py',
  'paru_gui/signature_verifier.py',
  'paru_gui/terminal_manager.py',
  'paru_gui/tour_guide.py',
  'paru_gui/upstream_checker.py',
  'ui/__init__.py',
  'ui/components/__init__.py',
  'ui/components/command_assistant.py',
  'ui/components/empty_state.py',
  'ui/components/error_dialog.py',
  'ui/components/file_chooser_dialog.py',
  'ui/components/help_overlay.py',
  'ui/components/search_bar.py',
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

window_py_source = [
  '../window.py',
]

install_data(paru_gui_sources, install_dir: moduledir)
install_data(window_py_source, install_dir: moduledir)
install_subdir('ui', install_dir: moduledir)
