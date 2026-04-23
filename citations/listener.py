import os

from django.conf import settings

from citations.consumer import KafkaConsumer
from citations.serializers import handle_update


def main():
    consumer = KafkaConsumer(
        update_handler=handle_update, 
        config=settings.CONSUMER_CONFIG,
        topics=settings.CONSUMER_TOPICS
        )
    
    try:
        os.system(f'touch {settings.HEALTHPROBE}')
        consumer.start()

    finally:
        os.system(f'rm {settings.HEALTHPROBE}')


if __name__ == '__main__':
    main()