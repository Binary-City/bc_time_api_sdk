from bc_time.api.objects.bases.read.all_using_pagination import AllUsingPagination
from bc_time.api.api import Api
from bc_time.api.enumerators.content_type import ContentType

class MobileAttendanceSelfServiceDevices(AllUsingPagination):
    def __init__(self, api: Api=None) -> None:
        super().__init__(api)
        self._content_type_id = ContentType.mobile_attendance_self_service_device