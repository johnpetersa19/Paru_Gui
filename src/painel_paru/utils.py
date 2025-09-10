from gi.repository import Gtk
import gettext
import os
_ = gettext.gettext

def check_content_path(window, terminal_manager=None):
    """
    Verifica se um diretório válido está selecionado.

    Args:
        window: Instância da janela principal
        terminal_manager: Opcional, gerenciador de terminal para exibir mensagens

    Returns:
        bool: True se o diretório é válido, False caso contrário
    """
    if not hasattr(window, 'content_path') or not window.content_path:
        if terminal_manager:
            terminal_manager.append(_("❌ Nenhum diretório selecionado."), "error")
        return False
    return True

def check_path_exists(window, terminal_manager=None):
    """
    Verifica se o caminho do conteúdo existe no sistema de arquivos.

    Args:
        window: Instância da janela principal
        terminal_manager: Opcional, gerenciador de terminal para exibir mensagens

    Returns:
        bool: True se o caminho existe, False caso contrário
    """
    if not check_content_path(window, terminal_manager):
        return False

    if not os.path.exists(window.content_path):
        if terminal_manager:
            terminal_manager.append(_("❌ Caminho não existe: ") + window.content_path, "error")
        return False
    return True

def check_pkgbuild_exists(window, terminal_manager=None):
    """
    Verifica se um diretório válido está selecionado e se contém um PKGBUILD.

    Args:
        window: Instância da janela principal
        terminal_manager: Opcional, gerenciador de terminal para exibir mensagens

    Returns:
        bool: True se o PKGBUILD existe, False caso contrário
    """
    if not check_content_path(window, terminal_manager):
        return False

    pkgbuild_path = f"{window.content_path}/PKGBUILD"
    if not os.path.exists(pkgbuild_path):
        if terminal_manager:
            terminal_manager.append(_("❌ PKGBUILD não encontrado"), "error")
        return False
    return True
