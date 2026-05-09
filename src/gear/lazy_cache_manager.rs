use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

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
        
        if let Some(entry) = cache.get_mut(key) {
            if !entry.is_expired() {
                return Some(entry.access().clone());
            } else {
                cache.remove(key);
            }
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
        let mut lru_key: Option<String> = None;
        let mut oldest_access = Instant::now();

        for (key, entry) in cache.iter() {
            if entry.last_access < oldest_access {
                oldest_access = entry.last_access;
                lru_key = Some(key.clone());
            }
        }

        if let Some(key) = lru_key {
            cache.remove(&key);
        }
    }

    pub fn set(&self, key: &str, value: T) {
        let mut cache = self.cache.lock().unwrap();
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
