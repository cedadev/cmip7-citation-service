from django import forms
from django.core.validators import RegexValidator
from django.forms import formset_factory

from citations.models import Citations

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

ContactFormSet = formset_factory(PartyForm, extra=1)

class CitationForm(forms.ModelForm):
    """Form for gathering Citation information"""

    alphanumeric = RegexValidator(
        r"^[0-9a-zA-Z-_.]*$",
        "Only alphanumeric characters and hyphens/underscores are allowed.",
    )

    abstract = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':"Abstract"}),
    )

    drs_url = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder':'DRS URL for the CMIP7 dataset'})
    )

    doi_url = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder':'DOI URL for the CMIP7 dataset'}),
        required=False
    )

    rights = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':'Usage rights for the CMIP7 dataset'})
    )

    license = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':"License for the CMIP7 dataset"})
    )

    field_order = [
        'title',
        'abstract',
        'drs_url',
        'doi_url',
        'rights',
        'license'
    ]

    class Meta:
        model = Citations
        fields = ['doi_url']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):

                field.widget.attrs.update({
                    "size": 100
                })
            else:

                field.widget.attrs.update({
                    "size": 60
                })

class EditCitationForm(CitationForm):

    alphanumeric = RegexValidator(
        r"^[0-9a-zA-Z-_.]*$",
        "Only alphanumeric characters and hyphens/underscores are allowed.",
    )

    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={
            'readonly':'readonly',
            'style':'background-color: #adadad;'})
    )

class NewCitationForm(CitationForm):

    alphanumeric = RegexValidator(
        r"^[0-9a-zA-Z-_.]*$",
        "Only alphanumeric characters and hyphens/underscores are allowed.",
    )

    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        widget=forms.TextInput(attrs={'placeholder':'Title of CMIP7 Citation record'})
    )