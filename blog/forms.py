from django import forms

from .models import Comment, Post


class PostSubmissionForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Post
        fields = ["title", "body", "author_name", "author_email", "image"]
        widgets = {
            "title": forms.TextInput(attrs={"autocomplete": "off", "maxlength": 180}),
            "body": forms.Textarea(attrs={"rows": 7, "maxlength": 20000}),
            "author_name": forms.TextInput(attrs={"autocomplete": "name", "maxlength": 80}),
            "author_email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Images must be 5 MB or smaller.")
        return image

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Invalid submission.")
        return value


class CommentSubmissionForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Comment
        fields = ["author_name", "author_email", "body"]
        widgets = {
            "author_name": forms.TextInput(attrs={"autocomplete": "name", "maxlength": 80}),
            "author_email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "body": forms.Textarea(attrs={"rows": 3, "maxlength": 4000}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Invalid submission.")
        return value
