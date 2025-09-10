import subprocess
import os
import logging
from gi.repository import GLib, Gio
import gettext

_ = gettext.gettext

class ParuRunner:
    """Executa comandos Paru com suporte a atualização da interface e cancelamento

    Esta classe fornece uma interface segura para executar comandos Paru em segundo plano,
    com suporte para ambientes Flatpak e tratamento adequado de saída e erros. O método
    principal, run_command(), executa comandos de forma assíncrona, atualizando a interface
    do usuário através de callbacks e permitindo o cancelamento de operações em andamento.

    Principais funcionalidades:
    - Suporte automático para execução em ambientes Flatpak
    - Configuração adequada do ambiente para evitar problemas de localização
    - Tratamento robusto de erros e exceções
    - Atualização em tempo real da interface do usuário
    - Suporte para cancelamento de operações
    """
    
    @staticmethod
    def run_command(cmd, output_callback):
        """
        Executa comandos Paru com suporte a atualização da interface e cancelamento.

        Este método executa comandos Paru em um processo separado, gerenciando adequadamente
        o ambiente (incluindo suporte para Flatpak) e atualizando a interface do usuário
        através do callback fornecido. O método retorna o objeto do processo para permitir
        cancelamento posterior.

        O método configura automaticamente o ambiente para evitar problemas com localização
        (definindo LANG=C e LC_ALL=C), o que garante que a saída do comando seja consistente
        para parsing e detecção de padrões específicos.

        Args:
            cmd (list): Lista de strings representando o comando e seus argumentos.
                        Exemplo: ["paru", "-Syu"]
            output_callback (callable): Função de callback que recebe a saída do comando.
                                        Deve aceitar pelo menos um parâmetro (a linha de saída)
                                        e opcionalmente um tipo de mensagem (ex: "info", "error")

        Returns:
            subprocess.Popen: Objeto do processo em execução, permitindo cancelamento posterior
            None: Em caso de erro durante a preparação ou execução do comando

        Example:
            >>> def callback(line, msg_type="info"):
            ...     print(f"[{msg_type}] {line}")
            >>> process = ParuRunner.run_command(["paru", "-Syu"], callback)
            >>> # Para cancelar posteriormente:
            >>> if process:
            ...     process.terminate()

        Note:
            - Em ambientes Flatpak, o método tenta usar flatpak-spawn para acessar comandos do host
            - A saída do comando é processada linha por linha para atualização imediata da interface
            - O método trata diversos cenários de erro, incluindo comandos não encontrados e permissões
        """
        # Validação básica do comando
        if not cmd or not isinstance(cmd, list) or len(cmd) == 0:
            error_msg = _("Comando inválido: lista de comandos vazia ou não é uma lista")
            logging.error("Invalid command: empty command list or not a list")
            if output_callback:
                output_callback(error_msg, "error")
            return None

        # Log para depuração (em inglês para facilitar diagnóstico)
        logging.debug("Executing command: %s", " ".join(cmd))

        try:
            # Verifica se estamos em um ambiente Flatpak
            is_flatpak = os.path.exists("/.flatpak-info")
            full_cmd = cmd.copy()  # Cria cópia para não modificar o original

            # Se for Flatpak, tenta usar flatpak-spawn para acessar comandos do host
            if is_flatpak:
                try:
                    # Verifica se flatpak-spawn está disponível
                    subprocess.run(["flatpak-spawn", "--version"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  check=True,
                                  timeout=2.0)
                    full_cmd = ["flatpak-spawn", "--host"] + cmd
                    if output_callback:
                        output_callback(_("Executando em ambiente Flatpak com flatpak-spawn"), "info")
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    if output_callback:
                        output_callback(_("flatpak-spawn não disponível, executando diretamente"), "warning")
            else:
                if output_callback:
                    output_callback(_("Executando em ambiente nativo"), "info")

            # Configura o ambiente para evitar problemas de localização
            env = os.environ.copy()
            env["LANG"] = "C"
            env["LC_ALL"] = "C"

            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                env=env,
                bufsize=1,
                close_fds=True
            )

            def read_output():
                """Lê a saída do processo e atualiza a interface"""
                try:
                    for line in process.stdout:
                        stripped_line = line.strip()
                        if stripped_line and output_callback:
                            GLib.idle_add(output_callback, stripped_line)
                    return False  # Processo terminou, para de monitorar
                except Exception as e:
                    error_msg = _("Erro ao ler saída: %s") % str(e)
                    logging.error("Error reading output: %s", str(e))
                    if output_callback:
                        output_callback(error_msg, "error")
                    return False

            # Configura o monitoramento da saída
            GLib.idle_add(read_output)

            return process  # Retorna o processo para permitir cancelamento

        except FileNotFoundError as e:
            error_msg = _("Comando não encontrado: %s") % cmd[0]
            logging.error("Command not found: %s", cmd[0])
            if output_callback:
                output_callback(error_msg, "error")
        except PermissionError as e:
            error_msg = _("Permissão negada para executar: %s") % cmd[0]
            logging.error("Permission denied for command: %s", cmd[0])
            if output_callback:
                output_callback(error_msg, "error")
        except subprocess.SubprocessError as e:
            error_msg = _("Erro ao executar subprocesso: %s") % str(e)
            logging.error("Subprocess error: %s", str(e))
            if output_callback:
                output_callback(error_msg, "error")
        except Exception as e:
            error_msg = _("Erro inesperado ao executar comando: %s") % str(e)
            logging.exception("Critical error in ParuRunner")
            if output_callback:
                output_callback(error_msg, "error")

        return None

    @staticmethod
    def check_for_conflicts(package_name):
        """
        Verifica possíveis conflitos de pacotes antes da instalação.

        Este método executa o comando 'paru -Si' para obter informações detalhadas
        sobre um pacote, incluindo possíveis conflitos com pacotes já instalados.
        Ele processa a saída do comando para identificar seções de conflitos que
        podem abranger múltiplas linhas.

        Args:
            package_name (str): Nome do pacote a ser verificado

        Returns:
            list: Lista de dicionários com informações sobre conflitos detectados
                  Cada dicionário contém:
                  - "package": Nome do pacote em conflito
                  - "current": Status do pacote atual ("instalado")
                  - "new": Status do novo pacote ("será instalado")
            []: Lista vazia se nenhum conflito for detectado

        Example:
            >>> conflicts = ParuRunner.check_for_conflicts("firefox")
            >>> if conflicts:
            ...     print(f"Conflitos detectados: {[c['package'] for c in conflicts]}")
        """
        try:
            result = subprocess.run(
                ["paru", "-Si", package_name],
                capture_output=True,
                text=True,
                check=True
            )

            conflicts = []
            in_conflicts_section = False

            for line in result.stdout.splitlines():
                if line.startswith("Conflicts With:"):
                    in_conflicts_section = True
                    packages = line.replace("Conflicts With:", "").strip()
                    if packages and packages != "None":
                        for pkg in packages.split():
                            if pkg not in ["None", "-", ""]:
                                conflicts.append({
                                    "package": pkg,
                                    "current": _("instalado"),
                                    "new": _("será instalado")
                                })
                elif in_conflicts_section and line.strip() and not line.startswith("Replaces:"):
                    # Processar linhas adicionais de conflitos
                    for pkg in line.strip().split():
                        if pkg not in ["None", "-", ""]:
                            conflicts.append({
                                "package": pkg,
                                "current": _("instalado"),
                                "new": _("será instalado")
                            })
                elif in_conflicts_section and (line.strip() == "" or line.startswith("Replaces:")):
                    in_conflicts_section = False

            return conflicts

        except subprocess.CalledProcessError as e:
            logging.error("Error checking conflicts for %s: %s", package_name, e.stderr)
            return []
        except Exception as e:
            logging.exception("Critical error checking conflicts for %s", package_name)
            return []