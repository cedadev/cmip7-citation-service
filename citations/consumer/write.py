from typing import Union

from django.conf import settings
from django.db import models
from rest_framework import serializers

from citations.consumer import KafkaConsumer


def chain_new_objects(
        data: dict, 
        serializer: serializers.ModelSerializer, 
        model: type[models.Model], 
        filter_kwargs: list, 
        optionals: list = None,
        allow_update: bool = False,
        fill_data_parameters: bool = False,
    ) -> str:
    """
    Validate new model instances.
    """

    optionals = optionals or []
    filters = {k: data.get(k) for k in filter_kwargs if k in data}
    for opt in optionals:
        if data.get(opt):
            filters[opt] = data[opt]
    instance = model.objects.filter(**filters)

    # Create instance if not specified.
    if not instance:
        serial = serializer(data=data)
        serial.is_valid(raise_exception=True)
        serial.save()
        inst_pk = serial.validated_data['id']
    else:
        instance = instance[0]
        serial = serializer(data=data, instance=instance)

        serial.is_valid(raise_exception=True)
        update = False
        if allow_update:
            for k,v in data.items():
                if v != getattr(instance, k):
                    update = True

        if update:
            serial.save()
        inst_pk = serial.validated_data.get('id',instance.pk)

    # Should return newly created instance or existing one
    return inst_pk

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