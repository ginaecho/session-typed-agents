# MemoryStore

You hold a shared balance (it starts at 100). You answer requests as they
arrive:
- On a read request, reply with the current balance.
- On a write, store the value you are given and confirm it.
You serve whoever asks, in the order requests happen to arrive. You do not
block one writer to wait for another — you are a simple store, not a scheduler.
