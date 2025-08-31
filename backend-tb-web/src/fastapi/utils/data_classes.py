from pydantic import BaseModel

class RunTaskRequest(BaseModel):
    storage_path: str
    task_name: str
