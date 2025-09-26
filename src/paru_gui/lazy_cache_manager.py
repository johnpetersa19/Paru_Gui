import time
import threading
import subprocess
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future
from gi.repository import GLib, GObject

@dataclass
class CacheEntry:
    data: Any
    timestamp: float
    access_count: int = 0
    last_access: float = 0
    ttl: float = 3600
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl
    
    def access(self) -> None:
        self.access_count += 1
        self.last_access = time.time()

class LazyCache:
    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._access_order: List[str] = []
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return None
            
            entry.access()
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return entry.data
    
    def set(self, key: str, data: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            if ttl is None:
                ttl = self._default_ttl
            
            entry = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl
            )
            
            self._cache[key] = entry
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            self._enforce_size_limit()
    
    def _enforce_size_limit(self) -> None:
        while len(self._cache) > self._max_size:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
    
    def clear_expired(self) -> None:
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hit_ratio': self._calculate_hit_ratio()
            }
    
    def _calculate_hit_ratio(self) -> float:
        total_accesses = sum(entry.access_count for entry in self._cache.values())
        if total_accesses == 0:
            return 0.0
        return total_accesses / len(self._cache) if self._cache else 0.0

class LazyLoader(GObject.Object):
    __gsignals__ = {
        'data-loaded': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
        'load-error': (GObject.SignalFlags.RUN_LAST, None, (str, str)),
        'batch-loaded': (GObject.SignalFlags.RUN_LAST, None, (str, object)),
        'loading-progress': (GObject.SignalFlags.RUN_LAST, None, (str, int, int))
    }
    
    def __init__(self, max_workers: int = 5):
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._loading: Dict[str, Future] = {}
        self._cache = LazyCache()
        self._batch_size = 50
        self._loaded_ranges: Dict[str, List[Tuple[int, int]]] = {}
        self._pending_requests: Dict[str, List[Callable]] = {}
        
    def load_async(self, key: str, loader_func: Callable, *args, ttl: float = 3600, **kwargs) -> None:
        cached_data = self._cache.get(key)
        if cached_data is not None:
            GLib.idle_add(self._emit_data_loaded, key, cached_data)
            return
        
        if key in self._loading:
            if key not in self._pending_requests:
                self._pending_requests[key] = []
            return
        
        def load_and_cache():
            try:
                result = loader_func(*args, **kwargs)
                self._cache.set(key, result, ttl)
                GLib.idle_add(self._emit_data_loaded, key, result)
                
                if key in self._pending_requests:
                    for callback in self._pending_requests[key]:
                        GLib.idle_add(callback, key, result)
                    del self._pending_requests[key]
                    
                return result
            except Exception as e:
                GLib.idle_add(self._emit_load_error, key, str(e))
                if key in self._pending_requests:
                    del self._pending_requests[key]
                raise
            finally:
                if key in self._loading:
                    del self._loading[key]
        
        future = self._executor.submit(load_and_cache)
        self._loading[key] = future
    
    def load_batch(self, base_key: str, start: int, count: int, 
                   loader_func: Callable, *args, **kwargs) -> None:
        if base_key not in self._loaded_ranges:
            self._loaded_ranges[base_key] = []
        
        ranges = self._loaded_ranges[base_key]
        missing_ranges = self._find_missing_ranges(ranges, start, count)
        
        if not missing_ranges:
            cached_batch = self._get_cached_batch(base_key, start, count)
            if cached_batch:
                GLib.idle_add(self._emit_batch_loaded, base_key, cached_batch)
                return
        
        for range_start, range_count in missing_ranges:
            batch_key = f"{base_key}_batch_{range_start}_{range_count}"
            
            def load_batch_data(r_start: int, r_count: int) -> None:
                try:
                    GLib.idle_add(self._emit_loading_progress, base_key, 0, r_count)
                    result = loader_func(r_start, r_count, *args, **kwargs)
                    
                    for i, item in enumerate(result):
                        item_key = f"{base_key}_{r_start + i}"
                        self._cache.set(item_key, item)
                        GLib.idle_add(self._emit_loading_progress, base_key, i + 1, r_count)
                    
                    ranges.append((r_start, r_start + len(result) - 1))
                    ranges.sort()
                    self._merge_overlapping_ranges(ranges)
                    
                    requested_batch = self._get_cached_batch(base_key, start, count)
                    GLib.idle_add(self._emit_batch_loaded, base_key, requested_batch)
                    
                except Exception as e:
                    GLib.idle_add(self._emit_load_error, batch_key, str(e))
                    
            self._executor.submit(load_batch_data, range_start, range_count)
    
    def _find_missing_ranges(self, loaded_ranges: List[Tuple[int, int]], 
                           start: int, count: int) -> List[Tuple[int, int]]:
        end = start + count - 1
        missing = []
        current_pos = start
        
        for range_start, range_end in loaded_ranges:
            if current_pos > end:
                break
                
            if current_pos < range_start:
                missing_count = min(range_start - current_pos, end - current_pos + 1)
                missing.append((current_pos, missing_count))
                current_pos = range_start
            
            if current_pos <= range_end:
                current_pos = range_end + 1
        
        if current_pos <= end:
            missing.append((current_pos, end - current_pos + 1))
        
        return missing
    
    def _merge_overlapping_ranges(self, ranges: List[Tuple[int, int]]) -> None:
        if len(ranges) <= 1:
            return
            
        i = 0
        while i < len(ranges) - 1:
            current_start, current_end = ranges[i]
            next_start, next_end = ranges[i + 1]
            
            if current_end >= next_start - 1:
                merged = (current_start, max(current_end, next_end))
                ranges[i] = merged
                ranges.pop(i + 1)
            else:
                i += 1
    
    def _get_cached_batch(self, base_key: str, start: int, count: int) -> Optional[List[Any]]:
        batch = []
        for i in range(start, start + count):
            item_key = f"{base_key}_{i}"
            cached_item = self._cache.get(item_key)
            if cached_item is None:
                return None
            batch.append(cached_item)
        return batch
    
    def get_cached(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def prefetch(self, keys: List[str], loader_func: Callable, *args, **kwargs) -> None:
        for key in keys:
            if not self._cache.get(key) and key not in self._loading:
                self.load_async(key, loader_func, key, *args, **kwargs)
    
    def invalidate(self, pattern: str) -> None:
        keys_to_remove = [k for k in self._cache._cache.keys() if pattern in k]
        with self._cache._lock:
            for key in keys_to_remove:
                if key in self._cache._cache:
                    del self._cache._cache[key]
                if key in self._cache._access_order:
                    self._cache._access_order.remove(key)
    
    def clear_cache(self, pattern: Optional[str] = None) -> None:
        if pattern is None:
            self._cache.clear()
        else:
            self.invalidate(pattern)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        return self._cache.get_stats()
    
    def is_loading(self, key: str) -> bool:
        return key in self._loading
    
    def _emit_data_loaded(self, key: str, data: Any) -> bool:
        self.emit('data-loaded', key, data)
        return False
    
    def _emit_load_error(self, key: str, error: str) -> bool:
        self.emit('load-error', key, error)
        return False
    
    def _emit_batch_loaded(self, base_key: str, batch: List[Any]) -> bool:
        self.emit('batch-loaded', base_key, batch)
        return False
    
    def _emit_loading_progress(self, key: str, current: int, total: int) -> bool:
        self.emit('loading-progress', key, current, total)
        return False
    
    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

class SmartPackageLoader(LazyLoader):
    def __init__(self, max_workers: int = 3):
        super().__init__(max_workers)
        self._aur_cache_ttl = 1800
        self._local_cache_ttl = 300
        self._search_cache_ttl = 900
        
    def load_package_info(self, package_name: str) -> None:
        def fetch_package():
            result = subprocess.run(['paru', '-Si', package_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return self._parse_package_info(result.stdout)
            else:
                raise Exception(f"Package {package_name} not found")
        
        self.load_async(f"package_{package_name}", fetch_package, ttl=self._aur_cache_ttl)
    
    def load_installed_packages(self) -> None:
        def fetch_installed():
            result = subprocess.run(['paru', '-Q'], capture_output=True, text=True)
            packages = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ', 1)
                    if len(parts) >= 2:
                        name, version = parts
                        packages.append({
                            'name': name, 
                            'version': version, 
                            'installed': True,
                            'repository': 'local'
                        })
            return packages
        
        self.load_async("installed_packages", fetch_installed, ttl=self._local_cache_ttl)
    
    def load_package_search(self, search_term: str, start: int, count: int) -> None:
        def fetch_search(batch_start: int, batch_count: int):
            cmd = ['paru', '-Ss']
            if search_term:
                cmd.append(search_term)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            packages = self._parse_search_results(result.stdout)
            
            end_idx = min(batch_start + batch_count, len(packages))
            return packages[batch_start:end_idx]
        
        batch_key = f"search_{search_term}" if search_term else "all_packages"
        self.load_batch(batch_key, start, count, fetch_search)
    
    def load_package_updates(self) -> None:
        def fetch_updates():
            result = subprocess.run(['paru', '-Qu'], capture_output=True, text=True)
            updates = []
            for line in result.stdout.strip().split('\n'):
                if line and '->' in line:
                    parts = line.split(' -> ')
                    if len(parts) == 2:
                        name_old = parts[0].split()
                        if len(name_old) >= 2:
                            name = name_old[0]
                            old_version = name_old[1]
                            new_version = parts[1]
                            updates.append({
                                'name': name,
                                'old_version': old_version,
                                'new_version': new_version,
                                'update_available': True
                            })
            return updates
        
        self.load_async("package_updates", fetch_updates, ttl=self._local_cache_ttl)
    
    def _parse_package_info(self, paru_output: str) -> Dict[str, Any]:
        info = {}
        current_section = None
        
        for line in paru_output.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if ':' in line and not line.startswith(' '):
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                if key == 'depends_on':
                    current_section = 'depends'
                    info[key] = [dep.strip() for dep in value.split()] if value else []
                elif key == 'optional_deps':
                    current_section = 'optional_deps'
                    info[key] = []
                else:
                    info[key] = value
                    current_section = None
            elif current_section and line.startswith(' '):
                if current_section == 'optional_deps':
                    info[current_section].append(line.strip())
        
        return info
    
    def _parse_search_results(self, paru_output: str) -> List[Dict[str, Any]]:
        packages = []
        lines = paru_output.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if '/' in line and not line.startswith(' '):
                try:
                    parts = line.split('/')
                    if len(parts) >= 2:
                        repo = parts[0]
                        name_version_info = parts[1]
                        
                        name_version_parts = name_version_info.split()
                        if len(name_version_parts) >= 2:
                            name = name_version_parts[0]
                            version = name_version_parts[1]
                            
                            description = ""
                            if i + 1 < len(lines) and lines[i + 1].startswith(' '):
                                description = lines[i + 1].strip()
                                i += 1
                            
                            installed = "(Installed)" in name_version_info
                            
                            packages.append({
                                'name': name,
                                'version': version,
                                'repository': repo,
                                'description': description,
                                'installed': installed
                            })
                except (IndexError, ValueError):
                    pass
            i += 1
        
        return packages

class VirtualizedListModel:
    def __init__(self, loader: LazyLoader, base_key: str, page_size: int = 50):
        self._loader = loader
        self._base_key = base_key
        self._page_size = page_size
        self._visible_range = (0, 0)
        self._data: Dict[int, Any] = {}
        self._callbacks: List[Callable] = []
        
        loader.connect('batch-loaded', self._on_batch_loaded)
        loader.connect('data-loaded', self._on_data_loaded)
    
    def add_data_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)
    
    def set_visible_range(self, start: int, end: int) -> None:
        if (start, end) == self._visible_range:
            return
            
        self._visible_range = (start, end)
        
        page_start = (start // self._page_size) * self._page_size
        page_end = ((end // self._page_size) + 1) * self._page_size
        needed_count = page_end - page_start
        
        self._loader.load_batch(self._base_key, page_start, needed_count, self._fetch_items)
    
    def get_item(self, index: int) -> Optional[Any]:
        return self._data.get(index)
    
    def get_cached_range(self, start: int, end: int) -> List[Optional[Any]]:
        return [self._data.get(i) for i in range(start, end + 1)]
    
    def clear_cache(self) -> None:
        self._data.clear()
        self._loader.clear_cache(self._base_key)
    
    def _fetch_items(self, start: int, count: int) -> List[Any]:
        return [f"Item {i}" for i in range(start, start + count)]
    
    def _on_batch_loaded(self, loader: LazyLoader, base_key: str, batch: List[Any]) -> None:
        if base_key == self._base_key:
            start_idx = len(self._data)
            for i, item in enumerate(batch):
                self._data[start_idx + i] = item
            
            for callback in self._callbacks:
                callback(base_key, batch)
    
    def _on_data_loaded(self, loader: LazyLoader, key: str, data: Any) -> None:
        if key.startswith(f"{self._base_key}_"):
            try:
                index = int(key.split("_")[-1])
                self._data[index] = data
                
                for callback in self._callbacks:
                    callback(key, data)
            except (ValueError, IndexError):
                pass
