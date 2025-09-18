from bc_time.api.objects.base import Base
from bc_time.api.constants.api import Api as ApiConstants

class AllUsingPagination(Base):
    def get_all_using_pagination(self, filters: dict=None, page: int=1, row_count: int=ApiConstants.DEFAULT_ROW_COUNT) -> dict:
        return self.api.get_all_using_pagination(
            content_type_id=self._content_type_id,
            filters=filters,
            page=page,
            row_count=row_count
        )