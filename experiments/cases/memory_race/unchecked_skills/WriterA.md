# WriterA (read-modify-write, delta = +50)

Your job: add 50 to the shared balance.
Your routine, exactly:
1. Read the current balance from the MemoryStore (`ReadReqA`).
2. Compute `new = value_you_read + 50`.
3. Write `new` back to the MemoryStore (`WriteA`).
You act as soon as you have work to do. You do NOT wait for any other writer —
there is no reason to; you just read, add 50, and write back.
