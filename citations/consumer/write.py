from typing import Callable

from django.conf import settings
from django.db import models

from citations.consumer import CitationKafkaConsumer


def create_instance(model: models.Model, user: str, update_handler: Callable, required_fields: list, **kwargs):
    """
    Send message to consumer to create new instance"""

    consumer = CitationKafkaConsumer(
        update_handler=update_handler,
        config=settings.CONSUMER_CONFIG,
        topics=settings.CONSUMER_TOPICS,
    )
    consumer.write_request(
        table=model._meta.label.split('.')[-1],
        method='create',
        content=kwargs,
        user=user
    )

def update_instance(model: models.Model, user: str, update_handler: Callable, id: str, **kwargs):
    """
    Send message to consumer to update existing instance
    """
    
    consumer = CitationKafkaConsumer(
        update_handler=update_handler,
        config=settings.CONSUMER_CONFIG,
        topics=settings.CONSUMER_TOPICS,
    )

    consumer.write_request(
        table=model._meta.label.split('.')[-1],
        method='update',
        content=kwargs | {'id': id},
        user=user
    )

def delete_instance(model: models.Model, user: str, update_handler: Callable, id: str, **kwargs):
    """
    Send message to consumer to update existing instance
    """
    
    consumer = CitationKafkaConsumer(
        update_handler=update_handler,
        config=settings.CONSUMER_CONFIG,
        topics=settings.CONSUMER_TOPICS,
    )

    consumer.write_request(
        table=model._meta.label.split('.')[-1],
        method='delete',
        content={'id':id},
        user=user
    )