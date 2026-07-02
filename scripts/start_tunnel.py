"""Start a public ngrok tunnel to localhost:5000 and print the URL."""
from pyngrok import conf, ngrok

conf.get_default().region = "eu"
tunnel = ngrok.connect(5000, bind_tls=True)
print(tunnel.public_url, flush=True)

# Keep process alive
import time

while True:
    time.sleep(3600)
