from django import forms
from django.core.validators import RegexValidator

from citations.models import Citations

class CitationForm(forms.ModelForm):
    """Form for gathering Citation information"""

    alphanumeric = RegexValidator(
        r"^[0-9a-zA-Z-_]*$",
        "Only alphanumeric characters and hyphens/underscores are allowed.",
    )

    title = forms.CharField(
        max_length=300,
        validators=[alphanumeric],
        help_text='Title of CMIP7 Citation record'
    )

    abstract = forms.CharField(
        widget=forms.Textarea(),
        help_text='Citation record abstract'
    )

    drs_url = forms.CharField(
        widget=forms.Textarea(),
        help_text='DRS URL for the CMIP7 dataset'
    )

    doi_url = forms.CharField(
        widget=forms.Textarea(),
        help_text='DOI URL for the CMIP7 dataset (if applicable)',
        required=False
    )

    rights = forms.CharField(
        widget=forms.Textarea(),
        help_text='Usage rights for the CMIP7 dataset',
    )

    license = forms.CharField(
        widget=forms.Textarea(),
        help_text='License for the CMIP7 dataset',
    )