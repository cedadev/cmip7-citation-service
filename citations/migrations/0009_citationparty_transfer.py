from django.db import migrations

def populate_citationparty(apps, schema_editor):
    Citation = apps.get_model("citations", "Citations")
    CitationParty = apps.get_model("citations", "CitationParty")

    for citation in Citation.objects.all():
        for pos, party in enumerate(citation.contacts.all()):
            CitationParty.objects.create(
                citation=citation,
                party=party,
                position=pos,
            )

class Migration(migrations.Migration):

    dependencies = [
        ("citations", "0008_citationparty"),
    ]

    operations = [
        migrations.RunPython(populate_citationparty),
    ]