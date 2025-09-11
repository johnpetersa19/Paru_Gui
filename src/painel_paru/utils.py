from gi.repository import Gtk
import gettext
import os
import logging
from pathlib import Path

_ = gettext.gettext

def validate_path(window, terminal_manager=None, must_be_directory=False,
                  must_contain_pkgbuild=False, must_contain_patches=False):
    """
    Função unificada para validação de caminhos em diferentes cenários.

    Esta função substitui as funções duplicadas check_content_path, check_path_exists,
    check_pkgbuild_exists e check_patches_exist, oferecendo uma única implementação
    que cobre todos os cenários de validação de caminhos necessários na aplicação.

    A função realiza verificações em cascata, onde cada etapa depende da anterior:
    1. Verifica se um caminho está selecionado
    2. Verifica se o caminho existe no sistema de arquivos
    3. Verifica se é um diretório (se necessário)
    4. Verifica presença de PKGBUILD (se necessário)
    5. Verifica presença de patches (se necessário)

    Args:
        window (Gtk.Window): Instância da janela principal da aplicação
        terminal_manager (TerminalManager, optional): Gerenciador do terminal para
            exibir mensagens de erro ao usuário. Default é None.
        must_be_directory (bool, optional): Indica se o caminho deve ser um diretório.
            Default é False.
        must_contain_pkgbuild (bool, optional): Indica se o caminho deve conter um PKGBUILD.
            Default é False.
        must_contain_patches (bool, optional): Indica se o caminho deve conter arquivos .patch.
            Default é False.

    Returns:
        bool: True se todas as verificações necessárias foram bem-sucedidas, False caso contrário

    Example:
        >>> # Verificar se um caminho válido está selecionado
        >>> validate_path(window, terminal_manager)
        True
        >>>
        >>> # Verificar se um diretório válido existe
        >>> validate_path(window, terminal_manager, must_be_directory=True)
        True
        >>>
        >>> # Verificar se um diretório contém um PKGBUILD
        >>> validate_path(window, terminal_manager, must_be_directory=True, must_contain_pkgbuild=True)
        True
        >>>
        >>> # Verificar se um diretório contém patches
        >>> validate_path(window, terminal_manager, must_be_directory=True, must_contain_patches=True)
        True

    Note:
        - A função realiza verificações em cascata, parando na primeira falha
        - Mensagens de erro específicas são exibidas automaticamente no terminal
          quando terminal_manager é fornecido
        - A ordem das verificações é otimizada para minimizar operações de I/O
        - Esta função substitui completamente as funções check_content_path,
          check_path_exists, check_pkgbuild_exists e check_patches_exist
    """
    # 1. Primeira verificação: caminho selecionado
    if not hasattr(window, 'content_path') or not window.content_path:
        if terminal_manager:
            terminal_manager.append(_("❌ Nenhum diretório selecionado."), "error")
        return False

    # 2. Verificação de existência no sistema de arquivos
    if not os.path.exists(window.content_path):
        if terminal_manager:
            terminal_manager.append(_("❌ Caminho não existe: %s") % window.content_path, "error")
        return False

    # 3. Verificação se deve ser um diretório
    if must_be_directory and not os.path.isdir(window.content_path):
        if terminal_manager:
            terminal_manager.append(_("❌ Caminho selecionado não é um diretório"), "error")
        return False

    # 4. Verificação de PKGBUILD se necessário
    if must_contain_pkgbuild:
        pkgbuild_path = os.path.join(window.content_path, "PKGBUILD")

        # Verifica se o PKGBUILD existe
        if not os.path.exists(pkgbuild_path):
            if terminal_manager:
                terminal_manager.append(_("❌ PKGBUILD não encontrado"), "error")
            return False

        # Verifica se é um arquivo (não um diretório)
        if not os.path.isfile(pkgbuild_path):
            if terminal_manager:
                terminal_manager.append(_("❌ PKGBUILD encontrado, mas não é um arquivo"), "error")
            return False

        # Verifica permissões de leitura
        if not os.access(pkgbuild_path, os.R_OK):
            if terminal_manager:
                terminal_manager.append(_("❌ Sem permissão para ler o PKGBUILD"), "error")
            return False

    # 5. Verificação de patches se necessário
    if must_contain_patches:
        try:
            patch_files = list(Path(window.content_path).glob("*.patch"))
            if not patch_files:
                if terminal_manager:
                    terminal_manager.append(_("⚠️ Nenhum patch encontrado no diretório"), "warning")
                logging.debug(f"Nenhum arquivo .patch encontrado em: {window.content_path}")
                return False
        except Exception as e:
            error_type = type(e).__name__
            if terminal_manager:
                terminal_manager.append(_("❌ Erro ao verificar patches: %s") % error_type, "error")
            logging.error("Error checking patches: %s", str(e))
            return False

    return True
