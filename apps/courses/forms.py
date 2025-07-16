from django import forms
from .models import CourseHeader, CourseConfig, ModuleContent, Lesson, Quiz

class CourseHeaderForm(forms.ModelForm):
    class Meta:
        model = CourseHeader
        exclude = ['user', 'updated_at', 'created_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': 'required'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'required': 'required', 'min': '0', 'max': '100'}),
            'category': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'portrait': forms.FileInput(attrs={'class': 'form-control', 'required': 'required','id': 'id_portrait'}),
        }

class CourseConfigForm(forms.ModelForm):
    class Meta:
        model = CourseConfig
        exclude = ['updated_at', 'created_at']
        widgets = {
            'course_type': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'sequential': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'deadline': forms.NumberInput(attrs={'class': 'form-control', 'required': 'required'}),
            'audience': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'certification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_signature': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }



class ModuleContentForm(forms.ModelForm):
    """Formulario para crear módulos dentro de un curso."""
    class Meta:
        model = ModuleContent
        exclude = ['updated_at', 'created_at']
        widgets = {
            'course_header': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LessonForm(forms.ModelForm):
    """Formulario para crear lecciones dentro de un módulo."""
    class Meta:
        model = Lesson
        exclude = ['updated_at', 'created_at']
        widgets = {
            'module_content': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'lesson_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'resource': forms.FileInput(attrs={'class': 'form-control'}),
        }


class QuizForm(forms.ModelForm):
    """Formulario para crear un cuestionario opcional."""
    class Meta:
        model = Quiz
        exclude = ['updated_at', 'created_at']
        widgets = {
            'course_header': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
