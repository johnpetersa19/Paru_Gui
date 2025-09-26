"""Paru GUI - Main package initialization."""

__version__ = "0.1.0"
__author__ = "MiniMax Agent"
__description__ = "A modern and secure graphical interface for managing Arch User Repository (AUR) packages"

from .error_handler import ErrorHandler
from .file_utils import FileUtils
from .history_manager import HistoryManager
from .lazy_cache_manager import LazyCacheManager
from .main import ParuGUIApplication
from .pkgbuild_analyzer import PKGBUILDAnalyzer
from .preferences_manager import PreferencesManager
from .sandboxing import SandboxManager
from .security_analyzer import SecurityAnalyzer
from .signature_verifier import SignatureVerifier
from .terminal_manager import TerminalManager
from .tour_guide import TourGuide
from .upstream_checker import UpstreamChecker

__all__ = [
    'ErrorHandler',
    'FileUtils',
    'HistoryManager',
    'LazyCacheManager',
    'ParuGUIApplication',
    'PKGBUILDAnalyzer',
    'PreferencesManager',
    'SandboxManager',
    'SecurityAnalyzer',
    'SignatureVerifier',
    'TerminalManager',
    'TourGuide',
    'UpstreamChecker',
]

