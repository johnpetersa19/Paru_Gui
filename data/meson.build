desktop_file = i18n.merge_file(
        input: 'org.gnome.painel_paru.desktop.in',
        output: 'org.gnome.painel_paru.desktop',
        type: 'desktop',
        po_dir: '../po',
        install: true,
        install_dir: get_option('datadir') / 'applications'
)
desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif

appstream_file = i18n.merge_file(
        input: 'org.gnome.painel_paru.metainfo.xml.in',
        output: 'org.gnome.painel_paru.metainfo.xml',
        po_dir: '../po',
        install: true,
        install_dir: get_option('datadir') / 'metainfo'
)
appstreamcli = find_program('appstreamcli', required: false, disabler: true)
if appstreamcli.found()
  test('Validate appstream file', appstreamcli,
       args: ['validate', '--no-net', '--explain', appstream_file])
endif

install_data('org.gnome.painel_paru.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas'
)

compile_schemas = find_program('glib-compile-schemas', required: false, disabler: true)
if compile_schemas.found()
  test('Validate schema file',
       compile_schemas,
       args: ['--strict', '--dry-run', meson.current_build_dir()])
endif

service_conf = configuration_data()
service_conf.set('bindir', get_option('prefix') / get_option('bindir'))
configure_file(
  input: 'org.gnome.painel_paru.service.in',
  output: 'org.gnome.painel_paru.service',
  configuration: service_conf,
  install_dir: get_option('datadir') / 'dbus-1' / 'services'
)

subdir('icons')