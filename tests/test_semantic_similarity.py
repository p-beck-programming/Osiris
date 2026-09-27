from app.semantic.embedder import embed_text
import numpy as np


a = embed_text("configure remote access to my server")
b = embed_text("set up Tailscale so I can connect from another device")
c = embed_text("buy ingredients for chicken tacos")


def similarity(x, y):
    return float(np.dot(x, y))


print("server ↔ tailscale:", similarity(a, b))
print("server ↔ tacos:", similarity(a, c))
