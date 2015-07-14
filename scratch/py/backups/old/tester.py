import monkey_asyncio

await = monkey_asyncio.get_event_loop().run_until_complete
coro = monkey_asyncio.coroutine

@coro
def zob(a):
 return a + 10

@coro
def a(a):
 b = yield from zob(a)
 b += yield from zob(a)
 b += yield from zob(a)
 b += yield from zob(a)
 return b + 10

def b(b):
 return await(a(b+10))

@coro
def c(c):
 return b(c+10)


print(await(c(1)))
