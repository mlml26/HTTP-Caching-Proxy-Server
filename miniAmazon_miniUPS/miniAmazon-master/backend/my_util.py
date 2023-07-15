import threading
class AtomicInteger:
    def __init__(self, i):
        self.num = i
        self.lock = threading.Lock()
    def getAndIncrement(self):
        with self.lock:
            ans = self.num
            self.num += 1
            return ans
    def get(self):
        with self.lock:
            return self.num

class AtomicStatus:
    def __init__(self, status):
        self.status = status
        self.lock = threading.Lock()
    def swap(self, status):
        with self.lock:
            old_status = self.status
            self.status = status
            return old_status

class AtomicDictionary:
    def __init__(self):
        self.map = {}
        self.lock = threading.Lock()
    def put(self, k, v):
        with self.lock:
            self.map[k] = v
    def get(self, k):
        with self.lock:
            return self.map[k]
    def contains(self, k):
        with self.lock:
            return k in self.map
    def remove(self, k):
        with self.lock:
            del self.map[k]
