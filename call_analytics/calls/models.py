from django.db import models

# Create your models here.
from django.db import models

class SentimentAnalysis(models.Model):
    input_text = models.TextField()
    overall_sentiment = models.CharField(max_length=20)
    satisfaction_score = models.IntegerField()
    reason_for_call = models.TextField()
    sentence_sentiments = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {self.overall_sentiment}"
