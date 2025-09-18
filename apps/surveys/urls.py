from django.urls import path
from .views import (
    survey_dashboard_admin, survey_dashboard_user, survey_dashboard,survey_new,
    section_create, section_rename, section_options, question_create, 
    question_rename, survey_audience_meta, survey_audience_user_search, survey_audience_preview
)

urlpatterns = [
    path('', survey_dashboard,   name='survey_dashboard'),
    path('admin/', survey_dashboard_admin, name='survey_dashboard_admin'),
    path('user/', survey_dashboard_user, name='survey_dashboard_user'),
    path('admin/new/', survey_new, name='survey_new'), 

    # === AJAX ===
    path('admin/<int:survey_id>/sections/create/', section_create, name='survey_section_create'),
    path('admin/sections/<int:section_id>/rename/', section_rename, name='survey_section_rename'),
    path('admin/<int:survey_id>/sections/options/', section_options, name='survey_section_options'),
    path('admin/sections/<int:section_id>/questions/create/', question_create, name='survey_question_create'),
    path('admin/questions/<int:question_id>/rename/', question_rename, name='survey_question_rename'),

    # === Segmentación (solo UI) ===
    path('admin/audience/meta/',        survey_audience_meta,        name='survey_audience_meta'),
    path('admin/audience/user-search/', survey_audience_user_search, name='survey_audience_user_search'),
    path('admin/audience/preview/',     survey_audience_preview,     name='survey_audience_preview'),

]
