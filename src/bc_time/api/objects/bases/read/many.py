from bc_time.api.objects.base import Base

class Many(Base):
    def get_many(self, content_uids: list) -> dict:
        return self.api.get_many(
            content_type_id=self._content_type_id,
            content_uids=content_uids
        )