import uuid
import xmltodict
import requests
from django.db import models
from citations.validators import validate_orcid, validate_title
from django.db.models.signals import post_save
from django.contrib.postgres.fields import ArrayField

# Create your models here.
class Institutions(models.Model):
    """
    Model for Institutions that may be linked to several parties/Funding streams.

    Id is auto incrementing.
    """

    name = models.CharField(max_length=120)
    acronym = models.CharField(max_length=10)
    country = models.CharField(max_length=120)


    id = models.CharField(max_length=120, primary_key=True)
    def __str__(self):
        if self.acronym is not None:
            return f'{self.name} ({self.acronym})'  # Country
        else:
            return self.name

class Parties(models.Model):
    """
    Model for parties with a list of affiliations.

    Id is unique, non auto incremental
    """

    first_name = models.CharField(max_length=30, editable=False)
    last_name = models.CharField(max_length=30, editable=False)
    middle_names = models.CharField(max_length=60, blank=True, editable=False)
    email = models.CharField(max_length=100)
    orcid = models.CharField(max_length=19, blank=True, validators=[validate_orcid])
    affiliations = models.ManyToManyField(Institutions, blank=True)

    # Hashlib of name elements
    id = models.CharField(primary_key=True)
    def __str__(self):
        if self.middle_names is not None and self.middle_names != '':
            return f'{self.first_name} ({self.middle_names}) {self.last_name} <{self.email}>'
        return f'{self.first_name} {self.last_name} <{self.email}>'
       
class FundingStreams(models.Model):
    """
    Model for Funding Streams associated with a single Institute.

    Id is auto incrementing.
    """

    name = models.CharField(max_length=120)
    # Multiple affiliations per funding stream.
    affiliation = models.ForeignKey(Institutions, blank=True, on_delete=models.CASCADE)

    id = models.CharField(max_length=120, primary_key=True)
    def __str__(self):
        return f'{self.name}'
    
class References(models.Model):
    """
    Store external references to the CMIP7 citation service

    Id is unique, non auto incrementing.
    """

    title = models.CharField(max_length=300)
    partieset = models.TextField()
    DOI = models.CharField(max_length=50, primary_key=True)

    def __str__(self):
        return f'{self.title}'
    
class Citations(models.Model):
    """
    Model for citations that have multiple links on creation

    Id is auto incrementing.
    """

    # Still would be good to create citations/parties etc in any order

    id        = models.CharField(max_length=300, primary_key=True)
    title     = models.CharField(max_length=300, validators=[validate_title])
    version   = models.IntegerField()

    abstract = models.TextField()
    drs_url  = models.CharField()
    doi_url  = models.CharField()
    rights   = models.CharField(max_length=30)
    license  = models.TextField()
    primary  = models.ForeignKey(
        Parties, on_delete=models.PROTECT, # Primary author cannot be deleted.
        related_name='primary_party', blank=True, null=True)
    contacts = models.ManyToManyField(
        Parties, related_name='contact_parties', blank=True, null=True)
    institutions = models.ManyToManyField(Institutions, blank=True, null=True)
    funders  = models.ManyToManyField(FundingStreams, blank=True, null=True)

    editable = models.BooleanField(default=True)
    published = models.BooleanField(default=False)

    mip_era     = models.CharField(max_length=30, default='unknown')
    activity_id = models.CharField(max_length=30, default='unknown')
    institution_id = models.CharField(max_length=30, default='unknown')
    source_id = models.CharField(max_length=30, default='unknown')
    experiment_id = models.CharField(max_length=30, default='unknown')

    # keywords = ArrayField(
    #     models.CharField(max_length=50),
    #     blank=True,
    #     default=list
    # )

    # References
    is_cited_by = models.ForeignKey(
        References, on_delete=models.CASCADE,
        related_name='is_cited_by',blank=True, null=True
    )

    cites = models.ForeignKey(
        References, on_delete=models.CASCADE,
        related_name='cites', blank=True, null=True
    )

    is_referenced_by = models.ForeignKey(
        References, on_delete=models.CASCADE,
        related_name='is_referenced_by',blank=True, null=True
    )

    # An endpoint for obtaining a list of ESGF urls that can be rendered
    #data_access = 

def locate_institute(inst: str):
    """
    Use ROR lookup API to find institute-level metadata
    """

    ROR_api = 'https://api.ror.org/v2/organizations?query=' + '%20'.join(inst.split(' '))
    r = requests.get(ROR_api)
    if int(r.status_code) >= 300:
        print('Institute not found')
        return {'name':inst}
    
    resp = r.json()
    found = False
    inst_count = 0
    while not found and inst_count < 10:
        names = resp['items'][inst_count]['names']
        for entry in names:
            if entry['value'] == inst:
                found = True
                break

        if not found:
            inst_count += 1

    if found:

        acronym = None
        for n in resp['items'][inst_count]['names']:
            if 'acronym' in n['types']:
                acronym = n['value']

        return {
            'name':inst,
            'acronym': acronym or ''.join([i[0] for i in inst.split(' ')]),
            'country': resp['items'][inst_count]['locations'][0]['geonames_details']['country_name']
        }
    else:
        return {'name':inst}

def extract_from_orcid(orcid):
    r = xmltodict.parse(
        requests.get(
            f'https://pub.orcid.org/v3.0/expanded-search/?q=orcid%3A{orcid}'
        ).text
    ).get('expanded-search:expanded-search',{}).get('expanded-search:expanded-result',None)
    
    # Demo loader for loading ORCID institutions to Party (if already known)
    if r is None:
        return None
    
    institutions = []
    for k, v in r.items():
        if k != 'expanded-search:institution-name':
            continue

        if isinstance(v, str):
            v = [v]

        for inst in v:
            institutions.append(inst)
    
    return institutions