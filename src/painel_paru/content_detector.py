from pathlib import Path

class ContentDetector:
    """Detecta tipo de conteúdo para carregar o card correto"""
    @staticmethod
    def detect_content(path: str) -> str:
        """Retorna estado baseado no conteúdo detectado"""
        path = Path(path)
        # Caso 1: Arquivo único
        if path.is_file():
            return ContentDetector._detect_file(path)
        # Caso 2: Pasta
        return ContentDetector._detect_folder(path)

    @staticmethod
    def _detect_file(file_path: Path) -> str:
        """Detecta tipo de arquivo único"""
        if file_path.name == "PKGBUILD":
            return "pkgbuild"
        elif file_path.suffix == ".pkg.tar.zst":
            return "packages"
        elif file_path.suffix == ".patch":
            return "patches"
        return "generic"

    @staticmethod
    def _detect_folder(folder_path: Path) -> str:
        """Detecta conteúdo de pasta com prioridades"""
        try:
            files = list(folder_path.iterdir())
        except PermissionError:
            return "error"

        # Variáveis para armazenar os tipos de conteúdo encontrados
        has_pkgbuild = False
        has_packages = False
        has_patches = False

        # Itera sobre os arquivos uma única vez para detectar todos os tipos
        for f in files:
            if f.name == "PKGBUILD":
                has_pkgbuild = True
            elif f.name.endswith(".pkg.tar.zst"):
                has_packages = True
            elif f.name.endswith(".patch"):
                has_patches = True

        # Prioridade 1: PKGBUILD
        if has_pkgbuild:
            return "pkgbuild"

        # Prioridade 2: Pacotes pré-compilados
        if has_packages:
            return "packages"

        # Prioridade 3: Patches
        if has_patches:
            return "patches"

        # Prioridade 4: Pasta vazia
        if not files:
            return "empty"

        return "generic"