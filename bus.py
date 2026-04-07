import redis
import json
from datetime import datetime
from typing import Dict, Any

class RedisBus:
    def __init__(self, host='localhost', port=6379, db=0):
        # We wrapped this in try block for robust skeleton execution, in case Redis is not running
        try:
            self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.redis.ping()
        except redis.ConnectionError:
            self.redis = None
            print("[Warning] Redis not connected. Running without message bus persistence.")

    def log_interaction(self, message: Dict[str, Any]):
        if not self.redis:
            return
        
        try:
            key = f"log:{datetime.now().isoformat()}"
            self.redis.set(key, json.dumps(message))
            self.redis.publish("agent_bus", json.dumps(message))
        except Exception as e:
            print(f"[Redis Logging Error] {e}")
