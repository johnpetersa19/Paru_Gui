#!/bin/bash

echo "🔧 Corrigindo meson.build: erro de ')' solto"

# Verifica se está na raiz
if [ ! -f "meson.build" ]; then
    echo "❌ Erro: Execute na raiz do projeto."
    exit 1
fi

# Faz backup
cp meson.build meson.build.bak
echo "✅ Backup feito: meson.build.bak"

# Remove linhas com ')' solto após comentários
sed -i '/# Compila GResource)/d' meson.build
sed -i '/# Recursos UI)/d' meson.build
sed -i '/^)$/d' meson.build

# Garante que não há ) solto no início de linha
sed -i '/^[[:space:]]*)[[:space:]]*$/d' meson.build

echo "✅ Linhas com ')' solto removidas"

# Define o bloco correto de recursos
cat << 'EOF' > /tmp/resources_fix.tmp
# Lista de arquivos UI
resources = files(
  'src/gtk/help-overlay.ui',
  'src/gtk/initial_screen.ui',
  'src/gtk/content_detection/pkgbuild_card.ui',
  'src/gtk/content_detection/packages_card.ui',
  'src/gtk/content_detection/patches_card.ui',
  'src/gtk/content_detection/empty_card.ui',
  'src/gtk/conflict_resolver/conflict_dialog.ui',
  'src/gtk/preferences/general_preferences.ui',
  'src/gtk/preferences/debug_preferences.ui',
  'src/gtk/preferences/devel_preferences.ui'
)

# Compila os recursos GResource
gnome.compile_resources(
  'painel_paru',
  'data/org.gnome.painel_paru.gresource.xml',
  sources: resources,
  c_name: 'org_gnome_painel_paru',
  export: true
)
EOF

# Encontra onde inserir (antes de 'python = find_program')
insert_line=$(grep -n "python = find_program" meson.build | cut -d: -f1 | head -1)

if [ -z "$insert_line" ]; then
    echo "❌ Não foi possível encontrar ponto de inserção."
    exit 1
fi

# Insere o bloco
sed -i "${insert_line}r /tmp/resources_fix.tmp" meson.build
rm -f /tmp/resources_fix.tmp

echo "✅ meson.build corrigido com sucesso!"
echo "➡️ O erro de ')' solto foi resolvido."
