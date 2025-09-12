# window_aur.py
from gi.repository import Gtk, Adw
import gettext

_ = gettext.gettext

class WindowAUR:
    """Módulo responsável pelas funcionalidades relacionadas ao AUR (Arch User Repository)"""

    def _setup_aur_buttons(self, builder):
        """Configura os botões da tela de pasta vazia relacionados ao AUR"""
        aur_search = builder.get_object("aur_search")
        download_button = builder.get_object("download_button")
        search_button = builder.get_object("search_button")

        if aur_search and download_button:
            # Atualiza botão de download conforme digitação
            aur_search.connect("changed", lambda entry:
                download_button.set_sensitive(bool(entry.get_text().strip())))

            # Configura busca ao pressionar Enter
            aur_search.connect("activate", lambda _: download_button.emit("clicked"))

        # Configura botão de download
        if download_button:
            download_button.connect("clicked", lambda _: self._download_pkgbuild(
                aur_search.get_text(),
                self.builder.get_object("ssh_toggle").get_active() if self.builder.get_object("ssh_toggle") else False,
                self.builder.get_object("comments_toggle").get_active() if self.builder.get_object("comments_toggle") else False
            ))

        # Configura botão de busca se existir
        if search_button and aur_search:
            search_button.connect("clicked", lambda _: self._search_aur_package(aur_search.get_text()))

    def _download_pkgbuild(self, pkg_name, use_ssh, show_comments):
        """Baixa PKGBUILD do AUR"""
        if not pkg_name.strip():
            self.terminal.append(_("❌ Nome do pacote não pode ser vazio."), "error")
            return

        try:
            self.terminal.append(f"📥 {_('Baixando PKGBUILD de')} '{pkg_name}'...", "progress")
            AurDownloader.start_download(pkg_name, self.content_path, use_ssh, self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao baixar PKGBUILD:')} {str(e)}", "error")
            print(f"❌ Erro ao baixar PKGBUILD: {e}")

    def _search_aur_package(self, query):
        """Busca um pacote no AUR"""
        if not query.strip():
            self.terminal.append(_("⚠️ Digite um nome para buscar no AUR."), "info")
            return

        try:
            self.terminal.append(f"🔍 {_('Buscando no AUR:')} {query}...", "progress")
            # Comando para buscar no AUR
            ParuRunner.run_command(["paru", "-Ss", query], self.terminal.append)
        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao buscar no AUR:')} {str(e)}", "error")
            print(f"❌ Erro ao buscar no AUR: {e}")

    def search_packages(self, query):
        """Pesquisa pacotes no AUR"""
        if not query.strip():
            return

        self.terminal.append(f"🔍 {_('Pesquisando pacotes:')} {query}...", "info")
        ParuRunner.run_command(["paru", "-Ss", query], self.terminal.append)

    def show_pkgbuild_review_dialog(self, pkgbuild_path, callback):
        """Mostra diálogo de revisão do PKGBUILD"""
        try:
            # Cria um diálogo modal
            dialog = Adw.Window(
                transient_for=self,
                modal=True,
                title=_("Revisão do PKGBUILD"),
                default_width=1000,
                default_height=700
            )

            # Cria o conteúdo principal
            content = Adw.ToolbarView()
            dialog.set_content(content)

            # Header bar
            header = Adw.HeaderBar()
            content.add_top_bar(header)

            # Botão de fechar
            close_button = Gtk.Button(
                icon_name="window-close-symbolic",
                tooltip_text=_("Fechar")
            )
            close_button.connect("clicked", lambda _: dialog.close())
            header.pack_end(close_button)

            # Container principal
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            main_box.set_margin_start(10)
            main_box.set_margin_end(10)
            main_box.set_margin_top(10)
            main_box.set_margin_bottom(10)
            content.set_content(main_box)

            # Divisor horizontal
            paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            paned.set_vexpand(True)

            # Painel ESQUERDA: PKGBUILD atual
            left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            left_label = Gtk.Label(
                label=_("PKGBUILD Atual"),
                xalign=0,
                css_classes=["heading"]
            )
            left_box.append(left_label)

            left_scroll = Gtk.ScrolledWindow()
            left_scroll.set_vexpand(True)

            left_text = Gtk.TextView(
                editable=False,
                monospace=True,
                wrap_mode=Gtk.WrapMode.WORD
            )
            left_buffer = left_text.get_buffer()

            # Carrega conteúdo do PKGBUILD atual
            try:
                with open(pkgbuild_path, 'r') as f:
                    content = f.read()
                    left_buffer.set_text(content)
            except Exception as e:
                left_buffer.set_text(f"Erro ao ler PKGBUILD: {str(e)}")

            left_scroll.set_child(left_text)
            left_box.append(left_scroll)

            # Painel DIREITA: PKGBUILD novo (ou fonte do AUR)
            right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            right_label = Gtk.Label(
                label=_("PKGBUILD do AUR"),
                xalign=0,
                css_classes=["heading"]
            )
            right_box.append(right_label)

            right_scroll = Gtk.ScrolledWindow()
            right_scroll.set_vexpand(True)

            right_text = Gtk.TextView(
                editable=False,
                monospace=True,
                wrap_mode=Gtk.WrapMode.WORD
            )
            right_buffer = right_text.get_buffer()

            # Botões de ação
            buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            buttons_box.set_halign(Gtk.Align.END)

            cancel_btn = Gtk.Button(label=_("Cancelar"))
            cancel_btn.connect("clicked", lambda _: dialog.close())

            continue_btn = Gtk.Button(label=_("Continuar Build"))
            continue_btn.add_css_class("suggested-action")
            continue_btn.connect("clicked", lambda _: {
                dialog.close(),
                callback(True) if callback else None
            })

            buttons_box.append(cancel_btn)
            buttons_box.append(continue_btn)

            # Adiciona os painéis ao Paned
            paned.set_start_child(left_box)
            paned.set_end_child(right_box)
            paned.set_position(500)  # Posição inicial do divisor

            main_box.append(paned)
            main_box.append(buttons_box)

            dialog.present()

        except Exception as e:
            self.terminal.append(f"❌ {_('Erro ao mostrar diálogo de revisão:')} {str(e)}", "error")
            print(f"❌ Erro ao mostrar diálogo de revisão: {e}")
