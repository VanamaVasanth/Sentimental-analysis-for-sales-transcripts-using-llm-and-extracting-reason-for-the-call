from django.urls import path
from .views import analysis_history, analyze_sentiment, analyze_form

urlpatterns = [
    path("analyze/", analyze_sentiment),
    path("form/", analyze_form),
    path("history/", analysis_history),
]

from .views import export_csv, export_pdf

urlpatterns += [
    path("export/csv/", export_csv),
    path("export/pdf/", export_pdf),
]
from .views import sentiment_dashboard

urlpatterns += [
    path("dashboard/", sentiment_dashboard),
]
from .views import rag_auto_response_view

urlpatterns += [
    path("rag-auto-response/", rag_auto_response_view),
]
