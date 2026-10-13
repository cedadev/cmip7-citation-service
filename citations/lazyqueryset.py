from django.db.models import Model,QuerySet
from citations.utils import fullname
from citations.serializers import PartiesSerializer

class LazyQuerySet:

    def __init__(self, queryset: QuerySet, required_params: list):
        self.queryset = queryset
        self.required_params = required_params

    def __len__(self):
        return len(self.queryset)

    def __getitem__(self, index: slice):
        item = self.queryset[index]

        if isinstance(item, list):
            return [self.render(i) for i in item]

        return self.render(item)

    def render(self, item: Model):
        return {k: getattr(item, k, None) for k in self.required_params}

class FundingStreamLQ(LazyQuerySet):

    def render(self, item: Model):
        fs = {k: getattr(item, k, None) for k in self.list_param_reqs}
        fs["affiliation_id"] = item.affiliation_id
        return fs

class CitationLQ(LazyQuerySet):

    def render(self, item: Model):
        cite = {k: getattr(item, k, None) for k in self.required_params}
        
        cite["primary"] = {
            "fullname": fullname(PartiesSerializer(
                cite['primary']
            ).data),
            "id": cite['primary'].id,
        }
        return cite
