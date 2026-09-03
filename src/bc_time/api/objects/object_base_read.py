from bc_time.api.objects.bases.read.one import One
from bc_time.api.objects.bases.read.many import Many
from bc_time.api.objects.bases.read.all_using_pagination import AllUsingPagination

class ObjectBaseRead(One, Many, AllUsingPagination):
    pass
