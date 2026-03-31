from django.db import models
from rest_framework import serializers
from citations.consumer import KafkaConsumer
from django.conf import settings
from typing import Union

def chain_new_objects(
        data: dict, 
        serializer: serializers.ModelSerializer, 
        model: type[models.Model], 
        filter_kwargs: list, 
        optionals: list = None
    ) -> models.Model:
    """
    Validate new model instances.
    """

    optionals = optionals or []
    filters = {k: data[k] for k in filter_kwargs}
    for opt in optionals:
        if data.get(opt):
            filters[opt] = data[opt]
    instance = model.objects.filter(**filters)

    # Create instance if not specified.
    if not instance:
        serial = serializer(data=data)
        serial.is_valid(raise_exception=True)
        instance = create_instance(model, required_fields=serializer.Meta.required_fields, **dict(serial.validated_data))
    else:
        instance = instance[0]

    # Should return newly created instance or existing one
    return instance

def create_instance(model: models.Model, required_fields: list, **kwargs):
    """
    Send message to consumer to create new instance"""

    consumer = KafkaConsumer(
        settings.CONSUMER_CONFIG,
        settings.CONSUMER_TOPICS,
    )
    consumer.write_request(
        table=model._meta.label.split('.')[-1],
        method='create',
        content=kwargs
    )

    # Use settings.QUEUE_AWAIT_TIMEOUT
    id_kwargs = {k:v for k,v in kwargs.items() if k in required_fields}

    # Get newly created model from the table. Wait until it has been created.
    return model.objects.get(**id_kwargs)

def update_instance(model: models.Model, id: str, **kwargs):
    """
    Send message to consumer to update existing instance
    """
    
    consumer = KafkaConsumer(
        settings.CONSUMER_CONFIG,
        settings.CONSUMER_TOPICS,
    )

    consumer.write_request(
        table=model._meta.label.split('.')[-1],
        method='update',
        content=kwargs | {'id': id}
    )

    # Await update confirmation
    return model.objects.get(pk=id)

def delete_instance(model: models.Model, id: str, **kwargs):
    """
    Send message to consumer to update existing instance
    """
    
    consumer = KafkaConsumer(
        settings.CONSUMER_CONFIG,
        settings.CONSUMER_TOPICS,
    )

    consumer.write_request(
        table=model._meta.label.split('.')[-1],
        method='delete',
        content={'id':id}
    )

    # Await model deletion