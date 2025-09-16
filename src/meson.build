pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'paru_gui'
gnome = import('gnome')

# --- CORREÇÃO AQUI para GResource ---
# Adicionado extra_args para especificar o diretório-raiz dos recursos UI
gnome.compile_resources('paru_gui',
  'paru_gui.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  # O sourcedir agora aponta para 'ui', então os caminhos dentro do gresource.xml
  # devem ser relativos a 'ui', e não a 'src'.
  extra_args: ['--sourcedir=ui']
)
# --- FIM DA CORREÇÃO ---

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

paru_gui_sources = [
  '__init__.py',
  'main.py',
  'window.py',
]

install_data(paru_gui_sources, install_dir: moduledir)