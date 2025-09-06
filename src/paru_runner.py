import subprocess
from gi.repository import GLib

class ParuRunner:
    """Executa comandos Paru de forma segura"""
    
    @staticmethod
    def run_command(command: list, output_callback):
        """Executa comando Paru em thread separada"""
        def run():
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Envia saída para callback em tempo real
                for line in process.stdout:
                    GLib.idle_add(output_callback, line)
                
                process.wait()
                GLib.idle_add(output_callback, "✅ Comando concluído com sucesso!", "success")
            except Exception as e:
                GLib.idle_add(output_callback, f"❌ Erro: {str(e)}", "error")
        
        # Executa em thread separada
        from threading import Thread
        Thread(target=run, daemon=True).start()
