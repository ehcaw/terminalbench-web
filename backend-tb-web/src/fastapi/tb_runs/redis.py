from upstash_redis import Redis
from dotenv import load_dotenv
import json
import time
from typing import List, Dict, Optional

load_dotenv()

redis = Redis.from_env()

async def check_redis_running_tasks(user_id: str, task_id: str):
    task_key = f"{user_id}_{task_id}"
    is_running = redis.get(task_key)
    return is_running is not None

async def set_redis_running_task(user_id: str, task_name: str, task_id: str):
    task_key = f"{user_id}_{task_name}"
    redis.set(task_key, task_id)

async def remove_redis_running_task(user_id: str, task_name: str):
    task_key = f"{user_id}_{task_name}"
    redis.delete(task_key)

async def get_redis_running_tasks(user_id: str):
    results = []
    for key in redis.scan_iter(f"{user_id}_*"):
        results.append(redis.get(key))
    return results

# New buffering functions
class TaskOutputBuffer:
    """Manages task output buffering in Redis"""

    def _get_batch_key(self, task_id: str, run_id: str) -> str:
        return f"{task_id}:{run_id}"

    @staticmethod
    def append_output(task_id: str, run_id: str, message: Dict) -> None:
        """Append a message to the task output buffer"""
        buffer_key = TaskOutputBuffer._get_buffer_key(task_id, run_id)
        meta_key = TaskOutputBuffer._get_metadata_key(task_id, run_id)

        try:
            # Add timestamp if not present
            if 'timestamp' not in message:
                message['timestamp'] = time.time()

            # Append to the list
            redis.lpush(buffer_key, json.dumps(message))

            # Update metadata (get current count for accuracy)
            current_count = redis.llen(buffer_key) or 0
            meta_data = {
                'last_updated': time.time(),
                'message_count': current_count,
                'task_id': task_id,
                'run_id': run_id,
                'status': message.get('type', 'unknown')
            }
            redis.set(meta_key, json.dumps(meta_data))

            # Set expiration (24 hours)
            redis.expire(buffer_key, 86400)
            redis.expire(meta_key, 86400)

        except Exception as e:
            print(f"DEBUG: Redis operation failed: {e}")

    @staticmethod
    def _get_buffer_key(task_id: str, run_id: str) -> str:
        return f"task_output:{task_id}:{run_id}"

    @staticmethod
    def _get_metadata_key(task_id: str, run_id: str) -> str:
        return f"task_meta:{task_id}:{run_id}"

    @staticmethod
    def get_full_output(task_id: str, run_id: str) -> List[Dict]:
        """Get all buffered output for a task run"""
        buffer_key = TaskOutputBuffer._get_buffer_key(task_id, run_id)

        try:
            # Get all messages (they're stored in reverse order due to lpush)
            messages = redis.lrange(buffer_key, 0, -1)

            if not messages:
                return []

            # Parse and reverse to get chronological order
            parsed_messages = []
            for msg in reversed(messages):
                try:
                    parsed_messages.append(json.loads(msg))
                except json.JSONDecodeError:
                    continue

            return parsed_messages
        except Exception as e:
            print(f"DEBUG: Failed to get output from Redis: {e}")
            return []

    @staticmethod
    async def get_output_since(task_id: str, run_id: str, since_seq: int) -> List[Dict]:
        """Get buffered output since a specific sequence number"""
        all_output = TaskOutputBuffer.get_full_output(task_id, run_id)
        return [msg for msg in all_output if msg.get('seq', 0) > since_seq]

    @staticmethod
    async def get_task_metadata(task_id: str, run_id: str) -> Optional[Dict]:
        """Get task metadata"""
        meta_key = TaskOutputBuffer._get_metadata_key(task_id, run_id)
        meta_data = redis.get(meta_key)

        if meta_data:
            try:
                return json.loads(meta_data)
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def mark_task_complete(task_id: str, run_id: str, final_status: str) -> None:
        """Mark a task as complete"""
        meta_key = TaskOutputBuffer._get_metadata_key(task_id, run_id)

        try:
            meta_data = TaskOutputBuffer.get_task_metadata(task_id, run_id) or {}

            meta_data.update({
                'completed_at': time.time(),
                'final_status': final_status,
                'is_complete': True
            })

            redis.set(meta_key, json.dumps(meta_data))
            redis.expire(meta_key, 86400)
        except Exception as e:
            print(f"DEBUG: Failed to mark task complete in Redis: {e}")

    @staticmethod
    async def cleanup_old_tasks(max_age_hours: int = 24) -> int:
        """Clean up task buffers older than max_age_hours"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        # Find all metadata keys
        for key in redis.scan_iter("task_meta:*"):
            meta_data = redis.get(key)
            if meta_data:
                try:
                    meta = json.loads(meta_data)
                    if meta.get('last_updated', 0) < cutoff_time:
                        # Extract task_id and run_id from key
                        parts = key.split(':')
                        if len(parts) >= 3:
                            task_id, run_id = parts[1], parts[2]
                            buffer_key = TaskOutputBuffer._get_buffer_key(task_id, run_id)

                            # Delete both keys
                            redis.delete(key)
                            redis.delete(buffer_key)
                            cleaned_count += 1
                except json.JSONDecodeError:
                    continue

        return cleaned_count

# Create a global instance
task_buffer = TaskOutputBuffer()
