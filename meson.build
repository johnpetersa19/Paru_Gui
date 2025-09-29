project('paru_gui',
  version: '2.7.0',
  meson_version: '>= 1.0.0',
  default_options: ['warning_level=2', 'werror=false'],
)

i18n = import('i18n')
gnome = import('gnome')
python = import('python')

py_installation = python.find_installation('python3', required: true)
py_dependency = py_installation.dependency()

pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

conf = configuration_data()
conf.set('pkgdatadir', pkgdatadir)
conf.set('PYTHON', py_installation.full_path())
conf.set('VERSION', meson.project_version())

configure_file(
  input: 'src/paru_gui.in',
  output: 'paru_gui',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

subdir('data')
subdir('src')
subdir('po')

gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
