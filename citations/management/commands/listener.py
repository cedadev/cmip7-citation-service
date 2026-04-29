import os

from django.conf import settings
from django.core.management.base import BaseCommand

from citations.consumer import CitationKafkaConsumer
from citations.serializers import handle_update

from esgf_core_utils.listeners.base import probe_success, probe_fail

class Command(BaseCommand):
    help = "Runs backend listener"

    def add_arguments(self, parser):
        parser.add_argument('healthprobe', type=str, help="Healthprobe filesystem location")

    def handle(self, healthprobe: str, *args, **kwargs):
        start_listener(healthprobe)

def start_listener(healthprobe: str):
    consumer = CitationKafkaConsumer(update_handler=handle_update)
    
    try:
        if healthprobe:
            probe_success(healthprobe)
        consumer.start()
    except Exception as e:
        print(f"Exited - {e}")
        if healthprobe:
            probe_fail(healthprobe)


if __name__ == '__main__':
    start_listener()