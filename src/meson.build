pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'paru_gui'
gnome = import('gnome')

# Adicionado extra_args para especificar o diretório-raiz dos recursos UI
gnome.compile_resources('paru_gui',
  'paru_gui.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  # O sourcedir aponta para 'ui', então os caminhos dentro do gresource.xml
  # (ex: 'screens/welcome_screen.ui') devem ser relativos a 'src/ui'.
  extra_args: ['--sourcedir=ui']
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
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

# Lista dos arquivos Python de nível superior do pacote paru_gui
paru_gui_top_level_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'error_handler.py',
  'file_utils.py',
  'history_manager.py',
  'pkgbuild_analyzer.py',
  'preferences_manager.py',
  'sandboxing.py',
  'security_analyzer.py',
  'terminal_manager.py',
  'tour_guide.py',
  'upstream_checker.py',
]

# Instala os arquivos Python de nível superior para o diretório do módulo
install_data(paru_gui_top_level_sources, install_dir: moduledir)

# CORREÇÃO CRÍTICA AQUI: Instala o subdiretório 'ui' DIRETAMENTE no diretório do módulo,
# para que a estrutura seja moduledir/ui/screens, e não moduledir/ui/ui/screens.
install_subdir(
  'ui',
  install_dir: moduledir
)