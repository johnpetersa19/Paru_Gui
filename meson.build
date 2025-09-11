project('painel_paru', 'c',
  version: '0.1.0',
  meson_version: '>=0.57.0',
  default_options: ['warning_level=1', 'c_std=c11'])

# Diretórios principais
prefix = get_option('prefix')
datadir = join_paths(prefix, 'share')
bindir = join_paths(prefix, 'bin')
pkgdatadir = join_paths(datadir, meson.project_name())
moduledir = pkgdatadir / 'painel_paru'

# Importações de módulos Meson
gnome = import('gnome')
i18n = import('i18n')

# Lista de arquivos de interface gráfica (UI) para inclusão no GResource
resources = files(
  'src/gtk/help-overlay.ui',
  'src/gtk/initial_screen.ui',
  'src/gtk/content_detection/pkgbuild_card.ui',
  'src/gtk/content_detection/packages_card.ui',
  'src/gtk/content_detection/patches_card.ui',
  'src/gtk/content_detection/empty_card.ui',
  'src/gtk/preferences/debug_preferences.ui',
  'src/gtk/preferences/devel_preferences.ui',  # Adicionado: interface de preferências de desenvolvimento
  'src/gtk/conflict_resolver/conflict_dialog.ui'
)

# Compilação do recurso GResource com dependência explícita nos arquivos UI
gnome.compile_resources('painel_paru',
  'src/painel_paru.gresource.xml',
  c_name: 'org_gnome_painel_paru',
  dependencies: resources
)

# Localização (internacionalização)
i18n.gettext('painel_paru', preset: 'glib')

# Programa Python encontrado
python = find_program('python3', required: true)

# Dados de configuração para substituição no executável
conf = configuration_data()
conf.set('PYTHON', python.full_path())           # Caminho absoluto ao interpretador Python
conf.set('VERSION', meson.project_version())     # Versão do projeto
conf.set('localedir', join_paths(prefix, get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

# Gerar script de inicialização com substituições
configure_file(
  input: 'src/painel_paru.in',
  output: 'painel_paru',
  configuration: conf,
  install: true,
  install_dir: bindir,
  install_mode: 'r-xr-xr-x'
)

# ✅ CORREÇÃO: Instala o diretório inteiro mantendo a estrutura, especialmente a pasta handlers/
install_subdir('src/painel_paru', install_dir: moduledir)

# Instalação do esquema de configuração GLib
schema_file = 'data/org.gnome.painel_paru.gschema.xml'
install_data(schema_file,
  install_dir: join_paths(datadir, 'glib-2.0', 'schemas')
)

# Validação opcional do esquema (se glib-compile-schemas estiver disponível)
compile_schemas = find_program('glib-compile-schemas', required: false)

if compile_schemas.found()
  # Script pós-instalação para compilar esquemas
  meson.add_install_script(
    compile_schemas.full_path(),
    join_paths(datadir, 'glib-2.0', 'schemas')
  )

  # Teste de validação do schema
  test('Validate schema file',
    compile_schemas,
    args: ['--strict', '--dry-run', meson.project_source_root() / 'data']
  )
endif

# Subdiretórios adicionais
subdir('data/icons')