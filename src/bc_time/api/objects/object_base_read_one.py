from bc_time.api.objects.base import Base

class ObjectBaseReadOne(Base):
    def get_one(self, content_uid: int) -> dict:
        return self.api.get_one(
            content_type_id=self._content_type_id,
            content_uid=content_uid
        )