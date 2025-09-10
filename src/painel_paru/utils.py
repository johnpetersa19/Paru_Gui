from gi.repository import Gtk
import gettext
import os
import logging
from pathlib import Path

_ = gettext.gettext

def check_content_path(window, terminal_manager=None):
    """
    Verifica se um caminho válido está selecionado na interface do usuário.

    Esta função é fundamental para garantir que as operações que dependem de um
    caminho selecionado (como build de pacotes ou verificação de PKGBUILD) só
    sejam executadas quando um caminho válido estiver disponível. Ela verifica
    se o atributo 'content_path' existe na janela e se contém um valor não nulo.

    A função é usada como primeira linha de verificação antes de qualquer operação
    que precise de um caminho selecionado, evitando erros posteriores relacionados
    a caminhos inválidos ou não definidos.

    Args:
        window (Gtk.Window): Instância da janela principal da aplicação
        terminal_manager (TerminalManager, optional): Gerenciador do terminal para
            exibir mensagens de erro ao usuário. Default é None.

    Returns:
        bool: True se um caminho válido está selecionado, False caso contrário

    Example:
        >>> if check_content_path(window, terminal_manager):
        ...     # Caminho válido, podemos prosseguir
        ...     print("Caminho selecionado:", window.content_path)
        ... else:
        ...     # Nenhum caminho selecionado, exibir mensagem de erro já feita
        ...     pass

    Note:
        - Esta função não verifica se o caminho existe no sistema de arquivos
        - Apenas verifica se o atributo existe e tem um valor não nulo
        - Mensagens de erro são exibidas automaticamente no terminal se
          terminal_manager for fornecido
    """
    if not hasattr(window, 'content_path') or not window.content_path:
        if terminal_manager:
            terminal_manager.append(_("❌ Nenhum diretório selecionado."), "error")
        return False
    return True

def check_path_exists(window, terminal_manager=None, must_be_directory=False):
    """
    Verifica se o caminho do conteúdo existe no sistema de arquivos e é válido.

    Esta função realiza uma verificação completa do caminho selecionado, garantindo
    que ele não apenas esteja definido (como check_content_path), mas também que
    exista fisicamente no sistema de arquivos. Pode opcionalmente verificar se o
    caminho é um diretório, o que é essencial para operações que exigem diretórios.

    É usada antes de operações que acessam o sistema de arquivos, como leitura de
    PKGBUILD ou execução de comandos no diretório selecionado.

    Args:
        window (Gtk.Window): Instância da janela principal da aplicação
        terminal_manager (TerminalManager, optional): Gerenciador do terminal para
            exibir mensagens de erro ao usuário. Default é None.
        must_be_directory (bool, optional): Indica se o caminho deve ser um diretório.
            Default é False.

    Returns:
        bool: True se o caminho existe (e é diretório se must_be_directory=True),
              False caso contrário

    Example:
        >>> # Verificar se um diretório válido existe
        >>> if check_path_exists(window, terminal_manager, must_be_directory=True):
        ...     print("Diretório válido:", window.content_path)
        ...
        >>> # Verificar se um arquivo ou diretório existe
        >>> if check_path_exists(window, terminal_manager):
        ...     print("Caminho válido:", window.content_path)

    Note:
        - Primeiro verifica se o caminho está selecionado com check_content_path
        - Verifica a existência física do caminho com os.path.exists
        - Quando must_be_directory=True, também verifica com os.path.isdir
        - Mensagens de erro são exibidas automaticamente no terminal se
          terminal_manager for fornecido
    """
    if not check_content_path(window, terminal_manager):
        return False

    # Verifica se o caminho existe no sistema de arquivos
    if not os.path.exists(window.content_path):
        if terminal_manager:
            terminal_manager.append(_("❌ Caminho não existe: %s") % window.content_path, "error")
        return False

    # Verifica se deve ser um diretório e se não é
    if must_be_directory and not os.path.isdir(window.content_path):
        if terminal_manager:
            terminal_manager.append(_("❌ Caminho selecionado não é um diretório"), "error")
        return False

    return True

def check_pkgbuild_exists(window, terminal_manager=None):
    """
    Verifica se um diretório válido está selecionado e contém um PKGBUILD válido.

    Esta função é especializada para operações específicas de AUR/PKGBUILD, garantindo
    que o diretório selecionado contenha um arquivo PKGBUILD, que é essencial para
    build de pacotes. Ela combina verificações de caminho com verificação específica
    do arquivo PKGBUILD.

    É usada antes de operações que dependem do PKGBUILD, como edição, visualização
    de informações ou execução de build.

    Args:
        window (Gtk.Window): Instância da janela principal da aplicação
        terminal_manager (TerminalManager, optional): Gerenciador do terminal para
            exibir mensagens de erro ao usuário. Default é None.

    Returns:
        bool: True se o PKGBUILD existe no diretório selecionado, False caso contrário

    Example:
        >>> if check_pkgbuild_exists(window, terminal_manager):
        ...     # PKGBUILD existe, podemos editar ou buildar
        ...     print("PKGBUILD encontrado em:", window.content_path)
        ... else:
        ...     # Não há PKGBUILD, não podemos prosseguir
        ...     pass

    Note:
        - Primeiro verifica se o caminho existe e é um diretório com check_path_exists
        - Verifica especificamente a presença do arquivo "PKGBUILD" (case-sensitive)
        - Não verifica se o PKGBUILD é válido sintaticamente, apenas sua presença
        - Mensagens de erro são exibidas automaticamente no terminal se
          terminal_manager for fornecido
    """
    # Verifica se o caminho existe e é um diretório
    if not check_path_exists(window, terminal_manager, must_be_directory=True):
        return False

    pkgbuild_path = os.path.join(window.content_path, "PKGBUILD")

    # Verifica se o PKGBUILD existe
    if not os.path.exists(pkgbuild_path):
        if terminal_manager:
            terminal_manager.append(_("❌ PKGBUILD não encontrado"), "error")
        return False

    # Verifica se é um arquivo (não um diretório com o mesmo nome)
    if not os.path.isfile(pkgbuild_path):
        if terminal_manager:
            terminal_manager.append(_("❌ PKGBUILD encontrado, mas não é um arquivo"), "error")
        return False

    # Verifica permissões de leitura
    if not os.access(pkgbuild_path, os.R_OK):
        if terminal_manager:
            terminal_manager.append(_("❌ Sem permissão para ler o PKGBUILD"), "error")
        return False

    return True

def check_patches_exist(window, terminal_manager=None):
    """
    Verifica se existem patches aplicáveis no diretório selecionado.

    Esta função verifica se há arquivos com extensão .patch no diretório selecionado,
    que podem ser aplicados durante o processo de build. É útil para operações que
    dependem de patches personalizados.

    Args:
        window (Gtk.Window): Instância da janela principal da aplicação
        terminal_manager (TerminalManager, optional): Gerenciador do terminal para
            exibir mensagens de erro ao usuário. Default é None.

    Returns:
        bool: True se existem patches no diretório, False caso contrário

    Example:
        >>> if check_patches_exist(window, terminal_manager):
        ...     print("Patches encontrados, preparando para aplicar...")

    Note:
        - Primeiro verifica se o caminho existe e é um diretório
        - Procura por arquivos com extensão .patch
        - Não verifica a validade dos patches, apenas sua presença
    """
    if not check_path_exists(window, terminal_manager, must_be_directory=True):
        return False

    try:
        patch_files = list(Path(window.content_path).glob("*.patch"))
        if not patch_files:
            if terminal_manager:
                terminal_manager.append(_("⚠️ Nenhum patch encontrado no diretório"), "warning")
            return False
        return True
    except Exception as e:
        error_type = type(e).__name__
        if terminal_manager:
            terminal_manager.append(_("❌ Erro ao verificar patches: %s") % error_type, "error")
        logging.error("Error checking patches: %s", str(e))
        return False