__author__ = "Daniel Westwood"
__contact__ = "daniel.westwood@stfc.ac.uk"
__copyright__ = "Copyright 2026 United Kingdom Research and Innovation"

## Consumer Unit for Kafka queues, able to utilise the ORM directly

import logging
from typing import Union

from confluent_kafka import Consumer, KafkaException, Producer

import citations.models as tables
import citations.serializers as serializers
from citations.utils import logstream

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False


class KafkaConsumer:
    def __init__(
        self,
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

                self.receive_message(message)

                self.consumer.commit(message=message, asynchronous=False)

        except KeyboardInterrupt:
            logger.info("Kafka consumer interrupted. Exiting...")

        except KafkaException as e:
            logger.error("Kafka exception: %s", e)

        finally:
            logger.info("Closing Kafka consumer...")

            self.consumer.close()

    def write_request(self, table: str, method: str, content: dict):
        """
        Request to update the database

        This can ONLY be executed by the Frontend service as the backend
        is stuck in the `start()` method loop.

        If the consumer is defined the message system will be utilised for write
        requesting. Otherwise the write can be made directly to the database.
        """
        logger.info(f'Write Request: {table}:{method} - {content}')

        if self.consumer is not None:
            self.send_message(table=table, method=method, content=content)
        else:
            self.handle_update(table=table, method=method, content=content)

    def send_message(self, table: str, method: str, content: dict):
        """
        Send message for write request to the events queue.

        If any formal message checks are required beyond the validation of data
        through the Views, here is where they should go.
        """

        if self.producer is None:
            raise KafkaException("No configuration provided")

        message = {"table": table, "method": method, "content": content}

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

    def receive_message(self, message):
        """
        Interpret message.value in terms of ORM

        Note: Use a separate module to write using ORM so it can
        be used outside the Kafka consumer.
        """
        self.handle_update(**dict(message.value))

    def handle_update(self, table: str, method: str, content: dict):
        """
        Handle ANY ORM Request updates here."""

        model = getattr(tables, table)
        serializer = getattr(serializers, table+'Serializer')
        pk = model._meta.pk.name

        match method:
            case "create":
                instance = model.objects.create(
                    **{c:v for c,v in content.items() if c not in serializer.Meta.relations}
                )
                for r in serializer.Meta.relations:
                    if r in content:
                        getattr(instance, r).set(content[r])
                instance.save()

            case "update":
                # Must have already validated that the primary key exists and does not change - frontend
                instance = model.objects.get(**{pk: content[pk]})
                content.pop(pk)
                for attr, value in content.items():
                    if attr in serializer.Meta.relations:
                        attr_i = getattr(instance, attr)
                        attr_i.set(value)
                    else:
                        setattr(instance, attr, value)
                instance.save()

            case "delete":
                model.objects.get(**{pk: content[pk]}).delete()
