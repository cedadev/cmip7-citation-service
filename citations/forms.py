from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import BaseFormSet, formset_factory
from django.utils.safestring import mark_safe

from citations.models import Citations

alphanumeric = RegexValidator(
    r"^[0-9a-zA-Z-_.]*$",
    "Only alphanumeric characters and hyphens/underscores are allowed.",
)

class PartyForm(forms.Form):
    first_name = forms.CharField(required=True)
    middle_names = forms.CharField(required=False)
    last_name = forms.CharField(required=True)
    orcid = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    field_order = [
        "first_name",
        "middle_names",
        "last_name",
        "orcid",
        "email",
    ]

class OneRequiredFormSet(BaseFormSet):
    def clean(self):
        super().clean()

        # Count how many forms have valid, non-empty data
        filled_forms = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                filled_forms += 1

        if filled_forms < 1:
            raise ValidationError(
                mark_safe("A <b>minimum of one contact</b> (the primary contact) must be provided.")
            )

class InstitutionForm(forms.Form):
    name = forms.CharField(required=True)
    acronym = forms.CharField(required=False)
    country = forms.CharField(required=False)

    field_order = [
        'name',
        'acronym',
        'country'
    ]

class FunderForm(forms.Form):
    name = forms.CharField(required=True)
    affiliation = forms.CharField(required=False)

    field_order = [
        'name',
        'affiliation'
    ]

class ReplicaForm(forms.Form):
    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={'placeholder':'Title of Replica Citation record','style':"width: 100%;"})
    )

class PrefixFormSet(BaseFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, prefix=self.prefix, **kwargs)

        if self.prefix == 'contact':
            return

        for form in self.forms:
            if not form.initial:
                continue
            
            for field in form.fields.values():
                field.widget.attrs['readonly'] = True
                field.widget.attrs['style'] = 'background-color: #adadad;'

class InstitutionBaseFormSet(PrefixFormSet):
    prefix='institution'
class FunderBaseFormSet(PrefixFormSet):
    prefix='funder'
class ContactBaseFormSet(PrefixFormSet, OneRequiredFormSet):
    prefix='contact'
class ReplicaBaseFormSet(PrefixFormSet):
    prefix='replica'

InstitutionFormSet = formset_factory(InstitutionForm, formset=InstitutionBaseFormSet, extra=1)
FunderFormSet = formset_factory(FunderForm, formset=FunderBaseFormSet, extra=1)
ContactFormSet = formset_factory(PartyForm, formset=ContactBaseFormSet, extra=1)
ReplicaFormSet = formset_factory(ReplicaForm, formset=ReplicaBaseFormSet, extra=1)

class CitationForm(forms.ModelForm):
    """Form for gathering Citation information"""

    abstract = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':"Abstract"}),
        required=False
    )

    drs_url = forms.CharField(
        label = 'DRS URL',
        widget=forms.TextInput(attrs={'placeholder':'DRS URL for the CMIP7 dataset'}),
        required=False
    )

    doi_url = forms.CharField(
        label='DOI URL',
        widget=forms.TextInput(attrs={'placeholder':'DOI URL for the CMIP7 dataset'}),
        required=False
    )

    rights = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':'Usage rights for the CMIP7 dataset'}),
        required=False
    )

    license = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':"License for the CMIP7 dataset"}),
        required=False
    )

    mip_era = forms.CharField(
        label = 'MIP Era (Validated against CVs)',
        widget=forms.TextInput(attrs={'placeholder':"CMIP7 MIP Era Facet"}),
        required=False
    )
    activity = forms.CharField(
        label = 'Activity (Validated against CVs)',
        widget=forms.TextInput(attrs={'placeholder':"CMIP7 Activity Facet"}),
        required=False
    )
    institution = forms.CharField(
        label = 'Institution (Validated against CVs)',
        widget=forms.TextInput(attrs={'placeholder':"CMIP7 Institution Facet"}),
        required=False
    )
    source = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder':"CMIP7 Source Facet"}),
        required=False
    )
    experiment = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder':"CMIP7 Experiment Facet"}),
        required=False
    )
    domain = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder':"CMIP7 Domain Facet"}),
        required=False
    )

    field_groups = {
        'General Information': ['Title', 'Abstract','DRS URL','DOI URL'],
        'CMIP7 Facets': [
            'MIP Era (Validated against CVs)',
            'Activity (Validated against CVs)',
            'Institution (Validated against CVs)',
            'Source',
            'Experiment',
            'Domain'],
        'Licensing and Fair Use': [
            'Rights',
            'License',
        ]}
    
    field_order = [
        'title',
        'abstract',
        'drs_url',
        'doi_url',
        'mip_era',
        'activity',
        'institution',
        'source',
        'experiment',
        'domain',
        'rights',
        'license'
    ]

    class Meta:
        model = Citations
        fields = ['doi_url']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                "style": "width: 100%;"
            })

class EditCitationForm(CitationForm):

    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={
            'readonly':'readonly',
            'style':'background-color: #adadad;'})
    )

class NewCitationForm(CitationForm):

    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={'placeholder':'Title of CMIP7 Citation record'})
    )