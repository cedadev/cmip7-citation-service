import uuid
import xmltodict
import requests
from django.db import models
from citations.validators import validate_country, validate_orcid
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class Institutions(models.Model):
    """
    Model for Institutions that may be linked to several Authors/Funding streams.

    Id is auto incrementing.
    """

    name = models.CharField(max_length=120)
    acronym = models.CharField(max_length=10)
    country = models.CharField(max_length=120, validators=[validate_country])


    id = models.AutoField(primary_key=True)
    def __str__(self):
        return f'{self.name} ({self.acronym})' # Country

class Authors(models.Model):
    """
    Model for Authors with a list of affiliations.

    Id is unique, non auto incremental
    """

    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.CharField(max_length=100)
    orcid = models.CharField(max_length=19, blank=True, validators=[validate_orcid])
    affiliations = models.ManyToManyField(Institutions, blank=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    def __str__(self):
        return f'{self.first_name} {self.last_name} <{self.email}>'
       
class FundingStreams(models.Model):
    """
    Model for Funding Streams associated with a single Institute.

    Id is auto incrementing.
    """

    name = models.CharField(max_length=120)
    affiliation = models.ForeignKey(Institutions, on_delete=models.CASCADE)

    id = models.AutoField(primary_key=True)
    def __str__(self):
        return f'{self.name}'
    
class References(models.Model):
    """
    Store external references to the CMIP7 citation service

    Id is unique, non auto incrementing.
    """

    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=300)
    authorset = models.TextField()
    DOI = models.CharField(max_length=50)

    def __str__(self):
        return f'{self.title}'
    
class Citations(models.Model):
    """
    Model for citations that have multiple links on creation

    Id is auto incrementing.
    """

    # Still would be good to create citations/authors etc in any order

    name     = models.CharField(max_length=300, primary_key=True)
    abstract = models.TextField()
    drs_url  = models.CharField()
    doi_url  = models.CharField()
    rights   = models.CharField(max_length=30)
    license  = models.TextField()
    primary  = models.ForeignKey(
        Authors, on_delete=models.CASCADE,
        related_name='primary_author')
    contacts = models.ManyToManyField(
        Authors, related_name='contact_authors')
    institutions = models.ManyToManyField(Institutions)
    funders  = models.ManyToManyField(FundingStreams)

    # References
    is_cited_by = models.ForeignKey(
        References, on_delete=models.CASCADE,
        related_name='is_cited_by'
    )

    cites = models.ForeignKey(
        References, on_delete=models.CASCADE,
        related_name='cites'
    )

    is_referenced_by = models.ForeignKey(
        References, on_delete=models.CASCADE,
        related_name='is_referenced_by'
    )

    # An endpoint for obtaining a list of ESGF urls that can be rendered
    #data_access = 

@receiver(post_save, sender=Authors)
def extract_from_orcid(sender, instance, created, **kwargs):
    if created:
        r = xmltodict.parse(
            requests.get(
                f'https://pub.orcid.org/v3.0/expanded-search/?q=orcid%3A{instance.orcid}'
            ).text
        ).get('expanded-search:expanded-search',{}).get('expanded-search:expanded-result',None)
        
        # Demo loader for loading ORCID institutions to Author (if already known)
        if r is None:
            return
        
        for k, v in r.items():
            if k != 'expanded-search:institution-name':
                continue

            if not isinstance(v, list):
                v = [v]
            for inst in v:
                try:
                    institute = Institutions.objects.get(name=inst)
                    instance.affiliations.add(institute)
                    instance.save(update_fields='affiliations')
                except:
                    # Unknown institutions are ignored
                    pass