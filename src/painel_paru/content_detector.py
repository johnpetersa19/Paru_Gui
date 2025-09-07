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
        return "generic"
    
    @staticmethod
    def _detect_folder(folder_path: Path) -> str:
        """Detecta conteúdo de pasta com prioridades"""
        files = list(folder_path.iterdir())
        
        # Prioridade 1: PKGBUILD
        if any(f.name == "PKGBUILD" for f in files):
            return "pkgbuild"
        
        # Prioridade 2: Pasta vazia
        if not files:
            return "empty"
        
        return "generic"
