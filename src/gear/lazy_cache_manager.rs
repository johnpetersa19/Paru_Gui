use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug)]
struct CacheEntry<T> {
    value: T,
    timestamp: Instant,
    ttl: Duration,
    last_access: Instant,
}

impl<T> CacheEntry<T> {
    fn is_expired(&self) -> bool {
        self.timestamp.elapsed() > self.ttl
    }

    fn access(&mut self) -> &T {
        self.last_access = Instant::now();
        &self.value
    }
}

#[derive(Debug)]
pub struct LazyCacheManager<T> {
    cache: Arc<Mutex<HashMap<String, CacheEntry<T>>>>,
    default_ttl: Duration,
    max_size: usize,
}

impl<T: Clone + Send + 'static> LazyCacheManager<T> {
    pub fn new(max_size: usize, default_ttl_secs: u64) -> Self {
        Self {
            cache: Arc::new(Mutex::new(HashMap::new())),
            default_ttl: Duration::from_secs(default_ttl_secs),
            max_size,
        }
    }

    pub fn get<F>(&self, key: &str, factory: F) -> Option<T>
    where
        F: FnOnce() -> T,
    {
        let mut cache = self.cache.lock().unwrap();
        
        self._cleanup_expired_locked(&mut cache);

        if let Some(entry) = cache.get_mut(key) {
            return Some(entry.access().clone());
        }

        let value = factory();
        let entry = CacheEntry {
            value: value.clone(),
            timestamp: Instant::now(),
            ttl: self.default_ttl,
            last_access: Instant::now(),
        };

        if cache.len() >= self.max_size {
            self._evict_lru(&mut cache);
        }

        cache.insert(key.to_string(), entry);
        Some(value)
    }

    fn _evict_lru(&self, cache: &mut HashMap<String, CacheEntry<T>>) {
        let lru_key = cache.iter()
            .min_by_key(|(_, e)| e.last_access)
            .map(|(k, _)| k.clone());

        if let Some(key) = lru_key {
            cache.remove(&key);
        }
    }

    pub fn cleanup_expired(&self) {
        let mut cache = self.cache.lock().unwrap();
        self._cleanup_expired_locked(&mut cache);
    }

    fn _cleanup_expired_locked(&self, cache: &mut HashMap<String, CacheEntry<T>>) {
        cache.retain(|_, entry| !entry.is_expired());
    }

    pub fn set(&self, key: &str, value: T) {
        let mut cache = self.cache.lock().unwrap();
        self._cleanup_expired_locked(&mut cache);
        
        if cache.len() >= self.max_size {
            self._evict_lru(&mut cache);
        }
        cache.insert(key.to_string(), CacheEntry {
            value,
            timestamp: Instant::now(),
            ttl: self.default_ttl,
            last_access: Instant::now(),
        });
    }

    pub fn clear(&self) {
        self.cache.lock().unwrap().clear();
    }
}
