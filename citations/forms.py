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
        widget=forms.TextInput(attrs={'placeholder':'Title of CMIP7 Citation record'})
    )

    abstract = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':"Abstract"}),
    )

    drs_url = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':'DRS URL for the CMIP7 dataset'})
    )

    doi_url = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':'DOI URL for the CMIP7 dataset (if applicable)'}),
        required=False
    )

    rights = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':'Usage rights for the CMIP7 dataset'})
    )

    license = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder':"License for the CMIP7 dataset"})
    )

    class Meta:
        model = Citations
        fields = ['doi_url']