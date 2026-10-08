import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 30
accesslog = "-"
# Não registra query strings (podem conter "code" do OAuth)
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
