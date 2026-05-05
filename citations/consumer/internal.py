__author__ = "Daniel Westwood"
__contact__ = "daniel.westwood@stfc.ac.uk"
__copyright__ = "Copyright 2026 United Kingdom Research and Innovation"

## Consumer Unit for Kafka queues, able to utilise the ORM directly

import logging
from typing import Any, Callable, Union

from confluent_kafka import Consumer, KafkaException, Producer

from citations.utils import logstream

from django.conf import settings

#from esgf_core_utils.models.kafka.consumer import KafkaConsumer

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False

class CitationInternalMessageProcessor: # MessageProcessor

    def __init__(self, handler: Callable):
        self.handler = handler

    def ingest(self, message):

        if hasattr(settings, 'FROM_KAFKA_TIMESTAMP'):
            if message.timestamp < settings.FROM_KAFKA_TIMESTAMP:
                return

        # Ignore messages before a specific timestamp as needed.
        self.handler(**dict(message))

    def direct_message(self, table: str, method: str, content: dict[str,Any]):
        self.handler(table=table, method=method, content=content)

# Temporary class - replace with import from esgf core utils package.
class TempKafkaConsumer:
    def __init__(
        self,
        message_processor: CitationInternalMessageProcessor, 
        config: Union[dict, None] = None,
        topics: Union[list, None] = None,
        timeout: Union[int, None] = None,
    ):

        if config is not None:
            # Front: Writes made to write_request -> send_message
            # Back: Writes received via start(msg_received) -> process_message -> handle_message
            self.consumer = Consumer(config)
            self.producer = Producer(config)
        else:
            # Writes made directly from write_request -> handle_update
            self.consumer = None
            self.producer = None

        self.message_processor = message_processor
        self.timeout = timeout or 5000  # ms
        self.topics = topics

    def start(self):
        """
        Consumer Listener Loop Start Function

        Runs ONLY on Listener deployment, in which case write_request CANNOT be utilised
        as the management command is blocking this from being used.
        """

        if self.consumer is None:
            raise KafkaException("No configuration provided")

        self.consumer.subscribe(self.topics)
        try:
            logger.info(
                "Kafka consumer started. Subscribed to topics: %s",
                self.topics,
            )

            while True:
                message = self.consumer.poll(timeout_ms=self.timeout)
                logger.info(
                    "Kafka consuming message: %s",
                    message,
                )

                if message is None:
                    continue

                self.message_processor.ingest(message)

                self.consumer.commit(message=message, asynchronous=False)

        except KeyboardInterrupt:
            logger.info("Kafka consumer interrupted. Exiting...")

        except KafkaException as e:
            logger.error("Kafka exception: %s", e)

        finally:
            logger.info("Closing Kafka consumer...")

            self.consumer.close()

class CitationKafkaConsumer(TempKafkaConsumer): # KafkaConsumer from ESGF

    def __init__(self, update_handler: str, *args, **kwargs):
        message_processor = CitationInternalMessageProcessor(update_handler)
        super().__init__(message_processor=message_processor, **kwargs)

    def write_request(self, table: str, method: str, content: dict, user: str):
        """
        Request to update the database

        This can ONLY be executed by the Frontend service as the backend
        is stuck in the `start()` method loop.

        If the consumer is defined the message system will be utilised for write
        requesting. Otherwise the write can be made directly to the database.
        """
        logger.info(f'Write Request from {user}: {table}:{method} - {content}')

        if self.consumer is not None:
            self.send_message(table=table, method=method, content=content, user=user)
        else:
            self.message_processor.direct_message(table=table, method=method, content=content)

    def send_message(self, table: str, method: str, content: dict, user: str):
        """
        Send message for write request to the events queue.

        If any formal message checks are required beyond the validation of data
        through the Views, here is where they should go.
        """

        if self.producer is None:
            raise KafkaException("No configuration provided")

        message = {"table": table, "method": method, "content": content, "user": user}

        def delivery_report(err, msg):
            if err is not None:
                raise ValueError(err)
            else:
                logger.info(
                    f"Message {msg.key()} successfully delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
                )

        self.producer.produce(
            topic=self.topics[0],
            key="CitationSvc",
            value=message,
            callback=delivery_report,
        )
        self.producer.flush()