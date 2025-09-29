import os
import re
import subprocess
import logging
import json
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse, urljoin, quote
import gi
gi.require_version('GObject', '2.0')
from gi.repository import GObject, GLib

class UpdateSource(Enum):
    WEB_API = "web_api"
    HTML_SCRAPING = "html_scraping"
    RSS_FEED = "rss_feed"
    FTP_LISTING = "ftp_listing"
    ARCHIVE_LISTING = "archive_listing"

class UpdatePriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class UpstreamUpdateInfo:
    pkgname: str
    current_version: str
    version: str
    release_date: Optional[str] = None
    changelog_url: Optional[str] = None
    download_url: Optional[str] = None
    source_type: str = "Unknown"
    security_update: bool = False
    priority: UpdatePriority = UpdatePriority.NORMAL
    size_mb: Optional[float] = None

@dataclass
class CacheEntry:
    timestamp: datetime
    data: Any
    ttl: timedelta = timedelta(hours=6)

@dataclass
class UpstreamSource:
    name: str
    source_type: UpdateSource
    url: str
    version_pattern: Optional[str] = None
    enabled: bool = True
    auth_token: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class FilterOptions:
    exclude_prerelease: bool = True
    exclude_beta: bool = True
    exclude_alpha: bool = True
    exclude_rc: bool = False
    include_security_only: bool = False

class SimpleCache:
    def __init__(self, default_ttl_hours: int = 6):
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = timedelta(hours=default_ttl_hours)
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if datetime.utcnow() - entry.timestamp < entry.ttl:
                    return entry.data
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, data: Any, ttl: Optional[timedelta] = None):
        with self._lock:
            self.cache[key] = CacheEntry(
                timestamp=datetime.utcnow(),
                data=data,
                ttl=ttl or self.default_ttl
            )

    def clear(self):
        with self._lock:
            self.cache.clear()

class UniversalUpstreamChecker(GObject.Object):
    __gsignals__ = {
        'update-found': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'check-completed': (GObject.SignalFlags.RUN_LAST, None, (str, bool)),
    }

    def __init__(self):
        super().__init__()
        self.cache = SimpleCache()
        self.filter_options = FilterOptions()
        self._setup_logging()

    def _setup_logging(self):
        self.logger = logging.getLogger("upstream_checker")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def check_for_updates(self, pkgbuild_path: str) -> Optional[UpstreamUpdateInfo]:
        """Método principal para verificar atualizações upstream"""
        if not os.path.exists(pkgbuild_path):
            self.logger.error(f"PKGBUILD not found: {pkgbuild_path}")
            return None

        pkgname, current_version, sources, project_url = self._parse_pkgbuild(pkgbuild_path)
        
        if pkgname == "unknown" or current_version == "unknown":
            self.logger.warning(f"Could not extract package info from: {pkgbuild_path}")
            return None

        # Cache check
        cache_key = f"upstream_{pkgname}_{current_version}"
        cached_info = self.cache.get(cache_key)
        if cached_info:
            return cached_info

        # Detectar e verificar sources
        update_info = self._perform_check(pkgname, current_version, sources, project_url)
        
        if update_info and self._passes_filters(update_info):
            self.cache.set(cache_key, update_info)
            self.emit('update-found', update_info)
            return update_info
        
        return None

    def check_for_updates_async(self, pkgbuild_path: str, callback: Optional[Callable] = None):
        """Versão assíncrona da verificação"""
        def async_check():
            try:
                result = self.check_for_updates(pkgbuild_path)
                if callback:
                    GLib.idle_add(callback, result, None)
            except Exception as e:
                self.logger.error(f"Async check failed: {e}")
                if callback:
                    GLib.idle_add(callback, None, str(e))
        
        thread = threading.Thread(target=async_check, daemon=True)
        thread.start()

    def get_upstream_status_for_card(self, pkgbuild_path: str) -> Dict[str, Any]:
        """Método específico para integração com a GUI do Paru"""
        update_info = self.check_for_updates(pkgbuild_path)
        
        if update_info:
            return {
                'has_update': True,
                'current_version': update_info.current_version,
                'latest_version': update_info.version,
                'source_name': update_info.source_type,
                'security_update': update_info.security_update,
                'update_age_days': self._calculate_age_days(update_info.release_date),
                'changelog_url': update_info.changelog_url,
                'download_url': update_info.download_url,
                'priority': update_info.priority.value
            }
        
        return {
            'has_update': False,
            'current_version': None,
            'latest_version': None,
            'source_name': None,
            'security_update': False,
            'update_age_days': None
        }

    def _perform_check(self, pkgname: str, current_version: str, sources: List[str], project_url: Optional[str]) -> Optional[UpstreamUpdateInfo]:
        """Realiza a verificação upstream universal"""
        detected_sources = self._auto_detect_sources(sources, project_url)
        
        best_update = None
        
        for source in detected_sources:
            if not source.enabled:
                continue
            
            try:
                update_info = self._check_source(source, pkgname, current_version)
                if update_info and self._is_newer_version(current_version, update_info.version):
                    if not best_update or self._is_newer_version(best_update.version, update_info.version):
                        best_update = update_info
                        # Se for atualização de segurança, priorizar
                        if 'security' in (update_info.changelog_url or '').lower():
                            best_update.security_update = True
                            best_update.priority = UpdatePriority.HIGH
                        
            except Exception as e:
                self.logger.error(f"Error checking source {source.name}: {e}")
                continue

        return best_update

    def _auto_detect_sources(self, sources: List[str], project_url: Optional[str]) -> List[UpstreamSource]:
        """Detecção automática universal de fontes"""
        detected_sources = []
        potential_urls = sources + ([project_url] if project_url else [])
        
        for url in potential_urls:
            if not url:
                continue
            
            source_type, api_url, platform_name = self._determine_source_type(url)
            if source_type and api_url:
                source = UpstreamSource(
                    name=f"auto_{platform_name}",
                    source_type=source_type,
                    url=api_url
                )
                detected_sources.append(source)
        
        return detected_sources

    def _determine_source_type(self, url: str) -> Tuple[Optional[UpdateSource], Optional[str], str]:
        """Detecção universal de tipos de fonte - MUITO MAIS PLATAFORMAS"""
        
        # GitHub
        github_match = re.search(r'github\.com/([^/]+)/([^/]+)(?:/.*)?', url)
        if github_match:
            owner, repo = github_match.groups()
            repo = repo.rstrip('.git')
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            return UpdateSource.WEB_API, api_url, "GitHub"

        # GitLab (gitlab.com, gitlab.gnome.org, etc)
        gitlab_match = re.search(r'(gitlab\.[\w\.-]+)/([^/]+)/([^/]+)(?:/.*)?', url)
        if gitlab_match:
            host, owner, repo = gitlab_match.groups()
            repo = repo.rstrip('.git')
            encoded_path = quote(f"{owner}/{repo}", safe='')
            api_url = f"https://{host}/api/v4/projects/{encoded_path}/releases/permalink/latest"
            return UpdateSource.WEB_API, api_url, "GitLab"

        # Gitea/Forgejo (Codeberg, etc)
        gitea_match = re.search(r'(codeberg\.org|git\.[\w\.-]+)/([^/]+)/([^/]+)(?:/.*)?', url)
        if gitea_match:
            host, owner, repo = gitea_match.groups()
            repo = repo.rstrip('.git')
            api_url = f"https://{host}/api/v1/repos/{owner}/{repo}/releases/latest"
            return UpdateSource.WEB_API, api_url, "Gitea"

        # SourceHut (sr.ht)
        srht_match = re.search(r'git\.sr\.ht/~([^/]+)/([^/]+)(?:/.*)?', url)
        if srht_match:
            owner, repo = srht_match.groups()
            # sr.ht não tem API de releases, usar tags
            api_url = f"https://git.sr.ht/~{owner}/{repo}/refs"
            return UpdateSource.HTML_SCRAPING, api_url, "SourceHut"

        # BitBucket
        bitbucket_match = re.search(r'bitbucket\.org/([^/]+)/([^/]+)(?:/.*)?', url)
        if bitbucket_match:
            owner, repo = bitbucket_match.groups()
            api_url = f"https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/downloads"
            return UpdateSource.WEB_API, api_url, "BitBucket"

        # PyPI (Python packages)
        pypi_match = re.search(r'pypi\.org/project/([^/]+)', url)
        if pypi_match:
            package = pypi_match.group(1)
            api_url = f"https://pypi.org/pypi/{package}/json"
            return UpdateSource.WEB_API, api_url, "PyPI"

        # npm (Node.js packages)
        npm_match = re.search(r'npmjs\.com/package/([^/]+)', url)
        if npm_match:
            package = npm_match.group(1)
            api_url = f"https://registry.npmjs.org/{package}/latest"
            return UpdateSource.WEB_API, api_url, "npm"

        # SourceForge
        sf_match = re.search(r'sourceforge\.net/projects/([^/]+)', url)
        if sf_match:
            project = sf_match.group(1)
            api_url = f"https://sourceforge.net/projects/{project}/rss"
            return UpdateSource.RSS_FEED, api_url, "SourceForge"

        # GNU releases
        gnu_match = re.search(r'gnu\.org/software/([^/]+)', url)
        if gnu_match:
            package = gnu_match.group(1)
            api_url = f"https://ftp.gnu.org/gnu/{package}/"
            return UpdateSource.FTP_LISTING, api_url, "GNU"

        # Apache releases
        apache_match = re.search(r'apache\.org/[^/]*/([^/]+)', url)
        if apache_match:
            project = apache_match.group(1)
            api_url = f"https://archive.apache.org/dist/{project}/"
            return UpdateSource.ARCHIVE_LISTING, api_url, "Apache"

        # CPAN (Perl packages)
        cpan_match = re.search(r'cpan\.org/dist/([^/]+)', url)
        if cpan_match:
            dist = cpan_match.group(1)
            api_url = f"https://fastapi.metacpan.org/v1/release/{dist}"
            return UpdateSource.WEB_API, api_url, "CPAN"

        # RubyGems
        rubygems_match = re.search(r'rubygems\.org/gems/([^/]+)', url)
        if rubygems_match:
            gem = rubygems_match.group(1)
            api_url = f"https://rubygems.org/api/v1/gems/{gem}.json"
            return UpdateSource.WEB_API, api_url, "RubyGems"

        # Crates.io (Rust packages)
        crates_match = re.search(r'crates\.io/crates/([^/]+)', url)
        if crates_match:
            crate = crates_match.group(1)
            api_url = f"https://crates.io/api/v1/crates/{crate}"
            return UpdateSource.WEB_API, api_url, "Crates.io"

        # Feed/RSS detection
        if url.endswith(('.xml', '.rss', '.atom')) or any(keyword in url.lower() for keyword in ['rss', 'feed', 'atom']):
            return UpdateSource.RSS_FEED, url, "RSS Feed"

        # FTP detection
        if url.startswith('ftp://'):
            return UpdateSource.FTP_LISTING, url, "FTP"

        # Generic web pages (last resort)
        if url.startswith(('http://', 'https://')):
            if any(keyword in url.lower() for keyword in ['releases', 'tags', 'download', 'versions']):
                return UpdateSource.HTML_SCRAPING, url, "Web Page"

        return None, None, "Unknown"

    def _check_source(self, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Verificação universal de fonte"""
        if source.source_type == UpdateSource.WEB_API:
            return self._check_web_api(source, pkgname, current_version)
        elif source.source_type == UpdateSource.HTML_SCRAPING:
            return self._check_html_scraping(source, pkgname, current_version)
        elif source.source_type == UpdateSource.RSS_FEED:
            return self._check_rss_feed(source, pkgname, current_version)
        elif source.source_type == UpdateSource.FTP_LISTING:
            return self._check_ftp_listing(source, pkgname, current_version)
        elif source.source_type == UpdateSource.ARCHIVE_LISTING:
            return self._check_archive_listing(source, pkgname, current_version)
        
        return None

    def _check_web_api(self, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Verificação universal de APIs web JSON"""
        cmd = [
            'curl', '-s', '-f', '-L',
            '--user-agent', 'paru-gui/2.7.0 (UpstreamChecker)',
            '--max-time', '15',
            '--retry', '2',
            '--retry-delay', '1'
        ]
        
        # Headers de autenticação
        if source.auth_token:
            if 'github' in source.url:
                cmd.extend(['-H', f'Authorization: token {source.auth_token}'])
            elif 'gitlab' in source.url:
                cmd.extend(['-H', f'PRIVATE-TOKEN: {source.auth_token}'])
            else:
                cmd.extend(['-H', f'Authorization: Bearer {source.auth_token}'])
        
        # Headers customizados
        for header, value in source.custom_headers.items():
            cmd.extend(['-H', f'{header}: {value}'])
        
        cmd.append(source.url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode != 0:
                self.logger.debug(f"curl failed for {source.url}: {result.stderr}")
                return None

            if not result.stdout.strip():
                return None

            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                self.logger.warning(f"Invalid JSON from {source.url}")
                return None
            
            return self._extract_version_from_json(data, source, pkgname, current_version)
                    
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout fetching {source.url}")
        except Exception as e:
            self.logger.error(f"Error checking {source.url}: {e}")
        
        return None

    def _extract_version_from_json(self, data: Dict, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Extração universal de versão de diferentes APIs JSON"""
        version = None
        release_date = None
        changelog_url = None
        download_url = None
        source_name = source.name
        
        # GitHub/GitLab/Gitea style
        if 'tag_name' in data:
            version = data.get('tag_name', '').lstrip('vV')
            release_date = data.get('published_at') or data.get('created_at') or data.get('released_at')
            changelog_url = data.get('html_url') or data.get('url')
            download_url = data.get('tarball_url') or data.get('zipball_url')
            
        # PyPI style
        elif 'info' in data and 'version' in data['info']:
            version = str(data['info']['version']).lstrip('vV')
            release_date = None
            changelog_url = data['info'].get('project_url') or data['info'].get('home_page')
            download_url = data['info'].get('download_url')
            
        # npm style
        elif 'version' in data:
            version = str(data['version']).lstrip('vV')
            release_date = data.get('time', {}).get(data['version']) if isinstance(data.get('time'), dict) else None
            changelog_url = data.get('homepage') or data.get('repository', {}).get('url') if isinstance(data.get('repository'), dict) else None
            
        # CPAN style
        elif 'version' in data and 'author' in data:
            version = str(data['version']).lstrip('vV')
            release_date = data.get('date')
            changelog_url = data.get('resources', {}).get('homepage') if isinstance(data.get('resources'), dict) else None
            
        # Crates.io style
        elif 'crate' in data and 'versions' in data:
            versions = data.get('versions', [])
            if versions and isinstance(versions, list):
                latest = versions[0]
                version = str(latest.get('num', '')).lstrip('vV')
                release_date = latest.get('created_at')
                
        # Generic version field
        elif 'version' in data:
            version = str(data['version']).lstrip('vV')
            release_date = data.get('date') or data.get('release_date') or data.get('published')
            changelog_url = data.get('url') or data.get('link') or data.get('homepage')
            download_url = data.get('download_url') or data.get('download')
            
        # BitBucket downloads
        elif 'values' in data and isinstance(data['values'], list):
            downloads = data['values']
            if downloads:
                latest = downloads[0]
                name = latest.get('name', '')
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)*)', name)
                if version_match:
                    version = version_match.group(1)
                    download_url = latest.get('links', {}).get('self', {}).get('href')
        
        # Se ainda não encontrou, tentar buscar em campos aninhados
        if not version:
            for key in ['latest', 'current', 'stable']:
                if key in data and isinstance(data[key], dict):
                    nested_version = data[key].get('version') or data[key].get('tag_name', '').lstrip('vV')
                    if nested_version:
                        version = str(nested_version).lstrip('vV')
                        break
        
        if version and self._is_newer_version(current_version, version):
            return UpstreamUpdateInfo(
                pkgname=pkgname,
                current_version=current_version,
                version=version,
                release_date=release_date,
                changelog_url=changelog_url,
                download_url=download_url,
                source_type=source_name
            )
        
        return None

    def _check_html_scraping(self, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Verificação através de scraping HTML"""
        cmd = [
            'curl', '-s', '-f', '-L',
            '--user-agent', 'paru-gui/2.7.0 (UpstreamChecker)',
            '--max-time', '10',
            source.url
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout:
                html_content = result.stdout
                
                # Padrões de regex para diferentes formatos de versão
                patterns = [
                    r'v?(\d+\.\d+\.\d+)',           # Semantic versioning
                    r'v?(\d+\.\d+)',                # Major.minor
                    r'(\d{4}-\d{2}-\d{2})',         # Date-based
                    r'v?(\d+\.\d+\.\d+[a-zA-Z]\w*)', # With suffixes
                ]
                
                if source.version_pattern:
                    patterns.insert(0, source.version_pattern)
                
                all_versions = []
                for pattern in patterns:
                    versions = re.findall(pattern, html_content)
                    all_versions.extend(versions)
                
                if all_versions:
                    # Encontrar a versão mais recente
                    latest_version = max(all_versions, key=lambda v: self._version_to_tuple(v))
                    
                    if self._is_newer_version(current_version, latest_version):
                        return UpstreamUpdateInfo(
                            pkgname=pkgname,
                            current_version=current_version,
                            version=latest_version,
                            changelog_url=source.url,
                            source_type="Web Page"
                        )
        except Exception as e:
            self.logger.error(f"HTML scraping error for {source.url}: {e}")
        
        return None

    def _check_rss_feed(self, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Verificação através de RSS/Atom feeds"""
        cmd = ['curl', '-s', '-f', '--max-time', '10', source.url]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout:
                root = ET.fromstring(result.stdout)
                
                latest_version = None
                latest_date = None
                latest_link = None
                
                # Processar items do feed
                for item in root.findall('.//item'):
                    title = item.find('title')
                    pub_date = item.find('pubDate')
                    link = item.find('link')
                    
                    if title is not None and title.text:
                        version_match = re.search(r'(\d+\.\d+(?:\.\d+)*)', title.text)
                        if version_match:
                            version = version_match.group(1)
                            if not latest_version or self._is_newer_version(latest_version, version):
                                latest_version = version
                                latest_date = pub_date.text if pub_date is not None else None
                                latest_link = link.text if link is not None else None
                
                if latest_version and self._is_newer_version(current_version, latest_version):
                    return UpstreamUpdateInfo(
                        pkgname=pkgname,
                        current_version=current_version,
                        version=latest_version,
                        release_date=latest_date,
                        changelog_url=latest_link,
                        source_type="RSS Feed"
                    )
        except Exception as e:
            self.logger.error(f"RSS feed error for {source.url}: {e}")
        
        return None

    def _check_ftp_listing(self, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Verificação através de listagem FTP"""
        cmd = ['curl', '-s', '-l', '--max-time', '10', source.url]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout:
                files = result.stdout.strip().split('\n')
                
                latest_version = None
                latest_file = None
                
                for filename in files:
                    version_match = re.search(r'(\d+\.\d+(?:\.\d+)*)', filename)
                    if version_match:
                        version = version_match.group(1)
                        if not latest_version or self._is_newer_version(latest_version, version):
                            latest_version = version
                            latest_file = filename
                
                if latest_version and self._is_newer_version(current_version, latest_version):
                    download_url = urljoin(source.url, latest_file) if latest_file else None
                    return UpstreamUpdateInfo(
                        pkgname=pkgname,
                        current_version=current_version,
                        version=latest_version,
                        download_url=download_url,
                        source_type="FTP"
                    )
        except Exception as e:
            self.logger.error(f"FTP listing error for {source.url}: {e}")
        
        return None

    def _check_archive_listing(self, source: UpstreamSource, pkgname: str, current_version: str) -> Optional[UpstreamUpdateInfo]:
        """Verificação através de listagem de arquivos (Apache, GNU, etc)"""
        return self._check_html_scraping(source, pkgname, current_version)

    def _parse_pkgbuild(self, pkgbuild_path: str) -> Tuple[str, str, List[str], Optional[str]]:
        """Parse simplificado de PKGBUILD"""
        pkgname = "unknown"
        pkgver = "unknown"
        sources: List[str] = []
        project_url: Optional[str] = None

        try:
            with open(pkgbuild_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Remove comments
            content_clean = re.sub(r'#.*$', '', content, flags=re.MULTILINE)

            # Extract fields
            for line in content_clean.split('\n'):
                line = line.strip()
                
                if line.startswith('pkgname='):
                    pkgname = re.sub(r'pkgname=["\']*([^"\'\s]+)["\']*', r'\1', line)
                elif line.startswith('pkgver='):
                    pkgver = re.sub(r'pkgver=["\']*([^"\'\s]+)["\']*', r'\1', line)
                elif line.startswith('url='):
                    project_url = re.sub(r'url=["\']*([^"\'\s]+)["\']*', r'\1', line)

            # Extract source array
            source_match = re.search(r'source=\(([^)]*)\)', content_clean, re.DOTALL)
            if source_match:
                source_content = source_match.group(1)
                for line in source_content.split('\n'):
                    line = line.strip().strip('\'"')
                    if line and not line.startswith('#'):
                        # Variable substitution
                        line = line.replace('$pkgname', pkgname).replace('${pkgname}', pkgname)
                        line = line.replace('$pkgver', pkgver).replace('${pkgver}', pkgver)
                        sources.append(line)

        except Exception as e:
            self.logger.error(f"Error parsing PKGBUILD {pkgbuild_path}: {e}")

        return pkgname, pkgver, sources, project_url

    def _is_newer_version(self, current: str, candidate: str) -> bool:
        """Comparação inteligente de versões"""
        return self._version_to_tuple(candidate) > self._version_to_tuple(current)

    def _version_to_tuple(self, version: str) -> Tuple:
        """Converte versão para tupla comparável"""
        # Remove prefixos comuns
        version = re.sub(r'^[vVrR]', '', version)
        version = re.sub(r'[+-].*$', '', version)
        
        parts = []
        for part in version.split('.'):
            # Tenta extrair número e sufixo
            match = re.match(r'(\d+)(.*)$', part)
            if match:
                num, suffix = match.groups()
                parts.append(int(num))
                # Tratamento de sufixos de pre-release
                if suffix:
                    if any(pre in suffix.lower() for pre in ['alpha', 'a']):
                        parts.extend([0, 1])
                    elif any(pre in suffix.lower() for pre in ['beta', 'b']):
                        parts.extend([0, 2])
                    elif any(pre in suffix.lower() for pre in ['rc', 'cr']):
                        parts.extend([0, 3])
                    elif any(pre in suffix.lower() for pre in ['pre', 'preview']):
                        parts.extend([0, 4])
                    else:
                        parts.extend([0, 5])
            else:
                parts.append(0)
        
        return tuple(parts)

    def _passes_filters(self, update_info: UpstreamUpdateInfo) -> bool:
        """Aplicar filtros de atualização"""
        version = update_info.version.lower()
        
        if self.filter_options.exclude_prerelease and self._is_prerelease(version):
            return False
        if self.filter_options.exclude_beta and 'beta' in version:
            return False
        if self.filter_options.exclude_alpha and 'alpha' in version:
            return False
        if self.filter_options.exclude_rc and 'rc' in version:
            return False
        if self.filter_options.include_security_only and not update_info.security_update:
            return False
        
        return True

    def _is_prerelease(self, version: str) -> bool:
        """Detecta se é uma versão pre-release"""
        prerelease_keywords = ['alpha', 'beta', 'rc', 'pre', 'dev', 'snapshot', 'nightly', 'unstable']
        return any(keyword in version.lower() for keyword in prerelease_keywords)

    def _calculate_age_days(self, release_date: Optional[str]) -> Optional[int]:
        """Calcula idade da release em dias"""
        if not release_date:
            return None
        
        try:
            # Tenta diferentes formatos de data
            for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %z']:
                try:
                    date_obj = datetime.strptime(release_date[:19] + 'Z', fmt)
                    return (datetime.utcnow() - date_obj).days
                except ValueError:
                    continue
        except Exception:
            pass
        
        return None

    def set_filter_options(self, options: FilterOptions):
        """Configurar opções de filtro"""
        self.filter_options = options
        self.cache.clear()

    def get_filter_options(self) -> FilterOptions:
        """Obter opções de filtro atuais"""
        return self.filter_options

    def clear_cache(self):
        """Limpar cache manualmente"""
        self.cache.clear()
