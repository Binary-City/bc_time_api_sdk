from bc_time.api.objects.bases.read.one import One
from bc_time.api.objects.bases.read.many import Many
from bc_time.api.objects.bases.read.all_using_pagination import AllUsingPagination

class ObjectBaseRead(One, Many, AllUsingPagination):
    def get_one(self, content_uid: int) -> dict:
        return self.api.get_one(
            content_type_id=self._content_type_id,
            content_uid=content_uid
        )