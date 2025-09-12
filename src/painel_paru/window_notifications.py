from gi.repository import Gtk, Gio, Adw
import gettext

_ = gettext.gettext

class WindowNotifications:
    """Gerencia o sistema de notificações do aplicativo

    Esta classe é projetada para ser usada como mixin na classe PainelParuWindow.
    Ela fornece métodos para enviar diferentes tipos de notificações ao usuário.
    """

    def send_notification(self, title, body, icon_name="dialog-information-symbolic", priority=0):
        """Envia uma notificação ao usuário com compatibilidade entre versões

        Args:
            title (str): Título da notificação
            body (str): Corpo da notificação
            icon_name (str): Nome do ícone a ser usado
            priority (int): Prioridade da notificação (0=normal, 1=high, 2=critical)
        """
        try:
            # Tenta usar Adw.Notification (libadwaita 1.5+)
            if hasattr(Adw, 'Notification'):
                notification = Adw.Notification.new(title)
                notification.set_body(body)
                # Define prioridade (0=normal, 1=high, 2=critical)
                if priority == 2:  # CRITICAL
                    notification.set_priority(Adw.NotificationPriority.CRITICAL)
                elif priority == 1:  # HIGH
                    notification.set_priority(Adw.NotificationPriority.HIGH)
                else:  # NORMAL
                    notification.set_priority(Adw.NotificationPriority.NORMAL)
                notification.set_icon(Gio.ThemedIcon(name=icon_name))
                # Gera um ID único para a notificação
                notification_id = f"paru-gui-{hash(title + body)}"
                self.get_application().send_notification(notification_id, notification)
            else:
                # Fallback para Gio.Notification (GNOME 40+)
                notification = Gio.Notification.new(title)
                notification.set_body(body)
                notification.set_icon(Gio.ThemedIcon(name=icon_name))
                # Define prioridade via tags
                if priority == 2:  # CRITICAL
                    notification.set_priority(Gio.NotificationPriority.URGENT)
                elif priority == 1:  # HIGH
                    notification.set_priority(Gio.NotificationPriority.HIGH)
                else:  # NORMAL
                    notification.set_priority(Gio.NotificationPriority.NORMAL)
                # Gera um ID único para a notificação
                notification_id = f"paru-gui-{hash(title + body)}"
                self.get_application().send_notification(notification_id, notification)
        except Exception as e:
            print(f"⚠️ Não foi possível enviar notificação: {str(e)}")
            # Como fallback final, apenas exibe no terminal
            priority_str = ["NORMAL", "HIGH", "CRITICAL"][min(priority, 2)]
            if hasattr(self, 'terminal') and self.terminal:
                self.terminal.append(f"ℹ️ Notificação ({priority_str}): {title} - {body}", "info")

    def send_build_success_notification(self, package_name):
        """Envia notificação de build bem-sucedido"""
        self.send_notification(_("Build Concluído"),
                              _("O pacote {} foi compilado com sucesso.").format(package_name),
                              "package-x-generic-symbolic",
                              1)  # HIGH

    def send_build_failure_notification(self, package_name, error):
        """Envia notificação de falha no build"""
        self.send_notification(_("Falha no Build"),
                              _("O build do pacote {} falhou: {}").format(package_name, error),
                              "dialog-error-symbolic",
                              1)  # HIGH

    def send_install_success_notification(self, package_name):
        """Envia notificação de instalação bem-sucedida"""
        self.send_notification(_("Instalação Concluída"),
                              _("O pacote {} foi instalado com sucesso.").format(package_name),
                              "software-installed-symbolic",
                              1)  # HIGH

    def send_system_update_notification(self, packages_updated):
        """Envia notificação de atualização do sistema"""
        self.send_notification(_("Atualização Concluída"),
                              _("{} pacotes foram atualizados com sucesso.").format(packages_updated),
                              "system-software-update-symbolic",
                              1)  # HIGH

    def send_error_notification(self, error_title, error_message):
        """Envia notificação de erro crítico"""
        self.send_notification(error_title,
                              error_message,
                              "dialog-error-symbolic",
                              2)  # CRITICAL
