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

Special notes on the citation auto-generation:
- The citation listener (see ``cmip7_listeners``) will add the user ``Citation Support`` to all auto-generated Citation records where a primary author has not been provided. For specific records (i.e some CORDEX records archived with WDC) a mapping exists to provide author lists instead.
- Authors (parties) added to a citation record will always present in the order they were given, including for the ``Cite As`` property on publication. This includes where the author list has been extracted from the WDC or another API by the listener and the order preserved on exporting to the citation service.

See below for a list of the functions used to fill content in the records.

.. automodule:: citations.serializers
    :members: