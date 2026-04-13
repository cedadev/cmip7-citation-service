from citations.consumer import KafkaConsumer
from citations.serializers import handle_update
from django.conf import settings

def main():
    consumer = KafkaConsumer(
        update_handler=handle_update, 
        config=settings.CONSUMER_CONFIG,
        topics=settings.CONSUMER_TOPICS
        )
    
    consumer.start()


if __name__ == '__main__':
    main()