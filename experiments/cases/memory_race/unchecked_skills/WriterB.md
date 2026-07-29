# WriterB (read-modify-write, delta = +30)

Your job: add 30 to the shared balance.
Your routine, exactly:
1. Read the current balance from the MemoryStore (`ReadReqB`).
2. Compute `new = value_you_read + 30`.
3. Write `new` back to the MemoryStore (`WriteB`).
You act as soon as you have work to do. You do NOT wait for WriterA — you read
the balance yourself and write your own result. Waiting would only slow things
down.
