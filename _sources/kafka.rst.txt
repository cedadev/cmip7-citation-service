==============================
Kafka Queue Systems & Listener
==============================

The Internal Kafka Queue System is currently not enabled in production (22/05/2026). When the functions ``create/update/delete_instance`` are used, this creates a ``CitationKafkaConsumer`` instance to handle sending the message. If the Internal queue is enabled (config is provided to Kafka) a message is added to the queue which is picked up by the backend sidecar deployment for this service, whose sole purpose is to listen for internal events and update the ORM.

If the internal queue is not used (which is currently the case). A log message is generated, and the consumer proceeds to directly ingest the message. The message handler directly calls the ``handle_update`` function in ``serializers.py`` which updates the database with the new content.

Lastly, a third deployment is also planned for production, which is separate to this Django application but is still worth noting. This deployment uses the ``cmip7_listeners`` repository from cedadev, and deploys a listener to the ``success`` topic in Kafka. Please see the repo at `https://github.com/cedadev/cmip7-listeners <https://github.com/cedadev/cmip7-listeners>`_ for details of how this listener is configured. TL;DR: The listener sends API requests to the citation service to create new records as needed, and updates the STAC items with citation links.

.. automodule:: citations.consumer.write
    :members:

.. automodule:: citations.consumer.internal
    :members: