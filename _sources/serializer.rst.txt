=============================================
Citation Auto Generation (Serializer Classes)
=============================================

Citation records (and other records) are auto-filled with additional content through the Serializer classes from django rest framework. All auto-generation and validation steps are centralised in the Serializer classes, with very little functionality being required from the ``Views`` classes except for rendering changes.

The process for updating a record is as follows:
 - UI/API view registers a change to a record.
 - Serializer is instantiated and the data is validated.
 - Serializer is then used to create/update records (``serializer.save``)
    - Provided data is filtered to remove unknown arguments (mostly from the API)
    - The ``fill_data_parameters`` serializer method fills in new parameters, and instantiates sub-records (i.e institutions, funders, parties)
    - The publication workflow is executed if required.
    - The update is made via the ``create/update instance`` functions that route changes through the Kafka system if it is in use.

See below for a list of the functions used to fill content in the records.

.. automodule:: citations.serializers
    :members: