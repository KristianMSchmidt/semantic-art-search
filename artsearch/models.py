from django.db import models


class SearchLog(models.Model):
    query = models.TextField(editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    username = models.CharField(max_length=255, editable=False, blank=True, null=True)

    def __str__(self):
        return f"{self.query} @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
