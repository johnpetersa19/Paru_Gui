application_id = 'org.gnome.painel_paru'

scalable_icon = 'hicolor/scalable/apps/' + application_id + '.svg'
symbolic_icon = 'hicolor/symbolic/apps/' + application_id + '-symbolic.svg'

icon_scalable_dir = get_option('datadir') / 'icons' / 'hicolor' / 'scalable' / 'apps'
icon_symbolic_dir = get_option('datadir') / 'icons' / 'hicolor' / 'symbolic' / 'apps'

# Instala ícone principal (obrigatório)
if files(scalable_icon).length() > 0
  install_data(scalable_icon, install_dir: icon_scalable_dir)
else
  error('Ícone SVG não encontrado: ' + scalable_icon + '\nCrie o arquivo no diretório data/icons/')
endif

# Instala ícone simbólico (opcional)
if files(symbolic_icon).length() > 0
  install_data(symbolic_icon, install_dir: icon_symbolic_dir)
endif