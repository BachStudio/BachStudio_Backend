from uuid import UUID
from supabase import Client
from fastapi import HTTPException
from app.schemas.collect import CollectCreate, CollectUpdate

class CollectService:
    def __init__(self, db: Client):
        self.db = db
        self.table = "collects"

    async def get_collects(self, user_id: str):
        result = self.db.table(self.table).select("*").eq("owner_id", user_id).execute()
        return result.data

    async def create_collect(self, collect: CollectCreate, user_id: str):
        data = collect.model_dump()
        data["owner_id"] = user_id
        result = self.db.table(self.table).insert(data).execute()
        return result.data[0]

    async def get_collect(self, collect_id: UUID, user_id: str):
        result = self.db.table(self.table).select("*").eq("id", str(collect_id)).eq("owner_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Collect not found")
        return result.data[0]

    async def update_collect(self, collect_id: UUID, collect_update: CollectUpdate, user_id: str):
        data = collect_update.model_dump(exclude_unset=True)
        result = self.db.table(self.table).update(data).eq("id", str(collect_id)).eq("owner_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Collect not found or unauthorized")
        return result.data[0]

    async def delete_collect(self, collect_id: UUID, user_id: str):
        result = self.db.table(self.table).delete().eq("id", str(collect_id)).eq("owner_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Collect not found")
        return {"status": "success"}