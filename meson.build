project('painel_paru', 'c',
  version: '0.1.0',
  meson_version: '>=0.57.0',
  default_options: ['warning_level=1', 'c_std=c11'])

# Diretórios
prefix = get_option('prefix')
datadir = join_paths(prefix, 'share')
bindir = join_paths(prefix, 'bin')
pkgdatadir = join_paths(datadir, meson.project_name())
moduledir = pkgdatadir / 'painel_paru'

gnome = import('gnome')
i18n = import('i18n')

# Recursos UI - CORRIGIDO: Adicionado devel_preferences.ui e verificado todos os caminhos
resources = files(
  'src/gtk/help-overlay.ui',
  'src/gtk/initial_screen.ui',
  'src/gtk/content_detection/pkgbuild_card.ui',
  'src/gtk/content_detection/packages_card.ui',
  'src/gtk/content_detection/patches_card.ui',
  'src/gtk/content_detection/empty_card.ui',
  'src/gtk/preferences/debug_preferences.ui',
  'src/gtk/preferences/devel_preferences.ui',  # CORREÇÃO: Adicionado arquivo faltando
  'src/gtk/conflict_resolver/conflict_dialog.ui'
)

# Compila GResource - CORRIGIDO: Restaurado dependencies: resources
gnome.compile_resources('painel_paru',
  'src/painel_paru.gresource.xml',
  c_name: 'org_gnome_painel_paru',
  dependencies: resources,  # CORREÇÃO: Dependência dos recursos restaurada
  install_dir: join_paths(datadir, 'glib-2.0', 'resources')
)

# Configuração
python = find_program('python3', required: true)
conf = configuration_data()
conf.set('PYTHON', python.full_path()) # CORREÇÃO: Usando full_path() em vez de path()
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(prefix, get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

# Executável
configure_file(
  input: 'src/painel_paru.in',
  output: 'painel_paru',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

# Fontes do módulo
painel_paru_sources = files(
  'src/painel_paru/__init__.py',
  'src/painel_paru/main.py',
  'src/painel_paru/window.py',
  'src/painel_paru/ui_builder.py',          # Arquivo adicionado
  'src/painel_paru/terminal_manager.py',    # Arquivo adicionado
  'src/painel_paru/preferences_manager.py',
  'src/painel_paru/menu_manager.py',        # Arquivo adicionado
  'src/painel_paru/action_manager.py',      # Arquivo adicionado
  'src/painel_paru/handlers.py',            # ARQUIVO CRÍTICO ADICIONADO (corrigindo o erro)
  'src/painel_paru/content_detector.py',
  'src/painel_paru/conflict_resolver.py',
  'src/painel_paru/navigation.py',          # Arquivo adicionado
  'src/painel_paru/build_manager.py',
  'src/painel_paru/aur_downloader.py',
  'src/painel_paru/paru_runner.py',
  'src/painel_paru/terminal.py',
  'src/painel_paru/utils.py'                # Arquivo adicionado
)
install_data(painel_paru_sources, install_dir: moduledir)

# Schema
install_data('data/org.gnome.painel_paru.gschema.xml',
  install_dir: join_paths(datadir, 'glib-2.0', 'schemas')
)
meson.add_install_script('glib-compile-schemas', join_paths(datadir, 'glib-2.0', 'schemas'))