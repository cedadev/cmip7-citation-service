import logging

from django.conf import settings

if settings.DEBUG:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
logstream = logging.StreamHandler()

formatter = logging.Formatter('%(levelname)s [%(name)s]: %(message)s')
logstream.setFormatter(formatter)

LABEL_MAPPINGS = {
    'activity':'activity_id',
    'experiment': 'experiment_id',
    'source': 'source_id',
    'institution': 'institution_id',
    'domain': 'domain_id'
}

CORE_FACETS = [
    'mip_era',
    'activity_id',
    'experiment_id',
    'source_id',
    'institution_id',
]

ESGVOC_FACET_LABELS = ['mip_era','activity','institution','source','experiment', 'domain']