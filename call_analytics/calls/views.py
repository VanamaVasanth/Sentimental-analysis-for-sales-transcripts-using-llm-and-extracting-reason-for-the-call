import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from dotenv import load_dotenv
from .models import SentimentAnalysis
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# === Load Groq API Key from .env ===
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === Groq LangChain client ===
groq_llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama3-8b-8192"
)



# === Call Groq for sentiment analysis ===
def analyze_with_groq(text):
    prompt = f"""
You are a sentiment analysis expert.

Given the text below (can be a review or transcript), return JSON with:
- sentence_sentiments: list of {{sentence, sentiment}} (Positive, Neutral, Negative)
- overall_sentiment: Positive/Neutral/Negative
- satisfaction_score: 1–10
- reason_for_call: a short summary

Text:
{text}
"""
    response = groq_llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()

    # ✅ Clean Groq's Markdown JSON block
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                try:
                    return json.loads(part)
                except Exception:
                    continue

    # fallback if no JSON was extractable
    return {"raw_output": response.content, "error": "Could not parse JSON"}

# === API endpoint (/analyze/) ===
@csrf_exempt
def analyze_sentiment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            text = data.get("text", "").strip()

            if not text:
                return JsonResponse({"status": "error", "message": "Text is required"}, status=400)

            result = analyze_with_groq(text)
            return JsonResponse({"status": "success", "analysis": result})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Only POST method allowed"}, status=405)

# === Form view (/form/) ===
def analyze_form(request):
    result = None
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        if text:
            result = analyze_with_groq(text)

            # ✅ Save to DB if parsing succeeded
            if "sentence_sentiments" in result:
                SentimentAnalysis.objects.create(
                    input_text=text,
                    overall_sentiment=result["overall_sentiment"],
                    satisfaction_score=result["satisfaction_score"],
                    reason_for_call=result["reason_for_call"],
                    sentence_sentiments=result["sentence_sentiments"]
                )

    return render(request, "calls/analyze_form.html", {
        "result": json.dumps(result, indent=2) if result else None
    })

def analysis_history(request):
    entries = SentimentAnalysis.objects.order_by("-created_at")
    return render(request, "calls/analysis_history.html", {"entries": entries})

import csv
from django.http import HttpResponse
from .models import SentimentAnalysis
from io import BytesIO
from reportlab.pdfgen import canvas  # for PDF

# Export CSV
def export_csv(request):
    entries = SentimentAnalysis.objects.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sentiment_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Sentiment', 'Score', 'Reason', 'Text'])

    for entry in entries:
        writer.writerow([entry.created_at, entry.overall_sentiment, entry.satisfaction_score, entry.reason_for_call, entry.input_text])

    return response

# Export PDF
def export_pdf(request):
    entries = SentimentAnalysis.objects.all()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sentiment_export.pdf"'

    buffer = BytesIO()
    p = canvas.Canvas(buffer)

    y = 800
    for entry in entries:
        text = f"{entry.created_at} | {entry.overall_sentiment} | {entry.satisfaction_score} | {entry.reason_for_call}"
        p.drawString(40, y, text)
        y -= 20
        if y < 50:
            p.showPage()
            y = 800

    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

from django.utils.dateparse import parse_date

def analysis_history(request):
    queryset = SentimentAnalysis.objects.all()

    sentiment_filter = request.GET.get("sentiment")
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    if sentiment_filter:
        queryset = queryset.filter(overall_sentiment__iexact=sentiment_filter)

    if date_from:
        queryset = queryset.filter(created_at__date__gte=parse_date(date_from))

    if date_to:
        queryset = queryset.filter(created_at__date__lte=parse_date(date_to))

    return render(request, "calls/analysis_history.html", {
        "entries": queryset.order_by("-created_at")
    })

from django.core.paginator import Paginator

def analysis_history(request):
    queryset = SentimentAnalysis.objects.all().order_by("-created_at")

    paginator = Paginator(queryset, 10)  # 10 per page
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    return render(request, "calls/analysis_history.html", {
        "entries": page_obj
    })

def analysis_history(request):
    queryset = SentimentAnalysis.objects.all().order_by("-created_at")

    # === Filters ===
    sentiment_filter = request.GET.get("sentiment")
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")
    search_query = request.GET.get("q")

    if sentiment_filter:
        queryset = queryset.filter(overall_sentiment__iexact=sentiment_filter)

    if date_from:
        queryset = queryset.filter(created_at__date__gte=parse_date(date_from))

    if date_to:
        queryset = queryset.filter(created_at__date__lte=parse_date(date_to))

    if search_query:
        queryset = queryset.filter(
            models.Q(input_text__icontains=search_query) |
            models.Q(reason_for_call__icontains=search_query) |
            models.Q(overall_sentiment__icontains=search_query)
        )

    paginator = Paginator(queryset, 10)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    return render(request, "calls/analysis_history.html", {
        "entries": page_obj,
        "search_query": search_query or ""
    })

from django.db.models import Count
from django.http import JsonResponse

def sentiment_dashboard(request):
    # Flatten sentence_sentiments from all entries
    all_sentiments = SentimentAnalysis.objects.values_list('sentence_sentiments', flat=True)

    sentiment_count = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0,
    }

    for entry in all_sentiments:
        for item in entry:
            sentiment = item.get("sentiment")
            if sentiment in sentiment_count:
                sentiment_count[sentiment] += 1

    return render(request, "calls/dashboard.html", {
        "sentiment_data": sentiment_count
    })

from .rag_response_system import generate_rag_response

def rag_auto_response_view(request):
    if request.method == "POST":
        user_text = request.POST.get("text", "")
        result = generate_rag_response(user_text)

        return render(request, "calls/rag_response.html", {
            "answer": result["answer"],
            "sources": result["sources"]
        })

    return render(request, "calls/rag_response.html", {
        "answer": "",
        "sources": []
    })
