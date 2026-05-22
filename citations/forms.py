from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import BaseFormSet, formset_factory
from django.utils.safestring import mark_safe
from django.conf import settings

from citations.models import Citations

alphanumeric = RegexValidator(
    r"^[0-9a-zA-Z-_.]*$",
    "Only alphanumeric characters and hyphens/underscores are allowed.",
)
reference_options = (
    (1, 'is_cited_by'),
    (2, 'is_referenced_by'),
    (3, 'cites')
)

reference_mapping = [
    'is_cited_by',
    'is_referenced_by',
    'cites'
]

POPOVER_ATTRS = {
    'data-bs-toggle':'popover',
    'data-bs-trigger':'hover',
    'data-bs-placement': 'top',
}

class InstitutionIdForm(forms.Form):
    def __init__(self, *args, **kwargs):
        
        institution_ids = kwargs.pop('institution_ids', None)
        preselect = kwargs.pop('preselect', None)
        id_labels = kwargs.pop('id_labels', {})
        
        super().__init__(*args, **kwargs)

        if institution_ids is None:
            return
        
        preselect = preselect or []

        for inst in institution_ids:
            label = inst 
            if id_labels.get(inst):
                label = f'{inst} ({id_labels.get(inst)})'
            self.fields[f"inst_{inst}"] = forms.BooleanField(
                label=label,
                required=False,
                initial=(inst in preselect),
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

class ReferenceForm(forms.Form):
    title    = forms.CharField(
        max_length=300,
        required=True, 
        widget=forms.TextInput(attrs={'placeholder':"Reference Title"})
    )
    citeas   = forms.CharField(
        label='Cite As',
        required=False,
        widget=forms.Textarea(attrs={'placeholder':"Reference Citation in full"})
    )
    DOI      = forms.CharField(label='DOI', max_length=200, required=True, widget=forms.TextInput(attrs={'placeholder':"Reference DOI"}))
    relation = forms.ChoiceField(choices=reference_options)

    field_order = [
        'title',
        'Cite As',
        'DOI'
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                "style": "width: 100%;"
            })

class ReplicaForm(forms.Form):
    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={'placeholder':'Title of Replica Citation record','style':"width: 100%;"})
    )

class PrefixFormSet(BaseFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, prefix=self.prefix, **kwargs)

        if self.prefix == 'contact' or self.prefix == 'reference':
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
class ReferenceBaseFormSet(PrefixFormSet):
    prefix='reference'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for form in self.forms:
            if not form.initial:
                continue

            form.fields['DOI'].widget.attrs['readonly'] = True
            form.fields['DOI'].widget.attrs['style']    = 'background-color: #adadad;'

InstitutionFormSet = formset_factory(InstitutionForm, formset=InstitutionBaseFormSet, extra=1)
ReferenceFormSet = formset_factory(ReferenceForm, formset=ReferenceBaseFormSet, extra=1)
FunderFormSet = formset_factory(FunderForm, formset=FunderBaseFormSet, extra=1)
ContactFormSet = formset_factory(PartyForm, formset=ContactBaseFormSet, extra=1)
ReplicaFormSet = formset_factory(ReplicaForm, formset=ReplicaBaseFormSet, extra=1)

class CitationForm(forms.ModelForm):
    """Form for gathering Citation information"""

    abstract = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder':"Abstract",
            'data-bs-content':'Abstract will be prefilled from Essential Model Documentation if empty.'
            } | POPOVER_ATTRS),
        required=False
    )

    drs_url = forms.CharField(
        label = 'Data Access URL',
        widget=forms.TextInput(attrs={
            'placeholder':'Data Access URL for the CMIP dataset',
            'data-bs-content':'Only provide if data is not present in ESGF Core Nodes.'
            } | POPOVER_ATTRS),
        required=False
    )

    doi_url = forms.CharField(
        label='DOI URL',
        widget=forms.TextInput(attrs={
            'placeholder':'DOI URL for the CMIP dataset',
            'data-bs-content':'Only provide if data has pre-existing DOI already published.'
            } | POPOVER_ATTRS),
        required=False
    )

    rights = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder':'Usage rights for the CMIP dataset',
            'data-bs-content':'Rights will be prefilled from Essential Model Documentation if empty.'
        } | POPOVER_ATTRS),
        required=False
    )

    license = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder':"License for the CMIP dataset",
            'data-bs-content':'License will be prefilled from Essential Model Documentation if empty.'
        } | POPOVER_ATTRS),
        required=False
    )

    mip_era = forms.CharField(
        label = 'MIP Era',
        widget=forms.TextInput(attrs={
            'placeholder':"MIP Era Facet",
            'data-bs-content':'Validated against CMIP CVs.'
        } | POPOVER_ATTRS),
        required=False
    )
    activity_id = forms.CharField(
        label = 'Activity',
        widget=forms.TextInput(attrs={
            'placeholder':"Activity Facet",
            'data-bs-content':'Validated against CMIP CVs.'
        } | POPOVER_ATTRS),
        required=False
    )
    institution_id = forms.CharField(
        label = 'Institution',
        widget=forms.TextInput(attrs={
            'placeholder':"Institution Facet",
            'data-bs-content':'Validated against CMIP CVs.'
        } | POPOVER_ATTRS),
        required=False
    )
    source_id = forms.CharField(
        label = 'Source',
        widget=forms.TextInput(attrs={
            'placeholder':"Source Facet",
            'data-bs-content':'Validated against CMIP CVs.'
        } | POPOVER_ATTRS),
        required=False
    )
    experiment_id = forms.CharField(
        label = 'Experiment',
        widget=forms.TextInput(attrs={
            'placeholder':"(Driving) Experiment Facet",
            'data-bs-content':'Validated against CMIP CVs.'
        } | POPOVER_ATTRS),
        required=False
    )
    domain_id = forms.CharField(
        label = 'Domain',
        widget=forms.TextInput(attrs={
            'placeholder':"Domain Facet",
            'data-bs-content':'Validated against CORDEX CVs.'
        } | POPOVER_ATTRS),
        required=False
    )

    field_groups = {
        'General Information': ['Title', 'Abstract','Data Access URL','DOI URL'],
        'Search Facets': [
            'MIP Era',
            'Activity',
            'Institution',
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
        'activity_id',
        'institution_id',
        'source_id',
        'experiment_id',
        'domain_id',
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
            'style':'background-color: #adadad;',
            'data-bs-content':'Not possible to edit existing record title.'
        } | POPOVER_ATTRS),
        required=False
    )

class NewCitationForm(CitationForm):

    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={
            'placeholder':'Title of CMIP Citation record',
            'data-bs-content':'Title will be auto-assembled if the Search Facets are supplied. Either the Title or Search Facets must be given.'
        } | POPOVER_ATTRS),
        required=False
    )