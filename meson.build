project('painel_paru', 'c',
  version: '0.1.0',
  meson_version: '>=0.57.0',
  default_options: ['warning_level=1', 'c_std=c11']
)

# Diretórios de instalação
prefix = get_option('prefix')
datadir = join_paths(prefix, 'share')
bindir = join_paths(prefix, 'bin')
pkgdatadir = join_paths(datadir, meson.project_name())
moduledir = pkgdatadir / 'painel_paru'

gnome = import('gnome')

# Lista completa de recursos UI para o GResource (como objetos File)
resources = files(
  'src/gtk/help-overlay.ui',
  'src/gtk/initial_screen.ui',
  'src/gtk/content_detection/pkgbuild_card.ui',
  'src/gtk/content_detection/packages_card.ui',
  'src/gtk/content_detection/patches_card.ui',
  'src/gtk/content_detection/empty_card.ui',
  'src/gtk/conflict_resolver/conflict_dialog.ui',
  'src/gtk/preferences/debug_preferences.ui'
)

# Configuração CORRETA do GResource usando gnome.compile_resources
# Instala no local padrão do GLib para recursos
gnome.compile_resources(
  'painel_paru',
  'data/painel_paru.gresource.xml',
  c_name: 'org_gnome_painel_paru',
  dependencies: resources,
  install_dir: join_paths(datadir, 'glib-2.0', 'resources')
)

# Configuração para painel_paru.in
conf = configuration_data()
conf.set('PYTHON', 'python3')
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(prefix, get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

# Gera o executável
configure_file(
  input: 'src/painel_paru.in',
  output: 'painel_paru',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

# Lista completa de fontes Python
painel_paru_sources = files(
  'src/__init__.py',
  'src/main.py',
  'src/window.py',
  'src/content_detector.py',
  'src/conflict_resolver.py',
  'src/preferences.py',
  'src/build_manager.py',
  'src/aur_downloader.py',
  'src/paru_runner.py',
  'src/terminal.py'
)

# Instala os módulos Python no local CORRETO
install_data(painel_paru_sources, install_dir: moduledir)

# Instala schemas de configuração
install_data('data/org.gnome.painel_paru.gschema.xml',
  install_dir: join_paths(datadir, 'glib-2.0', 'schemas')
)

# Pós-instalação para compilar schemas
meson.add_install_script('glib-compile-schemas', join_paths(datadir, 'glib-2.0', 'schemas'))